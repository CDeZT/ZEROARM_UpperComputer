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
from zeroarm_desktop.transport.base import (
    CallbackRegistry,
    LinkStateEvent,
    Subscription,
    Transport,
    WritePriority,
)


class SessionState(Enum):
    DISCONNECTED = "disconnected"
    OPENING = "opening"
    HANDSHAKING = "handshaking"
    READONLY_READY = "readonly_ready"
    RECONNECT_WAIT = "reconnect_wait"
    CLOSING = "closing"
    FAULTED = "faulted"


class ActionStatus(Enum):
    PENDING = "pending"
    COMPLETED = "completed"
    UNKNOWN_OUTCOME = "unknown_outcome"
    FAILED = "failed"


class ActionRequest:
    """Thread-safe observable result of one V1 action command."""

    def __init__(self, command_name: str) -> None:
        self.command_name = command_name
        self._status = ActionStatus.PENDING
        self._result: WireResult | None = None
        self._detail = "awaiting device response"
        self._lock = RLock()

    @property
    def status(self) -> ActionStatus:
        with self._lock:
            return self._status

    @property
    def done(self) -> bool:
        return self.status is not ActionStatus.PENDING

    @property
    def result(self) -> WireResult | None:
        with self._lock:
            return self._result

    @property
    def raw_value(self) -> int | None:
        result = self.result
        return result.raw_value if result is not None else None

    @property
    def is_ok(self) -> bool:
        result = self.result
        return result.is_ok if result is not None else False

    @property
    def detail(self) -> str:
        with self._lock:
            return self._detail

    def _complete(self, result: WireResult) -> None:
        with self._lock:
            if self._status is not ActionStatus.PENDING:
                return
            self._result = result
            self._status = ActionStatus.COMPLETED
            self._detail = f"V1 result={result.raw_value}"

    def _finish(self, status: ActionStatus, detail: str) -> None:
        with self._lock:
            if self._status is not ActionStatus.PENDING:
                return
            self._status = status
            self._detail = detail


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
        request_timeout_s: float = 1.0,
        reconnect_delay_s: float = 0.5,
        max_reconnect_attempts: int = 3,
    ) -> None:
        self._validate_poll_rate(poll_rate_hz)
        if request_timeout_s <= 0 or reconnect_delay_s < 0:
            raise ValueError("request timeout must be positive and reconnect delay non-negative")
        if max_reconnect_attempts < 0:
            raise ValueError("max reconnect attempts must be non-negative")
        self._transport = transport
        self._codec = V1CommandCodec()
        self._parser = StreamParser()
        self._poll_rate_hz = poll_rate_hz
        self._actions_allowed = actions_allowed
        self._request_timeout_ns = int(request_timeout_s * 1_000_000_000)
        self._reconnect_delay_s = reconnect_delay_s
        self._max_reconnect_attempts = max_reconnect_attempts
        self._state = SessionState.DISCONNECTED
        self._identity: FirmwareIdentity | None = None
        self._snapshot: RobotSnapshot | None = None
        self._statistics = SessionStatistics()
        self._expected_command: int | None = None
        self._expected_audit: str | None = None
        self._request_deadline_ns: int | None = None
        self._last_result: WireResult | None = None
        self._pending_action: ActionRequest | None = None
        self._last_gripper: GripperResponse | None = None
        self._last_bench_state: BenchState | None = None
        self._last_bench_protection: MotorProtection | None = None
        self._generation = 0
        self._command_audit: list[str] = []
        self._events = CallbackRegistry()
        self._snapshots = CallbackRegistry()
        self._stop_poll = Event()
        self._poll_thread: Thread | None = None
        self._stop_lifecycle = Event()
        self._watchdog_thread: Thread | None = None
        self._reconnect_thread: Thread | None = None
        self._reconnect_attempts = 0
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
            self._reconnect_attempts = 0
            self._stop_lifecycle.clear()
        self._start_watchdog()
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
            self._stop_lifecycle.set()
            self._stop_watchdog()
            raise

    def disconnect(self) -> None:
        with self._lock:
            if self._state is SessionState.DISCONNECTED:
                return
        self._set_state(SessionState.CLOSING, "disconnect requested")
        self._stop_lifecycle.set()
        self._stop_poller()
        self._stop_reconnector()
        self._stop_watchdog()
        self._transport.close()
        for subscription in self._transport_subscriptions:
            subscription.cancel()
        self._transport_subscriptions.clear()
        with self._lock:
            pending = self._pending_action
            self._pending_action = None
            self._expected_command = None
            self._expected_audit = None
            self._request_deadline_ns = None
        if pending is not None:
            pending._finish(ActionStatus.UNKNOWN_OUTCOME, "session disconnected")
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

    def send_joint_target(self, target: object) -> ActionRequest:
        from zeroarm_desktop.domain.models import JointTarget

        if not self._actions_allowed:
            raise PermissionError("action commands are disabled for this Session")
        if not isinstance(target, JointTarget):
            raise TypeError("target must be JointTarget")
        if self.state is not SessionState.READONLY_READY:
            raise RuntimeError("Session is not ready")
        return self._send_action_request(
            V1Command.SET_JOINT_TARGET,
            self._codec.encode_joint_target(target),
        )

    def send_teach_start(self, joint_mask: int) -> ActionRequest:
        return self._send_action_request(
            V1Command.TEACH_START,
            self._codec.encode_joint_mask(V1Command.TEACH_START, joint_mask),
        )

    def send_teach_stop(self) -> ActionRequest:
        return self._send_action_request(
            V1Command.TEACH_STOP,
            self._codec.encode_empty_command(V1Command.TEACH_STOP),
        )

    def send_enable(self, joint_mask: int) -> ActionRequest:
        return self._send_action_request(
            V1Command.ENABLE,
            self._codec.encode_joint_mask(V1Command.ENABLE, joint_mask),
        )

    def send_disable(self, joint_mask: int) -> ActionRequest:
        return self._send_action_request(
            V1Command.DISABLE,
            self._codec.encode_joint_mask(V1Command.DISABLE, joint_mask),
        )

    def send_stop(self) -> ActionRequest:
        return self._send_action_request(
            V1Command.STOP,
            self._codec.encode_empty_command(V1Command.STOP),
            priority=WritePriority.EMERGENCY,
            supersede=True,
        )

    def send_home(self, joint_mask: int) -> ActionRequest:
        return self._send_action_request(
            V1Command.HOME,
            self._codec.encode_joint_mask(V1Command.HOME, joint_mask),
        )

    def send_clear_fault(self) -> ActionRequest:
        return self._send_action_request(
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

    def _send_action_request(
        self,
        command: V1Command,
        data: bytes,
        *,
        priority: WritePriority = WritePriority.NORMAL,
        supersede: bool = False,
    ) -> ActionRequest:
        if not self._actions_allowed:
            raise PermissionError("action commands are disabled for this Session")
        if self.state is not SessionState.READONLY_READY:
            raise RuntimeError("Session is not ready")
        request = ActionRequest(command.name)
        superseded_request: ActionRequest | None = None
        with self._lock:
            if self._pending_action is not None:
                if not supersede:
                    raise RuntimeError("another action request is already pending")
                superseded_request = self._pending_action
            self._pending_action = request
            self._last_result = None
        if superseded_request is not None:
            superseded_request._finish(
                ActionStatus.UNKNOWN_OUTCOME,
                f"superseded by {command.name}; command was not retried",
            )
        try:
            self._send(
                int(command),
                data,
                audit=command.name,
                priority=priority,
                supersede=supersede,
            )
        except Exception as error:
            with self._lock:
                if self._pending_action is request:
                    self._pending_action = None
            request._finish(ActionStatus.FAILED, str(error))
            raise
        return request

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

    def _send(
        self,
        command: int,
        data: bytes,
        *,
        audit: str | None = None,
        priority: WritePriority = WritePriority.NORMAL,
        supersede: bool = False,
    ) -> None:
        superseded_audit: str | None = None
        with self._lock:
            if supersede and self._expected_command is not None:
                superseded_audit = self._expected_audit or "request"
                self._expected_command = None
                self._expected_audit = None
                self._request_deadline_ns = None
            elif self._expected_command is not None:
                raise RuntimeError("V1 allows at most one request in flight")
            self._expected_command = command
            self._expected_audit = audit or f"0x{command:02X}"
            self._request_deadline_ns = monotonic_ns() + self._request_timeout_ns
            if audit is not None:
                self._command_audit.append(audit)
        self._increment(requests_sent=1)
        if superseded_audit is not None:
            self._events.publish(
                SessionEvent(
                    "request_superseded",
                    self.state,
                    f"{superseded_audit} superseded by {audit or command}; outcome unknown",
                )
            )
        try:
            self._transport.write(data, priority=priority)
        except Exception:
            with self._lock:
                self._expected_command = None
                self._expected_audit = None
                self._request_deadline_ns = None
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
            self._expected_audit = None
            self._request_deadline_ns = None
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
                    with self._lock:
                        self._reconnect_attempts = 0
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
                result = self._codec.decode_result(frame)
                with self._lock:
                    self._last_result = result
                    request = self._pending_action
                    self._pending_action = None
                if request is not None:
                    request._complete(result)
                self.poll_once()
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
            self._schedule_reconnect("transport failed")

    def _start_watchdog(self) -> None:
        with self._lock:
            if self._watchdog_thread is not None:
                return
            thread = Thread(target=self._watchdog_loop, name="zeroarm-watchdog", daemon=True)
            self._watchdog_thread = thread
        thread.start()

    def _stop_watchdog(self) -> None:
        thread = self._watchdog_thread
        if thread is not None and thread is not current_thread() and thread.ident is not None:
            thread.join(1.0)
        self._watchdog_thread = None

    def _watchdog_loop(self) -> None:
        while not self._stop_lifecycle.wait(0.005):
            with self._lock:
                deadline = self._request_deadline_ns
            if deadline is not None and monotonic_ns() >= deadline:
                self._handle_request_timeout()

    def _handle_request_timeout(self) -> None:
        with self._lock:
            deadline = self._request_deadline_ns
            if deadline is None or monotonic_ns() < deadline:
                return
            command = self._expected_command
            audit = self._expected_audit or "request"
            state = self._state
            request = self._pending_action
            if request is not None and command != int(V1Command.GET_STATE):
                self._pending_action = None
            self._expected_command = None
            self._expected_audit = None
            self._request_deadline_ns = None
        self._increment(request_timeouts=1)
        self._events.publish(
            SessionEvent("request_timeout", state, f"{audit} timed out; outcome unknown")
        )
        if request is not None and command != int(V1Command.GET_STATE):
            request._finish(ActionStatus.UNKNOWN_OUTCOME, f"{audit} timed out; not retried")
        if state is SessionState.HANDSHAKING:
            self._schedule_reconnect(f"handshake timeout ({audit})")
        elif command is not None and command != int(V1Command.GET_STATE):
            self._events.publish(
                SessionEvent("unknown_outcome", state, f"{audit} was not retried")
            )

    def _schedule_reconnect(self, reason: str) -> None:
        with self._lock:
            if self._stop_lifecycle.is_set() or self._state in {
                SessionState.CLOSING,
                SessionState.DISCONNECTED,
            }:
                return
            if self._reconnect_thread is not None:
                return
            if self._reconnect_attempts >= self._max_reconnect_attempts:
                exhausted = True
            else:
                exhausted = False
                self._reconnect_attempts += 1
                attempt = self._reconnect_attempts
                thread = Thread(
                    target=self._reconnect_once,
                    args=(attempt,),
                    name="zeroarm-reconnect",
                    daemon=True,
                )
                self._reconnect_thread = thread
        if exhausted:
            self._set_state(SessionState.FAULTED, f"{reason}; reconnect attempts exhausted")
            return
        self._set_state(
            SessionState.RECONNECT_WAIT,
            f"{reason}; reconnect {attempt}/{self._max_reconnect_attempts}",
        )
        thread.start()

    def _reconnect_once(self, attempt: int) -> None:
        retry_reason: str | None = None
        try:
            if self._stop_lifecycle.wait(self._reconnect_delay_s):
                return
            self._stop_poller()
            self._transport.close()
            with self._lock:
                pending = self._pending_action
                self._pending_action = None
                self._identity = None
                self._snapshot = None
                self._parser.reset()
                self._expected_command = None
                self._expected_audit = None
                self._request_deadline_ns = None
            if pending is not None:
                pending._finish(
                    ActionStatus.UNKNOWN_OUTCOME,
                    f"reconnect {attempt}; prior command not retried",
                )
            self._transport.open()
            self._set_state(SessionState.HANDSHAKING, f"reconnect {attempt}; sending HELLO")
            self._send(int(V1Command.HELLO), self._codec.hello_request(), audit="HELLO")
        except TransportError as error:
            retry_reason = f"reconnect {attempt} failed: {error}"
        finally:
            with self._lock:
                if self._reconnect_thread is current_thread():
                    self._reconnect_thread = None
        if retry_reason is not None:
            self._schedule_reconnect(retry_reason)

    def _stop_reconnector(self) -> None:
        thread = self._reconnect_thread
        if thread is not None and thread is not current_thread() and thread.ident is not None:
            thread.join(1.0)
        self._reconnect_thread = None

    def _start_poller(self) -> None:
        self._stop_poll.clear()
        self._poll_thread = Thread(target=self._poll_loop, name="zeroarm-poll", daemon=True)
        self._poll_thread.start()

    def _stop_poller(self) -> None:
        self._stop_poll.set()
        thread = self._poll_thread
        if thread is not None and thread is not current_thread() and thread.ident is not None:
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
        request_timeouts: int = 0,
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
                request_timeouts=current.request_timeouts + request_timeouts,
                unexpected_frames=current.unexpected_frames + unexpected_frames,
                poll_sent=current.poll_sent + poll_sent,
                poll_coalesced=current.poll_coalesced + poll_coalesced,
                snapshots_published=current.snapshots_published + snapshots_published,
            )

    @staticmethod
    def _validate_poll_rate(value: int) -> None:
        if value not in {20, 50, 100}:
            raise ValueError("poll rate must be 20, 50, or 100 Hz")
