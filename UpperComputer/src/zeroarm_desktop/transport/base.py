"""Transport contracts shared by Mock and Serial links."""

from collections.abc import Callable
from dataclasses import dataclass
from enum import Enum
from threading import RLock
from typing import Protocol

from zeroarm_desktop.domain.errors import TransportError


class LinkState(Enum):
    CLOSED = "closed"
    OPENING = "opening"
    OPEN = "open"
    CLOSING = "closing"
    FAILED = "failed"


class WritePriority(Enum):
    NORMAL = "normal"
    EMERGENCY = "emergency"


@dataclass(frozen=True, slots=True)
class LinkStateEvent:
    previous: LinkState
    current: LinkState
    error: TransportError | None = None


@dataclass(frozen=True, slots=True)
class TransportStatistics:
    bytes_rx: int = 0
    bytes_tx: int = 0
    writes_accepted: int = 0
    queue_rejections: int = 0
    disconnects: int = 0


class Subscription:
    """An idempotent callback registration handle."""

    def __init__(self, cancel_callback: Callable[[], None]) -> None:
        self._cancel_callback = cancel_callback
        self._cancelled = False
        self._lock = RLock()

    def cancel(self) -> None:
        with self._lock:
            if self._cancelled:
                return
            self._cancelled = True
            self._cancel_callback()


class Transport(Protocol):
    @property
    def state(self) -> LinkState: ...

    @property
    def statistics(self) -> TransportStatistics: ...

    def open(self) -> None: ...

    def close(self, timeout_s: float = 2.0) -> None: ...

    def write(
        self, data: bytes, *, priority: WritePriority = WritePriority.NORMAL
    ) -> None: ...

    def subscribe_bytes(self, callback: Callable[[bytes], None]) -> Subscription: ...

    def subscribe_state(self, callback: Callable[[LinkStateEvent], None]) -> Subscription: ...


class CallbackRegistry:
    """Thread-safe callback registry that never invokes callbacks under its lock."""

    def __init__(self) -> None:
        self._callbacks: dict[int, Callable[..., None]] = {}
        self._next_id = 0
        self._lock = RLock()

    def subscribe(self, callback: Callable[..., None]) -> Subscription:
        with self._lock:
            callback_id = self._next_id
            self._next_id += 1
            self._callbacks[callback_id] = callback
        return Subscription(lambda: self._remove(callback_id))

    def publish(self, *args: object) -> None:
        with self._lock:
            callbacks = tuple(self._callbacks.values())
        for callback in callbacks:
            callback(*args)

    def _remove(self, callback_id: int) -> None:
        with self._lock:
            self._callbacks.pop(callback_id, None)
