"""Serial worker lifecycle, cancellation, discovery, and partial-write tests."""

from dataclasses import dataclass
from queue import Empty, Queue
from threading import Event
from time import monotonic

import pytest

from zeroarm_desktop.domain.errors import TransportOpenError, TransportPermissionError
from zeroarm_desktop.transport.base import LinkState
from zeroarm_desktop.transport.discovery import discover_serial_ports
from zeroarm_desktop.transport.serial_transport import SerialSettings, SerialTransport


class FakeSerial:
    def __init__(self) -> None:
        self.incoming: Queue[bytes] = Queue()
        self.written = bytearray()
        self.cancelled = Event()
        self.closed = False
        self.partial_write_size: int | None = None

    def read(self, size: int) -> bytes:
        del size
        if self.cancelled.wait(0.005):
            return b""
        try:
            return self.incoming.get_nowait()
        except Empty:
            return b""

    def write(self, data: bytes) -> int:
        count = (
            len(data)
            if self.partial_write_size is None
            else min(self.partial_write_size, len(data))
        )
        self.written.extend(data[:count])
        return count

    def cancel_read(self) -> None:
        self.cancelled.set()

    def close(self) -> None:
        self.closed = True
        self.cancelled.set()


def _wait_until(predicate: object, timeout_s: float = 1.0) -> None:
    check = predicate  # Keep the assertion helper independent of Qt.
    deadline = monotonic() + timeout_s
    while monotonic() < deadline:
        if callable(check) and check():
            return
        Event().wait(0.005)
    raise AssertionError("condition was not met before timeout")


def test_transport_contract__serial_open_receive_write_and_close() -> None:
    fake = FakeSerial()
    transport = SerialTransport(SerialSettings("COM_TEST"), serial_factory=lambda _: fake)
    received: list[bytes] = []
    states: list[LinkState] = []
    transport.subscribe_bytes(received.append)
    transport.subscribe_state(lambda event: states.append(event.current))

    transport.open()
    fake.incoming.put(b"response")
    transport.write(b"request")
    _wait_until(lambda: received == [b"response"] and fake.written == b"request")
    transport.close()

    assert states == [LinkState.OPENING, LinkState.OPEN, LinkState.CLOSING, LinkState.CLOSED]
    assert fake.cancelled.is_set()
    assert fake.closed
    assert transport.statistics.bytes_rx == 8
    assert transport.statistics.bytes_tx == 7


def test_serial_transport_completes_partial_writes() -> None:
    fake = FakeSerial()
    fake.partial_write_size = 2
    transport = SerialTransport(SerialSettings("COM_TEST"), serial_factory=lambda _: fake)
    transport.open()
    transport.write(b"abcdefg")
    _wait_until(lambda: fake.written == b"abcdefg")
    transport.close()


@pytest.mark.parametrize(
    ("error", "expected"),
    [
        (PermissionError("denied"), TransportPermissionError),
        (OSError("missing"), TransportOpenError),
    ],
)
def test_serial_transport_classifies_open_failures(
    error: Exception,
    expected: type[Exception],
) -> None:
    def fail(_: SerialSettings) -> FakeSerial:
        raise error

    transport = SerialTransport(SerialSettings("COM_BAD"), serial_factory=fail)
    with pytest.raises(expected):
        transport.open()
    assert transport.state is LinkState.FAILED


@dataclass
class FakePort:
    device: str
    name: str | None = None
    description: str | None = None
    hwid: str | None = None
    vid: int | None = None
    pid: int | None = None
    serial_number: str | None = None
    manufacturer: str | None = None
    product: str | None = None
    location: str | None = None


def test_serial_discovery_preserves_metadata_and_sorts_ports() -> None:
    ports = discover_serial_ports(
        [
            FakePort("COM10", description="机械臂", vid=0x0483, pid=0x5740),
            FakePort("COM2", description="Debug"),
        ]
    )
    assert [port.device for port in ports] == ["COM10", "COM2"]
    assert ports[0].description == "机械臂"
    assert ports[0].vid == 0x0483
