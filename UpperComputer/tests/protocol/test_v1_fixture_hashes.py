"""Every registered fixture must parse and match its frozen SHA-256."""

import hashlib

import pytest

from zeroarm_desktop.protocol.fixtures import (
    FIXTURE_SHA256,
    FrameFixture,
    all_fixtures,
)
from zeroarm_desktop.protocol.frame_codec import FrameCodec, FrameError


def test_v1_fixture__registry_covers_every_fixture() -> None:
    ids = {fixture.fixture_id for fixture in all_fixtures()}
    assert ids == set(FIXTURE_SHA256)


def test_v1_fixture__hashes_are_stable_and_registered() -> None:
    for fixture in all_fixtures():
        digest = hashlib.sha256(fixture.raw).hexdigest()
        assert FIXTURE_SHA256[fixture.fixture_id] == digest


@pytest.mark.parametrize(
    "fixture",
    all_fixtures(),
    ids=lambda fixture: fixture.fixture_id,
)
def test_v1_fixture__all_valid_frames_parse(fixture: FrameFixture) -> None:
    """Golden frames that are valid MCU frames must decode through FrameCodec."""
    if fixture.fixture_id in {"V1-LEN-ZERO", "V1-LEN-128"}:
        pytest.skip("invalid length boundary frames are rejected by design")
    if fixture.fixture_id in {"V1-BAD-CRC", "V1-BAD-ETX"}:
        pytest.skip("corrupted frames are rejected by design")

    frame = FrameCodec().decode_complete(fixture.raw)
    assert frame.raw == fixture.raw


@pytest.mark.parametrize(
    "fixture_id",
    ["V1-LEN-ZERO", "V1-LEN-128", "V1-BAD-CRC", "V1-BAD-ETX"],
)
def test_v1_fixture__invalid_frames_are_rejected(fixture_id: str) -> None:
    fixture = next(item for item in all_fixtures() if item.fixture_id == fixture_id)
    with pytest.raises(FrameError):
        FrameCodec().decode_complete(fixture.raw)


def test_v1_fixture__state_and_bench_lengths() -> None:
    for fixture in all_fixtures():
        if fixture.fixture_id.startswith("V1-STATE-"):
            assert len(fixture.raw) == 65, fixture.fixture_id
        if fixture.fixture_id == "V1-BENCH-QUERY-RSP-MOTOR1":
            assert len(fixture.raw) == 45, fixture.fixture_id
        if fixture.fixture_id == "V1-TARGET-MIXED-SIGNS":
            assert len(fixture.raw) == 33, fixture.fixture_id
