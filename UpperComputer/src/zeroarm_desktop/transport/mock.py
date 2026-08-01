"""In-process transport backed by a real byte-level V1 mock device."""

from collections.abc import Callable
from dataclasses import dataclass, field
from threading import RLock, Timer

from zeroarm_desktop.domain.errors import TransportDisconnected
from zeroarm_desktop.transport.base import (
    CallbackRegistry,
    LinkState,
    LinkStateEvent,
    Subscription,
    TransportStatistics,
    WritePriority,
)
from zeroarm_desktop.transport.mock_device import MockDevice, MockDeviceSettings, MockFaults


@dataclass(frozen=True, slots=True)
class MockSettings:
    seed: int = 0
    faults: MockFaults = field(default_factory=MockFaults)
    startup_limits_active: bool = True
    auto_home_idle_ms: int = 20_000
    home_fails: bool = False
    response_delay_ms: int = 0

    def device_settings(self) -> MockDeviceSettings:
        return MockDeviceSettings(
            startup_limits_active=self.startup_limits_active,
            auto_home_idle_ms=self.auto_home_idle_ms,
            home_fails=self.home_fails,
        )


class MockTransport:
    """A deterministic Transport implementation for tests and demos."""

    def __init__(self, settings: MockSettings | None = None) -> None:
        self.settings = settings or MockSettings()
        self._device = MockDevice(
            faults=self.settings.faults, settings=self.settings.device_settings()
        )
        self._state = LinkState.CLOSED
        self._statistics = TransportStatistics()
        self._bytes_callbacks = CallbackRegistry()
        self._state_callbacks = CallbackRegistry()
        self._lock = RLock()
        self._response_timers: list[Timer] = []

    @property
    def device(self) -> MockDevice:
        """Expose the device for deterministic fault and clock injection."""
        return self._device

    @property
    def state(self) -> LinkState:
        with self._lock:
            return self._state

    @property
    def statistics(self) -> TransportStatistics:
        with self._lock:
            return self._statistics

    def open(self) -> None:
        with self._lock:
            if self._state is LinkState.OPEN:
                return
        self._set_state(LinkState.OPENING)
        self._set_state(LinkState.OPEN)

    def close(self, timeout_s: float = 2.0) -> None:
        del timeout_s
        with self._lock:
            if self._state is LinkState.CLOSED:
                return
            timers = tuple(self._response_timers)
            self._response_timers.clear()
        for timer in timers:
            timer.cancel()
        self._set_state(LinkState.CLOSING)
        self._set_state(LinkState.CLOSED)

    def write(
        self, data: bytes, *, priority: WritePriority = WritePriority.NORMAL
    ) -> None:
        del priority
        if not isinstance(data, bytes):
            raise TypeError("transport data must be bytes")
        owned = bytes(data)
        with self._lock:
            if self._state is not LinkState.OPEN:
                raise TransportDisconnected("mock transport is not open")
            current = self._statistics
            self._statistics = TransportStatistics(
                bytes_rx=current.bytes_rx,
                bytes_tx=current.bytes_tx + len(owned),
                writes_accepted=current.writes_accepted + 1,
                queue_rejections=current.queue_rejections,
                disconnects=current.disconnects,
            )
        for response in self._device.receive(owned):
            if self.settings.response_delay_ms > 0:
                timer = Timer(
                    self.settings.response_delay_ms / 1_000,
                    self._publish_response,
                    args=(response,),
                )
                timer.daemon = True
                with self._lock:
                    self._response_timers.append(timer)
                timer.start()
            else:
                self._publish_response(response)

    def subscribe_bytes(self, callback: Callable[[bytes], None]) -> Subscription:
        return self._bytes_callbacks.subscribe(callback)

    def subscribe_state(self, callback: Callable[[LinkStateEvent], None]) -> Subscription:
        return self._state_callbacks.subscribe(callback)

    def _set_state(self, state: LinkState) -> None:
        with self._lock:
            previous = self._state
            self._state = state
        self._state_callbacks.publish(LinkStateEvent(previous, state))

    def _publish_response(self, response: bytes) -> None:
        with self._lock:
            if self._state is not LinkState.OPEN:
                return
            current = self._statistics
            self._statistics = TransportStatistics(
                bytes_rx=current.bytes_rx + len(response),
                bytes_tx=current.bytes_tx,
                writes_accepted=current.writes_accepted,
                queue_rejections=current.queue_rejections,
                disconnects=current.disconnects,
            )
        self._bytes_callbacks.publish(response)
