"""Joint mapping and URDF forward kinematics golden tests."""

import math
from pathlib import Path

from hypothesis import given
from hypothesis import strategies as st

from zeroarm_desktop.model3d.fk import UrdfForwardKinematics
from zeroarm_desktop.model3d.joint_mapping import JointModelMapping

URDF = (
    Path(__file__).parents[2]
    / "resources/robot_model/URDF_XG_Robot_Arm_Urdf_V1_1/urdf"
    / "URDF_XG_Robot_Arm_Urdf_V1_1.urdf"
)


@given(
    values=st.tuples(
        st.integers(0, 6_283_079),
        st.integers(1_570_770, 3_141_539),
        st.integers(-1_570_770, 1_570_769),
        st.integers(-1_570_770, 1_570_769),
        st.integers(0, 1_570_769),
        st.integers(0, 6_283_079),
    )
)
def test_mapping_roundtrip(values: tuple[int, int, int, int, int, int]) -> None:
    mapping = JointModelMapping()
    reconstructed = mapping.model_to_robot_urad(mapping.robot_to_model_rad(values))
    assert all(abs(left - right) <= 1 for left, right in zip(values, reconstructed, strict=True))


def test_mapping_matches_mcu_and_urdf_ranges() -> None:
    mapping = JointModelMapping()
    model = mapping.robot_to_model_rad((0, 1_570_770, -1_570_770, 0, 0, 0))
    assert math.isclose(model[1], -math.pi / 2, abs_tol=3e-5)
    assert math.isclose(model[2], 0.0, abs_tol=3e-5)
    assert math.isclose(model[4], -math.pi / 2, abs_tol=3e-5)
    assert not any(entry.hardware_verified for entry in mapping.entries)


def test_urdf_model_zero_pose_matches_reference_golden() -> None:
    fk = UrdfForwardKinematics(URDF)
    robot_for_model_zero = (
        0,
        round(math.pi * 1_000_000),
        round(-math.pi / 2 * 1_000_000),
        0,
        round(math.pi / 2 * 1_000_000),
        0,
    )
    result = fk.forward(robot_for_model_zero)
    expected = (0.0, -0.172631, 0.1815)
    assert len(result.links) == 7
    assert tuple(item.link_name for item in result.links) == (
        "base_link",
        "link1",
        "link2",
        "link3",
        "link4",
        "link5",
        "ee_link",
    )
    assert all(
        math.isclose(actual, target, abs_tol=5e-6)
        for actual, target in zip(result.position_m, expected, strict=True)
    )


def test_modified_dh_zero_equivalent_pose() -> None:
    fk = UrdfForwardKinematics(URDF)
    robot = (
        round(-math.pi / 2 * 1_000_000) % round(math.tau * 1_000_000),
        round(math.pi / 2 * 1_000_000),
        0,
        0,
        0,
        0,
    )
    position = fk.forward(robot).position_m
    expected = (0.247631, 0.0, 0.4755)
    assert all(
        math.isclose(actual, target, abs_tol=6e-6)
        for actual, target in zip(position, expected, strict=True)
    )


def test_each_single_joint_changes_link_chain_continuously() -> None:
    fk = UrdfForwardKinematics(URDF)
    base = (0, 3_141_539, -1_570_770, 0, 1_570_770, 0)
    zero = fk.forward(base)
    for axis in range(6):
        changed = list(base)
        changed[axis] += 1000
        result = fk.forward(tuple(changed))  # type: ignore[arg-type]
        assert result.end_effector != zero.end_effector
