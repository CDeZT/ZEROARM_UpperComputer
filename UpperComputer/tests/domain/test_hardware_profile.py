"""HardwareProfile, interlock policy, path validator, and readiness tests."""

from collections.abc import Sequence
from dataclasses import replace
from datetime import UTC, datetime
from typing import cast

import pytest
from hypothesis import given
from hypothesis import strategies as st

from zeroarm_desktop.domain.hardware_profile import (
    URAD_PER_DEGREE,
    HardwareProfile,
    InterlockPolicy,
    PathValidator,
    evaluate_readiness,
)
from zeroarm_desktop.domain.models import JointVector, RobotSnapshot
from zeroarm_desktop.protocol.v1_codec import V1FaultFlag

DEG = URAD_PER_DEGREE


def _snapshot(*, run_state: int = 1, fault: int = 0, homed: int | None = 0x1D) -> RobotSnapshot:
    zero = (0, 0, 0, 0, 0, 0)
    return RobotSnapshot(
        1,
        100,
        datetime.now(UTC),
        None,
        None,
        run_state,
        zero,
        zero,
        0,
        homed,
        0,
        None,
        None,
        fault,
        None,
        None,
    )


def test_profile__j2_and_j6_nonzero_targets_are_rejected() -> None:
    profile = HardwareProfile.default()
    assert profile.target_violations((0, 0, 0, 0, 0, 0)) == ()
    assert profile.target_violations((0, 1, 0, 0, 0, 0)) == ("unavailable_axis",)
    assert profile.target_violations((0, 0, 0, 0, 0, -1)) == ("unavailable_axis",)
    assert profile.target_violations((0, 1, 0, 0, 0, -1)) == (
        "unavailable_axis",
        "unavailable_axis",
    )


@given(any_j1=st.integers(-(2**31), 2**31 - 1))
def test_profile__j1_continuous_accepts_any_value(any_j1: int) -> None:
    profile = HardwareProfile.default()
    target = [0, 0, 0, 0, 0, 0]
    target[0] = any_j1
    assert profile.target_violations(cast(JointVector, tuple(target))) == ()


@pytest.mark.parametrize(
    "axis,lower,upper",
    [
        (2, 0, 135),
        (3, -90, 90),
        (4, -35, 135),
    ],
)
def test_profile__j3_j4_j5_boundaries_are_inclusive(axis: int, lower: int, upper: int) -> None:
    profile = HardwareProfile.default()
    for boundary in (lower * DEG, upper * DEG):
        target = [0] * 6
        target[axis] = boundary
        assert profile.target_violations(cast(JointVector, tuple(target))) == ()


@pytest.mark.parametrize(
    "axis,value",
    [(2, -1), (2, 136 * DEG), (3, -91 * DEG), (3, 91 * DEG), (4, -36 * DEG), (4, 136 * DEG)],
)
def test_profile__out_of_range_values_are_rejected(axis: int, value: int) -> None:
    target = [0] * 6
    target[axis] = value
    assert HardwareProfile.default().target_violations(cast(JointVector, tuple(target))) == (
        "joint_limit",
    )


def test_interlock__j4_motion_requires_j3_clear() -> None:
    policy = InterlockPolicy()
    zero = (0, 0, 0, 0, 0, 0)
    assert policy.target_violations((0, 0, 0, 10, 0, 0)) == ("j4_requires_j3_clear",)
    assert policy.target_violations((0, 0, 15 * DEG, 10, 0, 0)) == ("j4_requires_j3_clear",)
    assert policy.target_violations((0, 0, 15 * DEG + 1, 10, 0, 0)) == ()
    assert policy.target_violations((0, 0, 15 * DEG - 1, 10, 0, 0)) == ("j4_requires_j3_clear",)
    assert policy.transition_violations(zero, (0, 0, 0, 10, 0, 0)) == (
        "j4_requires_j3_clear",
        "j4_move_requires_j3_already_clear",
    )


def test_interlock__j5_upper_limit_scales_with_j3() -> None:
    policy = InterlockPolicy()
    zero = (0, 0, 0, 0, 0, 0)
    assert policy.target_violations((0, 0, 0, 0, 46 * DEG, 0)) == ("j5_midrange_requires_j3",)
    assert policy.target_violations((0, 0, 15 * DEG, 0, 46 * DEG, 0)) == (
        "j5_midrange_requires_j3",
    )
    assert policy.target_violations((0, 0, 15 * DEG + 1, 0, 46 * DEG, 0)) == ()
    assert policy.target_violations((0, 0, 45 * DEG + 1, 0, 61 * DEG, 0)) == ()
    assert policy.target_violations((0, 0, 45 * DEG + 1, 0, 135 * DEG, 0)) == ()
    assert policy.transition_violations(zero, (0, 0, 0, 0, 46 * DEG, 0)) == (
        "j5_midrange_requires_j3",
        "j5_midrange_requires_j3_already_clear",
    )


