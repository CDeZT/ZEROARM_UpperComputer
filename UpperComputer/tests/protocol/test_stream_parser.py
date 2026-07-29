"""Incremental, recovery, and boundedness tests for the V1 stream parser."""

from itertools import pairwise
from random import Random

from hypothesis import given
from hypothesis import strategies as st

from zeroarm_desktop.protocol.fixtures import (
    V1_BAD_CRC,
    V1_BAD_ETX,
    V1_HELLO_REQUEST,
    V1_HELLO_RESPONSE,
    V1_LEN_128,
    V1_LEN_ZERO,
    V1_RESULT_OK_CMD02,
)
from zeroarm_desktop.protocol.frame_codec import MAX_CONTENT_LENGTH, FrameCodec
from zeroarm_desktop.protocol.stream_parser import StreamParser


def _feed_chunks(parser: StreamParser, chunks: list[bytes]) -> list[bytes]:
    frames = []
    for index, chunk in enumerate(chunks):
        frames.extend(parser.feed(chunk, received_monotonic_ns=index + 1))
    return [frame.raw for frame in frames]


def test_stream_parser_accepts_split_and_concatenated_frames() -> None:
    parser = StreamParser()
    stream = V1_HELLO_REQUEST.raw + V1_HELLO_RESPONSE.raw + V1_RESULT_OK_CMD02.raw
    chunks = [stream[:1], stream[1:4], stream[4:9], stream[9:]]

    assert _feed_chunks(parser, chunks) == [
        V1_HELLO_REQUEST.raw,
        V1_HELLO_RESPONSE.raw,
        V1_RESULT_OK_CMD02.raw,
    ]
    assert parser.statistics.frames_received == 3
    assert parser.buffered_bytes == 0


def test_stream_parser_ignores_noise_and_preserves_chunk_timestamp() -> None:
    parser = StreamParser()

    frames = parser.feed(b"\x01\x02\x03" + V1_HELLO_REQUEST.raw, received_monotonic_ns=99)

    assert len(frames) == 1
    assert frames[0].received_monotonic_ns == 99
    assert parser.statistics.noise_bytes == 3


def test_stream_parser_classifies_errors_and_recovers() -> None:
    parser = StreamParser()
    stream = (
        V1_LEN_ZERO.raw + V1_LEN_128.raw + V1_BAD_CRC.raw + V1_BAD_ETX.raw + V1_HELLO_REQUEST.raw
    )

    frames = parser.feed(stream, received_monotonic_ns=1)

    assert [frame.raw for frame in frames] == [V1_HELLO_REQUEST.raw]
    assert parser.statistics.length_errors == 2
    assert parser.statistics.crc_errors == 1
    assert parser.statistics.etx_errors == 1


def test_stream_parser_reset_discards_partial_frame_only() -> None:
    parser = StreamParser()
    parser.feed(V1_HELLO_RESPONSE.raw[:7], received_monotonic_ns=1)
    assert parser.buffered_bytes > 0

    parser.reset()
    frames = parser.feed(V1_HELLO_REQUEST.raw, received_monotonic_ns=2)

    assert [frame.raw for frame in frames] == [V1_HELLO_REQUEST.raw]
    assert parser.statistics.bytes_received == 7 + len(V1_HELLO_REQUEST.raw)


@given(
    command=st.integers(min_value=0, max_value=0xFF),
    payload=st.binary(max_size=123),
    split_points=st.lists(st.integers(min_value=0, max_value=128), max_size=20),
)
def test_protocol_property__random_chunking_matches_complete_feed(
    command: int,
    payload: bytes,
    split_points: list[int],
) -> None:
    raw = FrameCodec().encode(command, payload)
    points = sorted({0, len(raw), *(min(point, len(raw)) for point in split_points)})
    chunks = [raw[start:end] for start, end in pairwise(points)]

    assert _feed_chunks(StreamParser(), chunks) == [raw]


@given(data=st.binary(max_size=4096))
def test_protocol_property__arbitrary_bytes_remain_bounded(data: bytes) -> None:
    parser = StreamParser()

    parser.feed(data, received_monotonic_ns=0)

    assert parser.buffered_bytes <= MAX_CONTENT_LENGTH
    assert parser.statistics.bytes_received == len(data)


def test_stream_parser_handles_one_million_random_bytes_without_growth() -> None:
    parser = StreamParser()
    random_bytes = Random(0).randbytes(1_000_000)

    parser.feed(random_bytes, received_monotonic_ns=0)

    assert parser.buffered_bytes <= MAX_CONTENT_LENGTH
    assert parser.statistics.bytes_received == 1_000_000
