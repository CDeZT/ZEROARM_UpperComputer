"""Robot asset URI, topology, integrity, and mesh geometry tests."""

from pathlib import Path

import pytest

from zeroarm_desktop.model3d.assets import (
    inspect_binary_stl,
    inspect_urdf,
    resolve_package_uri,
    verify_runtime_assets,
)

ASSET_ROOT = Path(__file__).parents[2] / "resources" / "robot_model"


def test_runtime_robot_assets_are_complete_and_verified() -> None:
    manifest = verify_runtime_assets(ASSET_ROOT)
    urdf = inspect_urdf(ASSET_ROOT / manifest.urdf)
    assert urdf.robot_name == "URDF_XG_Robot_Arm_Urdf_V1_1"
    assert urdf.root_link == "base_link"
    assert len(urdf.links) == 7
    assert len(urdf.joints) == 6
    assert len(set(urdf.mesh_uris)) == 7
    assert manifest.license == "GPL-2.0"
    assert not Path(manifest.urdf).is_absolute()


def test_all_seven_meshes_have_nonempty_geometry_and_sane_bounds() -> None:
    urdf = inspect_urdf(ASSET_ROOT / verify_runtime_assets(ASSET_ROOT).urdf)
    for uri in set(urdf.mesh_uris):
        mesh = inspect_binary_stl(resolve_package_uri(uri, ASSET_ROOT))
        assert mesh.triangle_count > 0
        extents = tuple(
            high - low for low, high in zip(mesh.bounds_min, mesh.bounds_max, strict=True)
        )
        assert all(0.001 < extent < 10.0 for extent in extents)


@pytest.mark.parametrize(
    "uri",
    ["file:///tmp/model.STL", "package://../secret", "package:///absolute"],
)
def test_package_uri_resolver_rejects_external_paths(uri: str) -> None:
    with pytest.raises(ValueError):
        resolve_package_uri(uri, ASSET_ROOT)


def test_manifest_contains_no_workspace_absolute_path() -> None:
    text = (ASSET_ROOT / "manifest.json").read_text(encoding="utf-8")
    assert "C:\\Users" not in text
    assert "C:/Users" not in text
