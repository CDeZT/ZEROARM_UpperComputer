"""Bounded incremental parser for the MCU V1 byte stream."""

from dataclasses import dataclass
from enum import Enum, auto

from zeroarm_desktop.protocol.crc8 import crc8_dallas_maxim
from zeroarm_desktop.protocol.frame_codec import (
    ETX,
    MAX_CONTENT_LENGTH,
    MIN_CONTENT_LENGTH,
    STX,
    ProtocolFrame,
)


@dataclass(frozen=True, slots=True)
class ParserStatistics:
    bytes_received: int = 0
    frames_received: int = 0
    noise_bytes: int = 0
    length_errors: int = 0
    crc_errors: int = 0
    etx_errors: int = 0


class _State(Enum):
    WAIT_STX = auto()
    WAIT_LENGTH = auto()
    WAIT_CONTENT = auto()
    WAIT_CRC = auto()
    WAIT_ETX = auto()


class StreamParser:
    """Consume arbitrary chunks while retaining at most one bounded frame."""

    def __init__(self) -> None:
        self._statistics = ParserStatistics()
        self.reset()

    @property
    def statistics(self) -> ParserStatistics:
        return self._statistics

    @property
    def buffered_bytes(self) -> int:
        return len(self._content)

    def reset(self) -> None:
        """Discard a partial frame without clearing lifetime statistics."""
        self._state = _State.WAIT_STX
        self._declared_length = 0
        self._content = bytearray()
        self._received_crc = 0

    def feed(self, chunk: bytes, *, received_monotonic_ns: int) -> list[ProtocolFrame]:
        if not isinstance(chunk, bytes):
            raise TypeError("chunk must be bytes")
        if received_monotonic_ns < 0:
            raise ValueError("received_monotonic_ns must not be negative")

        frames: list[ProtocolFrame] = []
        for value in chunk:
            self._increment(bytes_received=1)

            if self._state is _State.WAIT_STX:
                if value == STX:
                    self._state = _State.WAIT_LENGTH
                else:
                    self._increment(noise_bytes=1)
                continue

            if self._state is _State.WAIT_LENGTH:
                if not MIN_CONTENT_LENGTH <= value <= MAX_CONTENT_LENGTH:
                    self._increment(length_errors=1)
                    self.reset()
                else:
                    self._declared_length = value
                    self._content.clear()
                    self._state = _State.WAIT_CONTENT
                continue

            if self._state is _State.WAIT_CONTENT:
                self._content.append(value)
                if len(self._content) == self._declared_length:
                    self._state = _State.WAIT_CRC
                continue

            if self._state is _State.WAIT_CRC:
                self._received_crc = value
                if value != crc8_dallas_maxim(self._content):
                    self._increment(crc_errors=1)
                    self.reset()
                else:
                    self._state = _State.WAIT_ETX
                continue

            if value != ETX:
                self._increment(etx_errors=1)
                self.reset()
                continue

            content = bytes(self._content)
            raw = bytes((STX, self._declared_length)) + content + bytes((self._received_crc, ETX))
            frames.append(
                ProtocolFrame(
                    command=content[0],
                    payload=content[1:],
                    raw=raw,
                    received_monotonic_ns=received_monotonic_ns,
                )
            )
            self._increment(frames_received=1)
            self.reset()

        return frames

    def _increment(
        self,
        *,
        bytes_received: int = 0,
        frames_received: int = 0,
        noise_bytes: int = 0,
        length_errors: int = 0,
        crc_errors: int = 0,
        etx_errors: int = 0,
    ) -> None:
        current = self._statistics
        self._statistics = ParserStatistics(
            bytes_received=current.bytes_received + bytes_received,
            frames_received=current.frames_received + frames_received,
            noise_bytes=current.noise_bytes + noise_bytes,
            length_errors=current.length_errors + length_errors,
            crc_errors=current.crc_errors + crc_errors,
            etx_errors=current.etx_errors + etx_errors,
        )
