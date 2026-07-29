"""URDF tree parsing and deterministic six-axis forward kinematics."""

import math
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from pathlib import Path

from zeroarm_desktop.domain.models import JointVector
from zeroarm_desktop.model3d.joint_mapping import JointModelMapping

type Matrix4 = tuple[
    tuple[float, float, float, float],
    tuple[float, float, float, float],
    tuple[float, float, float, float],
    tuple[float, float, float, float],
]


@dataclass(frozen=True, slots=True)
class UrdfJoint:
    name: str
    parent: str
    child: str
    xyz: tuple[float, float, float]
    rpy: tuple[float, float, float]
    axis: tuple[float, float, float]


@dataclass(frozen=True, slots=True)
class LinkTransform:
    link_name: str
    world_from_link: Matrix4


@dataclass(frozen=True, slots=True)
class ForwardKinematicsResult:
    links: tuple[LinkTransform, ...]
    end_effector: Matrix4

    @property
    def position_m(self) -> tuple[float, float, float]:
        return (self.end_effector[0][3], self.end_effector[1][3], self.end_effector[2][3])


class UrdfForwardKinematics:
    def __init__(self, urdf_path: Path, mapping: JointModelMapping | None = None) -> None:
        self.mapping = mapping or JointModelMapping()
        self.root_link, self.joints = _parse_joint_chain(urdf_path)
        if tuple(joint.name for joint in self.joints) != tuple(
            entry.model_joint for entry in self.mapping.entries
        ):
            raise ValueError("URDF joint chain does not match JointModelMapping")

    def forward(self, joint_urad: JointVector) -> ForwardKinematicsResult:
        model_rad = self.mapping.robot_to_model_rad(joint_urad)
        world = identity_matrix()
        links = [LinkTransform(self.root_link, world)]
        for joint, angle in zip(self.joints, model_rad, strict=True):
            fixed = multiply(translation(*joint.xyz), rpy_rotation(*joint.rpy))
            moving = axis_angle(joint.axis, angle)
            world = multiply(world, multiply(fixed, moving))
            links.append(LinkTransform(joint.child, world))
        return ForwardKinematicsResult(tuple(links), world)


def identity_matrix() -> Matrix4:
    return (
        (1.0, 0.0, 0.0, 0.0),
        (0.0, 1.0, 0.0, 0.0),
        (0.0, 0.0, 1.0, 0.0),
        (0.0, 0.0, 0.0, 1.0),
    )


def multiply(left: Matrix4, right: Matrix4) -> Matrix4:
    rows = tuple(
        tuple(
            sum(left[row][index] * right[index][column] for index in range(4))
            for column in range(4)
        )
        for row in range(4)
    )
    return rows  # type: ignore[return-value]


def translation(x: float, y: float, z: float) -> Matrix4:
    return (
        (1.0, 0.0, 0.0, x),
        (0.0, 1.0, 0.0, y),
        (0.0, 0.0, 1.0, z),
        (0.0, 0.0, 0.0, 1.0),
    )


def rpy_rotation(roll: float, pitch: float, yaw: float) -> Matrix4:
    return multiply(rotation_z(yaw), multiply(rotation_y(pitch), rotation_x(roll)))


def axis_angle(axis: tuple[float, float, float], angle: float) -> Matrix4:
    x, y, z = axis
    length = math.sqrt(x * x + y * y + z * z)
    if length == 0:
        raise ValueError("joint axis must not be zero")
    x, y, z = x / length, y / length, z / length
    cosine, sine, one_minus = math.cos(angle), math.sin(angle), 1 - math.cos(angle)
    return (
        (
            cosine + x * x * one_minus,
            x * y * one_minus - z * sine,
            x * z * one_minus + y * sine,
            0.0,
        ),
        (
            y * x * one_minus + z * sine,
            cosine + y * y * one_minus,
            y * z * one_minus - x * sine,
            0.0,
        ),
        (
            z * x * one_minus - y * sine,
            z * y * one_minus + x * sine,
            cosine + z * z * one_minus,
            0.0,
        ),
        (0.0, 0.0, 0.0, 1.0),
    )


def rotation_x(angle: float) -> Matrix4:
    c, s = math.cos(angle), math.sin(angle)
    return ((1, 0, 0, 0), (0, c, -s, 0), (0, s, c, 0), (0, 0, 0, 1))


def rotation_y(angle: float) -> Matrix4:
    c, s = math.cos(angle), math.sin(angle)
    return ((c, 0, s, 0), (0, 1, 0, 0), (-s, 0, c, 0), (0, 0, 0, 1))


def rotation_z(angle: float) -> Matrix4:
    c, s = math.cos(angle), math.sin(angle)
    return ((c, -s, 0, 0), (s, c, 0, 0), (0, 0, 1, 0), (0, 0, 0, 1))


def _parse_joint_chain(path: Path) -> tuple[str, tuple[UrdfJoint, ...]]:
    root = ET.parse(path).getroot()
    joints = []
    children = set()
    for element in root.findall("joint"):
        parent_element = element.find("parent")
        child_element = element.find("child")
        if parent_element is None or child_element is None:
            raise ValueError("URDF joint must define parent and child")
        origin = element.find("origin")
        axis = element.find("axis")
        child = child_element.attrib["link"]
        children.add(child)
        joints.append(
            UrdfJoint(
                element.attrib["name"],
                parent_element.attrib["link"],
                child,
                _vector(origin.attrib.get("xyz", "0 0 0") if origin is not None else "0 0 0"),
                _vector(origin.attrib.get("rpy", "0 0 0") if origin is not None else "0 0 0"),
                _vector(axis.attrib.get("xyz", "1 0 0") if axis is not None else "1 0 0"),
            )
        )
    links = {element.attrib["name"] for element in root.findall("link")}
    roots = links - children
    if len(roots) != 1:
        raise ValueError("URDF must have one root")
    by_parent = {joint.parent: joint for joint in joints}
    ordered = []
    current = roots.pop()
    while current in by_parent:
        joint = by_parent[current]
        ordered.append(joint)
        current = joint.child
    if len(ordered) != len(joints):
        raise ValueError("URDF joint tree is not a single six-axis chain")
    return ordered[0].parent, tuple(ordered)


def _vector(text: str) -> tuple[float, float, float]:
    values = tuple(float(value) for value in text.split())
    if len(values) != 3:
        raise ValueError("URDF vector must contain three numbers")
    return values
