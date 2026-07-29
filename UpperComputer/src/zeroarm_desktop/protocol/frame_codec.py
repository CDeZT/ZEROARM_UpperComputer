"""Encoder and complete-frame validator for the MCU V1 envelope."""

from dataclasses import dataclass

from zeroarm_desktop.protocol.crc8 import crc8_dallas_maxim

STX = 0xAA
ETX = 0x55
MCU_BUFFER_SIZE = 128
MIN_CONTENT_LENGTH = 1
MAX_CONTENT_LENGTH = MCU_BUFFER_SIZE - 1
MAX_ENCODED_PAYLOAD_LENGTH = MCU_BUFFER_SIZE - 5


class FrameError(ValueError):
    """Base class for classified V1 frame validation failures."""


class FrameLengthError(FrameError):
    """The frame or declared content length is invalid."""


class FrameCrcError(FrameError):
    """The received CRC does not match the frame content."""


class FrameBoundaryError(FrameError):
    """The STX or ETX boundary byte is invalid."""


@dataclass(frozen=True, slots=True)
class ProtocolFrame:
    """A validated immutable protocol frame."""

    command: int
    payload: bytes
    raw: bytes
    received_monotonic_ns: int


class FrameCodec:
    """Encode and validate complete MCU V1 frames."""

    def encode(self, command: int, payload: bytes = b"") -> bytes:
        if not 0 <= command <= 0xFF:
            raise ValueError("command must fit in one byte")
        if not isinstance(payload, bytes):
            raise TypeError("payload must be bytes")
        if len(payload) > MAX_ENCODED_PAYLOAD_LENGTH:
            raise FrameLengthError(
                f"payload exceeds MCU TX limit of {MAX_ENCODED_PAYLOAD_LENGTH} bytes"
            )

        content = bytes((command,)) + payload
        return bytes((STX, len(content))) + content + bytes((crc8_dallas_maxim(content), ETX))

    def decode_complete(
        self,
        raw: bytes,
        *,
        received_monotonic_ns: int = 0,
    ) -> ProtocolFrame:
        if not isinstance(raw, bytes):
            raise TypeError("raw frame must be bytes")
        if len(raw) < 5:
            raise FrameLengthError("frame is shorter than the V1 minimum")
        if raw[0] != STX:
            raise FrameBoundaryError("invalid STX")

        content_length = raw[1]
        if not MIN_CONTENT_LENGTH <= content_length <= MAX_CONTENT_LENGTH:
            raise FrameLengthError("declared content length is outside the MCU RX bounds")
        if len(raw) != content_length + 4:
            raise FrameLengthError("frame size does not match its declared content length")
        if raw[-1] != ETX:
            raise FrameBoundaryError("invalid ETX")

        content = raw[2:-2]
        if raw[-2] != crc8_dallas_maxim(content):
            raise FrameCrcError("CRC does not match command and payload")

        return ProtocolFrame(
            command=content[0],
            payload=content[1:],
            raw=raw,
            received_monotonic_ns=received_monotonic_ns,
        )
