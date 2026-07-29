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
from zeroarm_desktop.protocol.stream_parser import StreamParser
from zeroarm_desktop.protocol.v1_codec import V1Command, V1CommandCodec
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

    def __init__(self, transport: Transport, *, poll_rate_hz: int = 20) -> None:
        self._validate_poll_rate(poll_rate_hz)
        self._transport = transport
        self._codec = V1CommandCodec()
        self._parser = StreamParser()
        self._poll_rate_hz = poll_rate_hz
        self._state = SessionState.DISCONNECTED
        self._identity: FirmwareIdentity | None = None
        self._snapshot: RobotSnapshot | None = None
        self._statistics = SessionStatistics()
        self._expected_command: V1Command | None = None
        self._generation = 0
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
            self._send(V1Command.HELLO, self._codec.hello_request())
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

    def poll_once(self) -> bool:
        with self._lock:
            if self._state is not SessionState.READONLY_READY:
                return False
            if self._expected_command is not None:
                self._increment(poll_coalesced=1)
                return False
        self._increment(poll_sent=1)
        self._send(V1Command.GET_STATE, self._codec.get_state_request())
        return True

    def subscribe_snapshots(self, callback: Callable[[RobotSnapshot], None]) -> Subscription:
        return self._snapshots.subscribe(callback)

    def subscribe_events(self, callback: Callable[[SessionEvent], None]) -> Subscription:
        return self._events.subscribe(callback)

    def _send(self, command: V1Command, data: bytes) -> None:
        with self._lock:
            if self._expected_command is not None:
                raise RuntimeError("V1 allows at most one request in flight")
            self._expected_command = command
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
            if expected is V1Command.HELLO:
                identity = self._codec.decode_hello(frame)
                with self._lock:
                    self._identity = identity
                self._events.publish(
                    SessionEvent("hello_received", self.state, identity.hello_text)
                )
                self._send(V1Command.GET_STATE, self._codec.get_state_request())
                return
            if expected is V1Command.GET_STATE:
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
