"""Versioned Recipe schema, static validation, and pure step expansion."""

import json
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Literal

from zeroarm_desktop.domain.trajectory import Trajectory, TrajectoryPoint, validate_trajectory

type JsonValue = None | bool | int | float | str | list["JsonValue"] | dict[str, "JsonValue"]


@dataclass(frozen=True, slots=True)
class RecipeStep:
    kind: Literal["wait_ms", "set_joint_target", "play_trajectory"]
    wait_ms: int | None = None
    joint_urad: tuple[int, int, int, int, int, int] | None = None
    duration_ms: int | None = None
    trajectory_name: str | None = None


@dataclass(frozen=True, slots=True)
class Recipe:
    schema_version: int
    name: str
    steps: tuple[RecipeStep, ...]
    metadata: Mapping[str, JsonValue]


@dataclass(frozen=True, slots=True)
class RecipeIssue:
    code: str
    step_index: int | None = None


def validate_recipe(
    recipe: Recipe,
    *,
    available_trajectories: Mapping[str, Trajectory] | None = None,
) -> tuple[RecipeIssue, ...]:
    issues: list[RecipeIssue] = []
    if recipe.schema_version != 1:
        issues.append(RecipeIssue("schema_unsupported"))
    if not recipe.steps:
        issues.append(RecipeIssue("empty_recipe"))
    for index, step in enumerate(recipe.steps):
        if step.kind == "wait_ms":
            if step.wait_ms is None or step.wait_ms < 0:
                issues.append(RecipeIssue("wait_invalid", index))
        elif step.kind == "set_joint_target":
            if step.joint_urad is None or len(step.joint_urad) != 6:
                issues.append(RecipeIssue("joint_target_invalid", index))
            if step.duration_ms is None or not 1 <= step.duration_ms <= 0xFFFF:
                issues.append(RecipeIssue("duration_invalid", index))
        elif step.kind == "play_trajectory":
            if not step.trajectory_name:
                issues.append(RecipeIssue("trajectory_name_missing", index))
            elif available_trajectories is not None:
                trajectory = available_trajectories.get(step.trajectory_name)
                if trajectory is None:
                    issues.append(RecipeIssue("trajectory_missing", index))
                else:
                    report = validate_trajectory(trajectory)
                    if not report.valid:
                        issues.append(RecipeIssue("trajectory_invalid", index))
        else:
            issues.append(RecipeIssue("unknown_step", index))
    return tuple(issues)


def recipe_to_json(recipe: Recipe) -> str:
    document = {
        "schema_version": recipe.schema_version,
        "name": recipe.name,
        "metadata": dict(recipe.metadata),
        "steps": [
            {
                "kind": step.kind,
                "wait_ms": step.wait_ms,
                "joint_urad": list(step.joint_urad) if step.joint_urad else None,
                "duration_ms": step.duration_ms,
                "trajectory_name": step.trajectory_name,
            }
            for step in recipe.steps
        ],
    }
    return json.dumps(document, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def recipe_from_json(text: str) -> Recipe:
    raw = json.loads(text)
    if raw.get("schema_version") != 1 or not isinstance(raw.get("steps"), list):
        raise ValueError("unsupported or invalid recipe document")
    steps = []
    for item in raw["steps"]:
        joints = item.get("joint_urad")
        joint_tuple = tuple(joints) if joints is not None else None
        steps.append(
            RecipeStep(
                item["kind"],
                item.get("wait_ms"),
                joint_tuple,
                item.get("duration_ms"),
                item.get("trajectory_name"),
            )
        )
    return Recipe(1, raw["name"], tuple(steps), raw.get("metadata", {}))


def expand_recipe_to_points(
    recipe: Recipe,
    *,
    available_trajectories: Mapping[str, Trajectory] | None = None,
) -> tuple[TrajectoryPoint, ...]:
    issues = validate_recipe(recipe, available_trajectories=available_trajectories)
    if issues:
        raise ValueError("recipe validation failed: " + ",".join(issue.code for issue in issues))
    points: list[TrajectoryPoint] = []
    time_ns = 0
    last_joints = (0, 1_570_770, 0, 0, 0, 0)
    for step in recipe.steps:
        if step.kind == "wait_ms":
            assert step.wait_ms is not None
            time_ns += step.wait_ms * 1_000_000
            points.append(TrajectoryPoint(time_ns, last_joints, 0))
        elif step.kind == "set_joint_target":
            assert step.joint_urad is not None and step.duration_ms is not None
            time_ns += step.duration_ms * 1_000_000
            last_joints = step.joint_urad
            points.append(TrajectoryPoint(time_ns, last_joints, 0))
        else:
            assert step.trajectory_name is not None
            trajectory = (available_trajectories or {})[step.trajectory_name]
            if not trajectory.points:
                continue
            base = trajectory.points[0].time_ns
            for point in trajectory.points:
                points.append(
                    TrajectoryPoint(
                        time_ns + (point.time_ns - base),
                        point.joint_urad,
                        point.gripper_u16 if point.gripper_u16 is not None else 0,
                    )
                )
                last_joints = point.joint_urad
            time_ns = points[-1].time_ns if points else time_ns
    return tuple(points)
