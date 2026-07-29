"""Runtime robot asset manifest, URDF validation, and package URI resolution."""

import hashlib
import json
import struct
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from pathlib import Path, PurePosixPath


@dataclass(frozen=True, slots=True)
class MeshInspection:
    triangle_count: int
    bounds_min: tuple[float, float, float]
    bounds_max: tuple[float, float, float]


@dataclass(frozen=True, slots=True)
class AssetFile:
    path: str
    sha256: str
    size: int


@dataclass(frozen=True, slots=True)
class RobotAssetManifest:
    schema_version: int
    package_name: str
    urdf: str
    source_revision: str
    license: str
    files: tuple[AssetFile, ...]


@dataclass(frozen=True, slots=True)
class UrdfInspection:
    robot_name: str
    links: tuple[str, ...]
    joints: tuple[str, ...]
    root_link: str
    mesh_uris: tuple[str, ...]


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        while chunk := stream.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def inspect_binary_stl(path: Path) -> MeshInspection:
    data = path.read_bytes()
    if len(data) < 84:
        raise ValueError(f"STL is too short: {path.name}")
    triangle_count = struct.unpack_from("<I", data, 80)[0]
    if triangle_count == 0 or len(data) != 84 + triangle_count * 50:
        raise ValueError(f"STL has invalid binary triangle data: {path.name}")
    minimum = [float("inf")] * 3
    maximum = [float("-inf")] * 3
    for triangle in range(triangle_count):
        offset = 84 + triangle * 50 + 12
        vertices = struct.unpack_from("<9f", data, offset)
        for coordinate in range(3):
            values = vertices[coordinate::3]
            minimum[coordinate] = min(minimum[coordinate], *values)
            maximum[coordinate] = max(maximum[coordinate], *values)
    return MeshInspection(triangle_count, tuple(minimum), tuple(maximum))  # type: ignore[arg-type]


def inspect_urdf(path: Path) -> UrdfInspection:
    root = ET.parse(path).getroot()
    if root.tag != "robot" or not root.attrib.get("name"):
        raise ValueError("URDF root must be a named robot")
    links = tuple(element.attrib["name"] for element in root.findall("link"))
    joints = tuple(element.attrib["name"] for element in root.findall("joint"))
    children = {
        child.attrib["link"]
        for joint in root.findall("joint")
        if (child := joint.find("child")) is not None
    }
    roots = set(links) - children
    if len(roots) != 1 or len(set(links)) != len(links) or len(set(joints)) != len(joints):
        raise ValueError("URDF must have one root and unique link/joint names")
    if len(joints) != len(links) - 1:
        raise ValueError("URDF joint graph must be a connected tree")
    mesh_uris = tuple(
        mesh.attrib["filename"] for mesh in root.findall(".//mesh") if "filename" in mesh.attrib
    )
    return UrdfInspection(root.attrib["name"], links, joints, roots.pop(), mesh_uris)


def resolve_package_uri(uri: str, asset_root: Path) -> Path:
    prefix = "package://"
    if not uri.startswith(prefix):
        raise ValueError("only package:// robot asset URIs are supported")
    relative = PurePosixPath(uri.removeprefix(prefix))
    if relative.is_absolute() or ".." in relative.parts or len(relative.parts) < 2:
        raise ValueError("package URI must remain inside the asset root")
    resolved = asset_root.joinpath(*relative.parts).resolve()
    root = asset_root.resolve()
    if not resolved.is_relative_to(root):
        raise ValueError("package URI escaped the asset root")
    return resolved


def load_robot_asset_manifest(asset_root: Path) -> RobotAssetManifest:
    raw = json.loads((asset_root / "manifest.json").read_text(encoding="utf-8"))
    files = tuple(AssetFile(**item) for item in raw["files"])
    return RobotAssetManifest(
        schema_version=raw["schema_version"],
        package_name=raw["package_name"],
        urdf=raw["urdf"],
        source_revision=raw["source_revision"],
        license=raw["license"],
        files=files,
    )


def verify_runtime_assets(asset_root: Path) -> RobotAssetManifest:
    manifest = load_robot_asset_manifest(asset_root)
    if manifest.schema_version != 1:
        raise ValueError("unsupported robot asset manifest schema")
    for item in manifest.files:
        path = asset_root / item.path
        if (
            not path.is_file()
            or path.stat().st_size != item.size
            or sha256_file(path) != item.sha256
        ):
            raise ValueError(f"robot asset failed integrity verification: {item.path}")
    urdf = asset_root / manifest.urdf
    inspection = inspect_urdf(urdf)
    if len(inspection.links) != 7 or len(inspection.joints) != 6:
        raise ValueError("ZeroArm runtime URDF must contain 7 links and 6 joints")
    resolved_meshes = {resolve_package_uri(uri, asset_root) for uri in inspection.mesh_uris}
    if len(resolved_meshes) != 7:
        raise ValueError("ZeroArm runtime URDF must reference exactly 7 meshes")
    for mesh in resolved_meshes:
        inspect_binary_stl(mesh)
    return manifest
