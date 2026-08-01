"""V1 read-only connection, handshake, and polling state machine."""

from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from enum import Enum
from threading import Event, RLock, Thread, current_thread
from time import monotonic_ns

from zeroarm_desktop.domain.errors import ProtocolDecodeError, TransportError
from zeroarm_desktop.domain.models import FirmwareIdentity, RobotSnapshot
from zeroarm_desktop.protocol.frame_codec import ProtocolFrame
from zeroarm_desktop.protocol.stream_parser import ParserStatistics, StreamParser
from zeroarm_desktop.protocol.v1_codec import (
    BenchState,
    GripperResponse,
    MotorProtection,
    V1BenchCommand,
    V1Command,
    V1CommandCodec,
    V1GripperCommand,
    WireResult,
)
from zeroarm_desktop.transport.base import CallbackRegistry, LinkStateEvent, Subscription, Transport


class SessionState(Enum):
    DISCONNECTED = "disconnected"
    OPENING = "opening"
    HANDSHAKING = "handshaking"
    READONLY_READY = "readonly_ready"
    RECONNECT_WAIT = "reconnect_wait"
    CLOSING = "closing"
    FAULTED = "faulted"


@dataclass(frozen=True, slots=True)
class SessionEvent:
    kind: str
    state: SessionState
    detail: str


@dataclass(frozen=True, slots=True)
class SessionStatistics:
    requests_sent: int = 0
    responses_received: int = 0
    request_timeouts: int = 0
    unexpected_frames: int = 0
    poll_sent: int = 0
    poll_coalesced: int = 0
    snapshots_published: int = 0


