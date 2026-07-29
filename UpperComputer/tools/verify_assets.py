"""Verify packaged robot assets and print a concise inventory."""

import argparse
from pathlib import Path

from zeroarm_desktop.model3d.assets import inspect_binary_stl, inspect_urdf, verify_runtime_assets


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("asset_root", type=Path)
    arguments = parser.parse_args()
    manifest = verify_runtime_assets(arguments.asset_root)
    urdf = inspect_urdf(arguments.asset_root / manifest.urdf)
    meshes = {arguments.asset_root / uri.removeprefix("package://") for uri in urdf.mesh_uris}
    triangles = sum(inspect_binary_stl(mesh).triangle_count for mesh in meshes)
    print(
        f"verified {len(urdf.links)} links, {len(urdf.joints)} joints, "
        f"{len(meshes)} meshes, {triangles} triangles"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