def test_interlock__lowering_j3_requires_centered_j4_and_retracted_j5() -> None:
    policy = InterlockPolicy()
    lowered = (0, 0, 10 * DEG, 0, 0, 0)
    extended_j4 = (0, 0, 10 * DEG, 20 * DEG, 0, 0)
    extended_j5 = (0, 0, 10 * DEG, 0, 46 * DEG, 0)
    assert "lower_j3_requires_j4_centered" in policy.transition_violations(extended_j4, lowered)
    assert "lower_j3_requires_j5_midrange" in policy.transition_violations(extended_j5, lowered)
    clean = (0, 0, 50 * DEG, 0, 60 * DEG, 0)
    assert "lower_j3_requires_j5_midrange" in policy.transition_violations(clean, lowered)


def test_path_validator__rejects_dangerous_midpoint_even_when_final_is_legal() -> None:
    validator = PathValidator()
    low_j3 = (0, 0, 10 * DEG, 0, 0, 0)
    raised_j3 = (0, 0, 50 * DEG, 0, 0, 0)
    high_j3_j5 = (0, 0, 50 * DEG, 0, 60 * DEG, 0)
    j5_extended = (0, 0, 50 * DEG, 0, 80 * DEG, 0)

    legal = validator.validate_path((low_j3, raised_j3, high_j3_j5, j5_extended))
    assert legal.valid
    dangerous_midpoint = (low_j3, j5_extended, high_j3_j5)
    result = validator.validate_path(dangerous_midpoint)
    assert not result.valid
    assert "j5_midrange_requires_j3_already_clear" in result.reasons()
    assert "j5_extended_requires_j3_already_clear" in result.reasons()


def test_path_validator__rejects_unavailable_axis_and_bad_points() -> None:
    validator = PathValidator()
    result = validator.validate_path(((0, 1, 0, 0, 0, 0),))
    assert not result.valid
    assert "unavailable_axis" in result.reasons()
    assert not validator.validate_path(cast(Sequence[JointVector], ((1, 2, 3),))).valid
    assert validator.validate_path(()).valid


def test_readiness__normal_and_fault_states() -> None:
    profile = HardwareProfile.default()
    ready = evaluate_readiness(_snapshot(), profile)
    assert ready.run_state_known
    assert ready.run_state_name == "READY"
    assert ready.motion_authorized
    assert not ready.reset_required
    assert ready.homed_complete

    startup = evaluate_readiness(_snapshot(run_state=5, fault=V1FaultFlag.STARTUP), profile)
    assert startup.run_state_name == "FAULT"
    assert startup.reset_required
    assert not startup.motion_authorized
    assert startup.fault_known == (V1FaultFlag.STARTUP,)

    estop = evaluate_readiness(_snapshot(run_state=5, fault=V1FaultFlag.ESTOP), profile)
    assert estop.reset_required
    assert estop.fault_known == (V1FaultFlag.ESTOP,)

    home = evaluate_readiness(_snapshot(run_state=2), profile)
    assert home.run_state_name == "HOMING"
    assert not home.motion_authorized


def test_readiness__unknown_run_state_and_unknown_fault_bits() -> None:
    report = evaluate_readiness(_snapshot(run_state=12345, fault=0x8000), HardwareProfile.default())
    assert not report.run_state_known
    assert report.run_state_name is None
    assert not report.motion_authorized
    assert report.fault_known == ()
    assert report.fault_unknown_bits == 0x8000


def test_readiness__homed_complete_requires_profile_mask() -> None:
    profile = HardwareProfile.default()
    assert evaluate_readiness(_snapshot(homed=0x1D), profile).homed_complete
    assert not evaluate_readiness(_snapshot(homed=0x04), profile).homed_complete
    assert not evaluate_readiness(_snapshot(homed=None), profile).homed_complete


def test_interlock__policy_defaults_are_ascending() -> None:
    assert InterlockPolicy().defaults_valid
    with pytest.raises(ValueError, match="ascending"):
        PathValidator(policy=replace(InterlockPolicy(), j3_min_for_j5_extended_urad=10))


def test_profile__single_source_of_truth() -> None:
    profile = HardwareProfile.default()
    assert profile.profile_id == "zeroarm_g474_v1_partial"
    assert profile.startup_limit_mask == 0x1D
    assert profile.home_mask == 0x1D
    assert profile.feedback_mask == 0x1F
    assert [c.available for c in profile.capabilities] == [True, False, True, True, True, False]
    assert [c.continuous for c in profile.capabilities] == [True, False, False, False, False, False]
    assert profile.capability(3).motor_id == 4
