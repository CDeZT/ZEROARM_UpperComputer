"""Golden vectors and boundaries for the pure V1 frame codec."""

import pytest
from hypothesis import given
from hypothesis import strategies as st

from zeroarm_desktop.protocol.crc8 import CRC8_DALLAS_MAXIM_CHECK, crc8_dallas_maxim
from zeroarm_desktop.protocol.fixtures import (
    V1_HELLO_REQUEST,
    V1_HELLO_RESPONSE,
    V1_RESULT_OK_CMD02,
)
from zeroarm_desktop.protocol.frame_codec import (
    MAX_ENCODED_PAYLOAD_LENGTH,
    FrameBoundaryError,
    FrameCodec,
    FrameCrcError,
    FrameLengthError,
)


def test_v1_fixture__crc_standard_check_vector() -> None:
    assert crc8_dallas_maxim(b"123456789") == CRC8_DALLAS_MAXIM_CHECK


def test_v1_fixture__hello_request_matches_mcu() -> None:
    codec = FrameCodec()

    assert codec.encode(0x00) == V1_HELLO_REQUEST.raw
    assert codec.decode_complete(V1_HELLO_REQUEST.raw).command == 0x00
    assert codec.decode_complete(V1_HELLO_REQUEST.raw).payload == b""


def test_v1_fixture__hello_response_matches_mcu() -> None:
    frame = FrameCodec().decode_complete(
        V1_HELLO_RESPONSE.raw,
        received_monotonic_ns=123,
    )

    assert frame.command == 0x00
    assert frame.payload == b"ZEROARM/1.0"
    assert frame.raw == V1_HELLO_RESPONSE.raw
    assert frame.received_monotonic_ns == 123


def test_v1_fixture__result_response_matches_mcu() -> None:
    assert FrameCodec().encode(0x02, b"\x00") == V1_RESULT_OK_CMD02.raw


@given(
    command=st.integers(min_value=0, max_value=0xFF),
    payload=st.binary(max_size=MAX_ENCODED_PAYLOAD_LENGTH),
)
def test_protocol_property__encoded_frames_round_trip(command: int, payload: bytes) -> None:
    codec = FrameCodec()

    decoded = codec.decode_complete(codec.encode(command, payload))

    assert decoded.command == command
    assert decoded.payload == payload


def test_frame_codec_rejects_invalid_encode_inputs() -> None:
    codec = FrameCodec()

    with pytest.raises(ValueError, match="command"):
        codec.encode(-1)
    with pytest.raises(ValueError, match="command"):
        codec.encode(256)
    with pytest.raises(TypeError, match="payload"):
        codec.encode(0, bytearray())  # type: ignore[arg-type]
    with pytest.raises(FrameLengthError, match="123"):
        codec.encode(0, bytes(MAX_ENCODED_PAYLOAD_LENGTH + 1))


@pytest.mark.parametrize(
    ("raw", "error_type"),
    [
        (b"", FrameLengthError),
        (bytes.fromhex("AB 01 00 00 55"), FrameBoundaryError),
        (bytes.fromhex("AA 00 00 55"), FrameLengthError),
        (bytes.fromhex("AA 80 00 00 55"), FrameLengthError),
        (bytes.fromhex("AA 02 00 00 55"), FrameLengthError),
        (bytes.fromhex("AA 01 00 01 55"), FrameCrcError),
        (bytes.fromhex("AA 01 00 00 54"), FrameBoundaryError),
    ],
)
def test_frame_codec_classifies_invalid_frames(
    raw: bytes,
    error_type: type[ValueError],
) -> None:
    with pytest.raises(error_type):
        FrameCodec().decode_complete(raw)


def test_frame_codec_requires_immutable_bytes() -> None:
    with pytest.raises(TypeError, match="raw frame"):
        FrameCodec().decode_complete(bytearray(V1_HELLO_REQUEST.raw))  # type: ignore[arg-type]
