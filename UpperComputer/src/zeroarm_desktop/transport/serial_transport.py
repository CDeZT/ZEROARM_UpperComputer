"""Cancellable pyserial byte transport with a bounded write queue."""

from collections import deque
from collections.abc import Callable
from contextlib import suppress
from dataclasses import dataclass
from threading import Event, RLock, Thread
from typing import Protocol

import serial

from zeroarm_desktop.domain.errors import (
    TransportDisconnected,
    TransportError,
    TransportOpenError,
    TransportPermissionError,
    TransportQueueFull,
)
from zeroarm_desktop.transport.base import (
    CallbackRegistry,
    LinkState,
    LinkStateEvent,
    Subscription,
    TransportStatistics,
    WritePriority,
)


@dataclass(frozen=True, slots=True)
class SerialSettings:
    port: str
    baudrate: int = 115200
    read_timeout_s: float = 0.05
    write_timeout_s: float = 0.5
    queue_capacity: int = 64
    read_chunk_size: int = 4096

    def __post_init__(self) -> None:
        if not self.port:
            raise ValueError("serial port must not be empty")
        if self.baudrate <= 0:
            raise ValueError("baudrate must be positive")
        if self.read_timeout_s <= 0 or self.write_timeout_s <= 0:
            raise ValueError("serial timeouts must be positive")
        if self.queue_capacity <= 0 or self.read_chunk_size <= 0:
            raise ValueError("serial queue and chunk sizes must be positive")


class SerialLike(Protocol):
    def read(self, size: int) -> bytes: ...

    def write(self, data: bytes) -> int | None: ...

    def cancel_read(self) -> None: ...

    def close(self) -> None: ...


SerialFactory = Callable[[SerialSettings], SerialLike]


def _default_serial_factory(settings: SerialSettings) -> SerialLike:
    return serial.Serial(
        port=settings.port,
        baudrate=settings.baudrate,
        timeout=settings.read_timeout_s,
        write_timeout=settings.write_timeout_s,
    )


class SerialTransport:
    def __init__(
        self,
        settings: SerialSettings,
        *,
        serial_factory: SerialFactory = _default_serial_factory,
    ) -> None:
        self.settings = settings
        self._serial_factory = serial_factory
        self._serial: SerialLike | None = None
        self._state = LinkState.CLOSED
        self._statistics = TransportStatistics()
        self._queue: deque[bytes] = deque()
        self._queue_lock = RLock()
        self._stop = Event()
        self._worker: Thread | None = None
        self._bytes_callbacks = CallbackRegistry()
        self._state_callbacks = CallbackRegistry()
        self._lock = RLock()

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
            if self._state is not LinkState.CLOSED:
                raise TransportOpenError(f"cannot open serial transport from {self._state.value}")
        self._set_state(LinkState.OPENING)
        try:
            port = self._serial_factory(self.settings)
        except PermissionError as error:
            permission_error = TransportPermissionError(str(error))
            self._set_state(LinkState.FAILED, permission_error)
            raise permission_error from error
        except (OSError, serial.SerialException) as error:
            open_error = TransportOpenError(str(error))
            self._set_state(LinkState.FAILED, open_error)
            raise open_error from error
        self._serial = port
        with self._queue_lock:
            self._queue.clear()
        self._stop.clear()
        self._worker = Thread(target=self._run, name="zeroarm-serial", daemon=True)
        self._worker.start()
        self._set_state(LinkState.OPEN)

    def close(self, timeout_s: float = 2.0) -> None:
        with self._lock:
            if self._state is LinkState.CLOSED:
                return
        self._set_state(LinkState.CLOSING)
        self._stop.set()
        port = self._serial
        if port is not None:
            with suppress(OSError, serial.SerialException):
                port.cancel_read()
        worker = self._worker
        if worker is not None:
            worker.join(timeout_s)
            if worker.is_alive():
                error = TransportError("serial worker did not stop before timeout")
                self._set_state(LinkState.FAILED, error)
                raise error
        self._close_port()
        self._set_state(LinkState.CLOSED)

    def write(self, data: bytes, *, priority: WritePriority = WritePriority.NORMAL) -> None:
        if not isinstance(data, bytes):
            raise TypeError("transport data must be bytes")
        if not isinstance(priority, WritePriority):
            raise TypeError("priority must be WritePriority")
        with self._lock:
            if self._state is not LinkState.OPEN:
                raise TransportDisconnected("serial transport is not open")
        with self._queue_lock:
            if priority is WritePriority.EMERGENCY:
                self._queue.clear()
                self._queue.appendleft(bytes(data))
            elif len(self._queue) >= self.settings.queue_capacity:
                self._increment(queue_rejections=1)
                raise TransportQueueFull("serial write queue is full")
            else:
                self._queue.append(bytes(data))
        self._increment(bytes_tx=len(data), writes_accepted=1)

    def subscribe_bytes(self, callback: Callable[[bytes], None]) -> Subscription:
        return self._bytes_callbacks.subscribe(callback)

    def subscribe_state(self, callback: Callable[[LinkStateEvent], None]) -> Subscription:
        return self._state_callbacks.subscribe(callback)

    def _run(self) -> None:
        try:
            while not self._stop.is_set():
                self._write_pending()
                port = self._serial
                if port is None:
                    return
                chunk = port.read(self.settings.read_chunk_size)
                if chunk:
                    owned = bytes(chunk)
                    self._increment(bytes_rx=len(owned))
                    self._bytes_callbacks.publish(owned)
        except (OSError, serial.SerialException) as error:
            if not self._stop.is_set():
                self._increment(disconnects=1)
                self._set_state(LinkState.FAILED, TransportDisconnected(str(error)))
        finally:
            self._close_port()

    def _write_pending(self) -> None:
        with self._queue_lock:
            if not self._queue:
                return
            data = self._queue.popleft()
        port = self._serial
        if port is None:
            raise TransportDisconnected("serial port is closed")
        offset = 0
        while offset < len(data):
            written = port.write(data[offset:])
            if written is None or written <= 0:
                raise TransportDisconnected("serial write made no progress")
            offset += written

    def _close_port(self) -> None:
        port, self._serial = self._serial, None
        if port is not None:
            with suppress(OSError, serial.SerialException):
                port.close()

    def _set_state(self, state: LinkState, error: TransportError | None = None) -> None:
        with self._lock:
            previous = self._state
            self._state = state
        self._state_callbacks.publish(LinkStateEvent(previous, state, error))

    def _increment(
        self,
        *,
        bytes_rx: int = 0,
        bytes_tx: int = 0,
        writes_accepted: int = 0,
        queue_rejections: int = 0,
        disconnects: int = 0,
    ) -> None:
        with self._lock:
            current = self._statistics
            self._statistics = TransportStatistics(
                bytes_rx=current.bytes_rx + bytes_rx,
                bytes_tx=current.bytes_tx + bytes_tx,
                writes_accepted=current.writes_accepted + writes_accepted,
                queue_rejections=current.queue_rejections + queue_rejections,
                disconnects=current.disconnects + disconnects,
            )
