"""Numerical IK FK-backcheck, limits, and unreachable tests."""

from pathlib import Path
from typing import cast

from zeroarm_desktop.model3d.fk import Matrix4, UrdfForwardKinematics
from zeroarm_desktop.model3d.ik import NumericalIkSolver

URDF = (
    Path(__file__).parents[2]
    / "resources/robot_model/URDF_XG_Robot_Arm_Urdf_V1_1/urdf/URDF_XG_Robot_Arm_Urdf_V1_1.urdf"
)


def test_ik_roundtrip_known_pose() -> None:
    fk = UrdfForwardKinematics(URDF)
    joints = (0, 3_141_539, 523_590, 0, 1_570_770, 0)
    result = NumericalIkSolver(fk).solve(fk.forward(joints).end_effector, joints)
    assert result.solutions
    assert result.solutions[0].position_error_m <= 0.0002
    assert not fk.mapping.validate_robot_limits(result.solutions[0].joint_urad)


def test_ik_reports_outside_workspace() -> None:
    fk = UrdfForwardKinematics(URDF)
    joints = (0, 3_141_539, 523_590, 0, 1_570_770, 0)
    target = [list(row) for row in fk.forward(joints).end_effector]
    target[0][3] = 10
    result = NumericalIkSolver(fk).solve(
        cast(Matrix4, tuple(tuple(row) for row in target)),
        joints,
    )
    assert not result.solutions
    assert result.reason == "invalid_or_outside_workspace"
