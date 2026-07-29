"""Headless 3D mesh, actual/ghost scene, and bounded tail tests."""

from datetime import UTC, datetime
from pathlib import Path

from zeroarm_desktop.domain.models import RobotSnapshot
from zeroarm_desktop.model3d.fk import UrdfForwardKinematics
from zeroarm_desktop.model3d.mesh import load_binary_stl
from zeroarm_desktop.model3d.scene import RobotSceneBuilder

ROOT = Path(__file__).parents[2] / "resources/robot_model"
URDF = ROOT / "URDF_XG_Robot_Arm_Urdf_V1_1/urdf/URDF_XG_Robot_Arm_Urdf_V1_1.urdf"


def _snapshot(generation: int) -> RobotSnapshot:
    joints = (0, 3_141_539, -1_570_770, 0, 1_570_770, 0)
    return RobotSnapshot(
        generation,
        generation,
        datetime.now(UTC),
        None,
        None,
        1,
        joints,
        joints,
        0,
        0,
        0,
        None,
        None,
        0,
        None,
        None,
    )


def test_headless_scene_contains_actual_and_ghost_links() -> None:
    builder = RobotSceneBuilder(UrdfForwardKinematics(URDF))
    scene = builder.build(_snapshot(1), ghost_target=(0, 3_141_539, 0, 0, 1_570_770, 0))
    assert len(scene.actual_links) == 7
    assert len(scene.ghost_links) == 7
    assert scene.actual_links[0].rgba[-1] == 1.0
    assert scene.ghost_links[0].rgba[-1] < 0.5
    assert not scene.hardware_mapping_verified


def test_trajectory_tail_is_bounded() -> None:
    builder = RobotSceneBuilder(UrdfForwardKinematics(URDF), tail_capacity=10)
    for generation in range(50):
        builder.build(_snapshot(generation))
    assert len(builder.build(_snapshot(51)).trajectory_tail) == 10


def test_numpy_loader_reads_all_runtime_meshes() -> None:
    mesh_root = ROOT / "URDF_XG_Robot_Arm_Urdf_V1_1/meshes"
    geometries = [load_binary_stl(path, link_name=path.stem) for path in mesh_root.glob("*.STL")]
    assert len(geometries) == 7
    assert sum(len(item.triangles) for item in geometries) == 371_786
    assert all(item.triangles.dtype.name == "float32" for item in geometries)