class DeviceSession:
    """Own V1 parsing and expose immutable read-only device state."""

    def __init__(
        self,
        transport: Transport,
        *,
        poll_rate_hz: int = 20,
        actions_allowed: bool = False,
    ) -> None:
        self._validate_poll_rate(poll_rate_hz)
        self._transport = transport
        self._codec = V1CommandCodec()
        self._parser = StreamParser()
        self._poll_rate_hz = poll_rate_hz
        self._actions_allowed = actions_allowed
        self._state = SessionState.DISCONNECTED
        self._identity: FirmwareIdentity | None = None
        self._snapshot: RobotSnapshot | None = None
        self._statistics = SessionStatistics()
        self._expected_command: int | None = None
        self._last_result: WireResult | None = None
        self._last_gripper: GripperResponse | None = None
        self._last_bench_state: BenchState | None = None
        self._last_bench_protection: MotorProtection | None = None
        self._generation = 0
        self._command_audit: list[str] = []
        self._events = CallbackRegistry()
        self._snapshots = CallbackRegistry()
        self._stop_poll = Event()
        self._poll_thread: Thread | None = None
        self._transport_subscriptions: list[Subscription] = []
        self._lock = RLock()

    @property
    def state(self) -> SessionState:
        with self._lock:
            return self._state

    @property
    def identity(self) -> FirmwareIdentity | None:
        with self._lock:
            return self._identity

    @property
    def latest_snapshot(self) -> RobotSnapshot | None:
        with self._lock:
            return self._snapshot

    @property
    def statistics(self) -> SessionStatistics:
        with self._lock:
            return self._statistics

    @property
    def parser_statistics(self) -> ParserStatistics:
        with self._lock:
            return self._parser.statistics

    @property
    def actions_allowed(self) -> bool:
        return self._actions_allowed

    @property
    def command_audit(self) -> tuple[str, ...]:
        with self._lock:
            return tuple(self._command_audit)

    def connect(self) -> None:
        with self._lock:
            if self._state is not SessionState.DISCONNECTED:
                return
            self._identity = None
            self._snapshot = None
            self._parser.reset()
        self._set_state(SessionState.OPENING, "opening transport")
        self._transport_subscriptions = [
            self._transport.subscribe_bytes(self._on_bytes),
            self._transport.subscribe_state(self._on_link_state),
        ]
        try:
            self._transport.open()
            self._set_state(SessionState.HANDSHAKING, "transport open; sending HELLO")
            self._send(int(V1Command.HELLO), self._codec.hello_request(), audit="HELLO")
        except TransportError as error:
            self._set_state(SessionState.FAULTED, str(error))
            raise

    def disconnect(self) -> None:
        with self._lock:
            if self._state is SessionState.DISCONNECTED:
                return
        self._set_state(SessionState.CLOSING, "disconnect requested")
        self._stop_poller()
        self._transport.close()
        for subscription in self._transport_subscriptions:
            subscription.cancel()
        self._transport_subscriptions.clear()
        with self._lock:
            self._expected_command = None
        self._set_state(SessionState.DISCONNECTED, "transport closed")

    def set_poll_rate_hz(self, value: int) -> None:
        self._validate_poll_rate(value)
        with self._lock:
            self._poll_rate_hz = value

    def pause_polling(self) -> None:
        """Stop the background poller and wait for it to exit.

        Used by controlled shutdown and other paths that must own the single
        in-flight request slot without racing the poller thread.
        """
        self._stop_poller()

    def resume_polling(self) -> None:
        """Restart the background poller if the session is still ready."""
        with self._lock:
            if self._state is not SessionState.READONLY_READY or self._poll_thread is not None:
                return
        self._start_poller()

    def poll_once(self) -> bool:
        with self._lock:
            if self._state is not SessionState.READONLY_READY:
                return False
            if self._expected_command is not None:
                self._increment(poll_coalesced=1)
                return False
        self._increment(poll_sent=1)
        self._send(int(V1Command.GET_STATE), self._codec.get_state_request(), audit="GET_STATE")
        return True

    def send_joint_target(self, target: object) -> WireResult:
        from zeroarm_desktop.domain.models import JointTarget

        if not self._actions_allowed:
            raise PermissionError("action commands are disabled for this Session")
        if not isinstance(target, JointTarget):
            raise TypeError("target must be JointTarget")
        if self.state is not SessionState.READONLY_READY:
            raise RuntimeError("Session is not ready")
        self._last_result = None
        self._send(
            int(V1Command.SET_JOINT_TARGET),
            self._codec.encode_joint_target(target),
            audit="SET_JOINT_TARGET",
        )
        result = self._last_result
        if result is None:
            raise RuntimeError("Mock action did not return a synchronous V1 result")
        self.poll_once()
        return result

    def send_teach_start(self, joint_mask: int) -> WireResult:
        return self._send_action_result(
            V1Command.TEACH_START,
            self._codec.encode_joint_mask(V1Command.TEACH_START, joint_mask),
        )

    def send_teach_stop(self) -> WireResult:
        return self._send_action_result(
            V1Command.TEACH_STOP,
            self._codec.encode_empty_command(V1Command.TEACH_STOP),
        )

    def send_enable(self, joint_mask: int) -> WireResult:
        return self._send_action_result(
            V1Command.ENABLE,
            self._codec.encode_joint_mask(V1Command.ENABLE, joint_mask),
        )

    def send_disable(self, joint_mask: int) -> WireResult:
        return self._send_action_result(
            V1Command.DISABLE,
            self._codec.encode_joint_mask(V1Command.DISABLE, joint_mask),
        )

    def send_stop(self) -> WireResult:
        return self._send_action_result(
            V1Command.STOP,
            self._codec.encode_empty_command(V1Command.STOP),
        )

    def send_home(self, joint_mask: int) -> WireResult:
        return self._send_action_result(
            V1Command.HOME,
            self._codec.encode_joint_mask(V1Command.HOME, joint_mask),
        )

    def send_clear_fault(self) -> WireResult:
        return self._send_action_result(
            V1Command.CLEAR_FAULT,
            self._codec.encode_empty_command(V1Command.CLEAR_FAULT),
        )

    def send_gripper_ping(self, servo_id: int) -> GripperResponse:
        """Readonly STS gripper ping; allowed on Serial without action authorization."""
        return self._send_readonly_gripper(
            V1GripperCommand.PING,
            self._codec.encode_gripper_ping(servo_id),
        )

    def send_gripper_read(self, servo_id: int, address: int, length: int) -> GripperResponse:
        """Readonly STS register read; action writes/moves remain blocked."""
        return self._send_readonly_gripper(
            V1GripperCommand.READ,
            self._codec.encode_gripper_read(servo_id, address, length),
        )

    def send_bench_query(self, motor_id: int) -> BenchState:
        """Readonly motor bench query; no arbitrary pass-through."""
        return self._send_readonly_bench_state(
            V1BenchCommand.QUERY,
            self._codec.encode_bench_id_command(V1BenchCommand.QUERY, motor_id),
        )

    def send_bench_get_protection(self, motor_id: int) -> MotorProtection:
        return self._send_readonly_bench_protection(
            V1BenchCommand.GET_PROTECTION,
            self._codec.encode_bench_id_command(V1BenchCommand.GET_PROTECTION, motor_id),
        )

    def _send_action_result(self, command: V1Command, data: bytes) -> WireResult:
        if not self._actions_allowed:
            raise PermissionError("action commands are disabled for this Session")
        self._last_result = None
        self._send(int(command), data, audit=command.name)
        result = self._last_result
        if result is None:
            raise RuntimeError("Mock action did not return a synchronous V1 result")
        self.poll_once()
        return result

    def _send_readonly_gripper(self, command: V1GripperCommand, data: bytes) -> GripperResponse:
        if self.state is not SessionState.READONLY_READY:
            raise RuntimeError("Session is not ready")
        self._last_gripper = None
        paused = self._pause_for_inline_request()
        try:
            self._send(int(command), data, audit=f"GRIPPER_{command.name}")
        finally:
            if paused:
                self.resume_polling()
        response = self._last_gripper
        if response is None:
            raise RuntimeError("gripper response missing")
        return response

    def _send_readonly_bench_state(self, command: V1BenchCommand, data: bytes) -> BenchState:
        if self.state is not SessionState.READONLY_READY:
            raise RuntimeError("Session is not ready")
        self._last_bench_state = None
        paused = self._pause_for_inline_request()
        try:
            self._send(int(command), data, audit=f"BENCH_{command.name}")
        finally:
            if paused:
                self.resume_polling()
        state = self._last_bench_state
        if state is None:
            raise RuntimeError("bench state response missing")
        return state

    def _send_readonly_bench_protection(
        self, command: V1BenchCommand, data: bytes
    ) -> MotorProtection:
        if self.state is not SessionState.READONLY_READY:
            raise RuntimeError("Session is not ready")
        self._last_bench_protection = None
        paused = self._pause_for_inline_request()
        try:
            self._send(int(command), data, audit=f"BENCH_{command.name}")
        finally:
            if paused:
                self.resume_polling()
        protection = self._last_bench_protection
        if protection is None:
            raise RuntimeError("bench protection response missing")
        return protection

    def _pause_for_inline_request(self) -> bool:
        with self._lock:
            active = self._poll_thread is not None
        if active:
            self.pause_polling()
        return active

    def subscribe_snapshots(self, callback: Callable[[RobotSnapshot], None]) -> Subscription:
        return self._snapshots.subscribe(callback)

    def subscribe_events(self, callback: Callable[[SessionEvent], None]) -> Subscription:
        return self._events.subscribe(callback)

    def _send(self, command: int, data: bytes, *, audit: str | None = None) -> None:
        with self._lock:
            if self._expected_command is not None:
                raise RuntimeError("V1 allows at most one request in flight")
            self._expected_command = command
            if audit is not None:
                self._command_audit.append(audit)
        self._increment(requests_sent=1)
        try:
            self._transport.write(data)
        except Exception:
            with self._lock:
                self._expected_command = None
            raise

    def _on_bytes(self, chunk: bytes) -> None:
        for frame in self._parser.feed(chunk, received_monotonic_ns=monotonic_ns()):
            self._handle_frame(frame)

    def _handle_frame(self, frame: ProtocolFrame) -> None:
        with self._lock:
            expected = self._expected_command
            if expected is None or frame.command != expected:
                self._increment(unexpected_frames=1)
                return
            self._expected_command = None
        self._increment(responses_received=1)
        try:
            if expected == int(V1Command.HELLO):
                identity = self._codec.decode_hello(frame)
                with self._lock:
                    self._identity = identity
                self._events.publish(
                    SessionEvent("hello_received", self.state, identity.hello_text)
                )
                self._send(
                    int(V1Command.GET_STATE), self._codec.get_state_request(), audit="GET_STATE"
                )
                return
            if expected == int(V1Command.GET_STATE):
                if len(frame.payload) == 1:
                    result = self._codec.decode_result(frame)
                    raise ProtocolDecodeError(f"GET_STATE returned result {result.raw_value}")
                with self._lock:
                    self._generation += 1
                    generation = self._generation
                snapshot = self._codec.decode_state(
                    frame,
                    generation=generation,
                    received_wall_utc=datetime.now(UTC),
                )
                with self._lock:
                    self._snapshot = snapshot
                    first_snapshot = self._state is SessionState.HANDSHAKING
                self._increment(snapshots_published=1)
                self._snapshots.publish(snapshot)
                if first_snapshot:
                    self._set_state(SessionState.READONLY_READY, "V1 read-only handshake complete")
                    self._start_poller()
                return
            if expected in {
                int(V1Command.SET_JOINT_TARGET),
                int(V1Command.TEACH_START),
                int(V1Command.TEACH_STOP),
                int(V1Command.ENABLE),
                int(V1Command.DISABLE),
                int(V1Command.STOP),
                int(V1Command.HOME),
                int(V1Command.CLEAR_FAULT),
            }:
                self._last_result = self._codec.decode_result(frame)
                return
            if expected in {int(V1GripperCommand.PING), int(V1GripperCommand.READ)}:
                self._last_gripper = self._codec.decode_gripper_response(frame)
                return
            if expected == int(V1BenchCommand.QUERY):
                self._last_bench_state = self._codec.decode_bench_state(frame)
                return
            if expected == int(V1BenchCommand.GET_PROTECTION):
                self._last_bench_protection = self._codec.decode_bench_protection(frame)
                return
        except ProtocolDecodeError as error:
            self._set_state(SessionState.FAULTED, str(error))

    def _on_link_state(self, event: LinkStateEvent) -> None:
        if event.current.value == "failed":
            self._stop_poller()
            self._set_state(
                SessionState.RECONNECT_WAIT, "transport failed; read-only reconnect required"
            )

    def _start_poller(self) -> None:
        self._stop_poll.clear()
        self._poll_thread = Thread(target=self._poll_loop, name="zeroarm-poll", daemon=True)
        self._poll_thread.start()

    def _stop_poller(self) -> None:
        self._stop_poll.set()
        thread = self._poll_thread
        if thread is not None and thread is not current_thread():
            thread.join(1.0)
        self._poll_thread = None

    def _poll_loop(self) -> None:
        while True:
            with self._lock:
                period_s = 1.0 / self._poll_rate_hz
            if self._stop_poll.wait(period_s):
                return
            self.poll_once()

    def _set_state(self, state: SessionState, detail: str) -> None:
        with self._lock:
            self._state = state
        self._events.publish(SessionEvent("state_changed", state, detail))

    def _increment(
        self,
        *,
        requests_sent: int = 0,
        responses_received: int = 0,
        unexpected_frames: int = 0,
        poll_sent: int = 0,
        poll_coalesced: int = 0,
        snapshots_published: int = 0,
    ) -> None:
        with self._lock:
            current = self._statistics
            self._statistics = SessionStatistics(
                requests_sent=current.requests_sent + requests_sent,
                responses_received=current.responses_received + responses_received,
                request_timeouts=current.request_timeouts,
                unexpected_frames=current.unexpected_frames + unexpected_frames,
                poll_sent=current.poll_sent + poll_sent,
                poll_coalesced=current.poll_coalesced + poll_coalesced,
                snapshots_published=current.snapshots_published + snapshots_published,
            )

    @staticmethod
    def _validate_poll_rate(value: int) -> None:
        if value not in {20, 50, 100}:
            raise ValueError("poll rate must be 20, 50, or 100 Hz")
