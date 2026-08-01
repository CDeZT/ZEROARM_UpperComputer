"""Packaged and source resource path resolution tests."""

from pathlib import Path

from pytest import MonkeyPatch

from zeroarm_desktop.infrastructure.paths import (
    application_root,
    default_data_root,
    resource_root,
    robot_model_root,
)


def test_data_root_honors_explicit_environment_override(
    tmp_path: Path, monkeypatch: MonkeyPatch
) -> None:
    expected = tmp_path / "isolated-data"
    monkeypatch.setenv("ZEROARM_DATA_ROOT", str(expected))

    assert default_data_root() == expected
    assert expected.is_dir()


def test_source_tree_resource_paths_resolve() -> None:
    root = application_root()
    assert (root / "pyproject.toml").is_file() or (root / "src").is_dir()
    assert resource_root() == root / "resources"
    model_root = robot_model_root()
    assert model_root == root / "resources" / "robot_model"
    assert (model_root / "manifest.json").is_file()


def test_robot_model_contains_expected_runtime_assets() -> None:
    model_root = robot_model_root()
    urdf = model_root / "URDF_XG_Robot_Arm_Urdf_V1_1" / "urdf" / "URDF_XG_Robot_Arm_Urdf_V1_1.urdf"
    assert urdf.is_file()
    meshes = model_root / "URDF_XG_Robot_Arm_Urdf_V1_1" / "meshes"
    assert len(list(meshes.glob("*.STL"))) == 7
