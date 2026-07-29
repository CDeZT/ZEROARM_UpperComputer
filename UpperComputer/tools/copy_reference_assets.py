"""Copy validated robot runtime assets from the read-only reference project."""

import argparse
import json
import shutil
from pathlib import Path

from zeroarm_desktop.model3d.assets import inspect_binary_stl, inspect_urdf, sha256_file

PACKAGE_NAME = "URDF_XG_Robot_Arm_Urdf_V1_1"
SOURCE_RELATIVE = Path("3. Simulink") / PACKAGE_NAME
MESH_NAMES = (
    "base_link.STL",
    "link1.STL",
    "link2.STL",
    "link3.STL",
    "link4.STL",
    "link5.STL",
    "ee_link.STL",
)


def copy_reference_assets(source_root: Path, destination_root: Path, source_revision: str) -> None:
    source_package = source_root / SOURCE_RELATIVE
    source_urdf = source_package / "urdf" / f"{PACKAGE_NAME}.urdf"
    source_license = source_root / "LICENSE"
    urdf = inspect_urdf(source_urdf)
    if len(urdf.links) != 7 or len(urdf.joints) != 6:
        raise ValueError("reference URDF does not contain the expected 7 links and 6 joints")
    for name in MESH_NAMES:
        inspect_binary_stl(source_package / "meshes" / name)

    package_destination = destination_root / PACKAGE_NAME
    (package_destination / "urdf").mkdir(parents=True, exist_ok=True)
    (package_destination / "meshes").mkdir(parents=True, exist_ok=True)
    (destination_root / "licenses").mkdir(parents=True, exist_ok=True)
    shutil.copy2(source_urdf, package_destination / "urdf" / source_urdf.name)
    for name in MESH_NAMES:
        shutil.copy2(source_package / "meshes" / name, package_destination / "meshes" / name)
    shutil.copy2(source_license, destination_root / "licenses" / "GPL-2.0.txt")

    runtime_files = [
        package_destination / "urdf" / source_urdf.name,
        *(package_destination / "meshes" / name for name in MESH_NAMES),
        destination_root / "licenses" / "GPL-2.0.txt",
    ]
    manifest = {
        "schema_version": 1,
        "package_name": PACKAGE_NAME,
        "urdf": f"{PACKAGE_NAME}/urdf/{source_urdf.name}",
        "source": "zero_arm_mcu/docx/Reference_project/zero-robotic-arm-master",
        "source_revision": source_revision,
        "license": "GPL-2.0",
        "files": [
            {
                "path": path.relative_to(destination_root).as_posix(),
                "sha256": sha256_file(path),
                "size": path.stat().st_size,
            }
            for path in sorted(runtime_files)
        ],
    }
    (destination_root / "manifest.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("source", type=Path)
    parser.add_argument("destination", type=Path)
    parser.add_argument("--source-revision", required=True)
    arguments = parser.parse_args()
    copy_reference_assets(arguments.source, arguments.destination, arguments.source_revision)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
