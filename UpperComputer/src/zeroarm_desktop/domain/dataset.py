"""Episode dataset schema and export helpers for offline learning pipelines."""

import csv
import json
from collections.abc import Mapping
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path

from zeroarm_desktop.domain.models import JointVector

type JsonValue = None | bool | int | float | str | list["JsonValue"] | dict[str, "JsonValue"]


@dataclass(frozen=True, slots=True)
class Observation:
    joint_urad: JointVector
    run_state_raw: int
    fault_flags_raw: int
    pc_monotonic_ns: int
    wall_utc: datetime
    device_time_ms: int | None
    sample_sequence: int | None


@dataclass(frozen=True, slots=True)
class Action:
    kind: str
    joint_urad: JointVector | None
    gripper_u16: int | None
    target_transport: str


@dataclass(frozen=True, slots=True)
class StepResult:
    accepted: bool
    result_raw: int | None
    completed: bool | None


@dataclass(frozen=True, slots=True)
class EpisodeStep:
    observation: Observation
    action: Action
    result: StepResult


@dataclass(frozen=True, slots=True)
class Episode:
    schema_version: int
    episode_id: str
    source: str
    steps: tuple[EpisodeStep, ...]
    metadata: Mapping[str, JsonValue]


def validate_episode(episode: Episode) -> tuple[str, ...]:
    issues: list[str] = []
    if episode.schema_version != 1:
        issues.append("schema_unsupported")
    if not episode.steps:
        issues.append("empty_episode")
    for index, step in enumerate(episode.steps):
        if step.action.target_transport not in {"mock", "serial", "none"}:
            issues.append(f"step_{index}_transport")
        if step.action.target_transport == "serial" and step.action.kind != "readonly":
            issues.append(f"step_{index}_serial_action_forbidden")
        if step.observation.device_time_ms is not None and step.observation.device_time_ms < 0:
            issues.append(f"step_{index}_device_time")
    return tuple(issues)


def episode_to_json(episode: Episode) -> str:
    def encode(value: object) -> object:
        if isinstance(value, datetime):
            return value.isoformat()
        if isinstance(value, tuple):
            return [encode(item) for item in value]
        if isinstance(value, list):
            return [encode(item) for item in value]
        if isinstance(value, Mapping):
            return {key: encode(item) for key, item in value.items()}
        if isinstance(value, (Episode, EpisodeStep, Observation, Action, StepResult)):
            return encode(asdict(value))
        return value

    return json.dumps(encode(episode), ensure_ascii=False, sort_keys=True, indent=2)


def export_episode_csv(episode: Episode, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.writer(stream)
        writer.writerow(
            [
                "index",
                "pc_monotonic_ns",
                "wall_utc",
                "device_time_ms",
                "sample_sequence",
                "action_kind",
                "target_transport",
                "accepted",
                "completed",
            ]
        )
        for index, step in enumerate(episode.steps):
            writer.writerow(
                [
                    index,
                    step.observation.pc_monotonic_ns,
                    step.observation.wall_utc.isoformat(),
                    step.observation.device_time_ms,
                    step.observation.sample_sequence,
                    step.action.kind,
                    step.action.target_transport,
                    step.result.accepted,
                    step.result.completed,
                ]
            )


def export_episode_npz(episode: Episode, path: Path) -> None:
    """Export a lightweight NPZ-compatible archive using pure Python JSON sidecar."""
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "episode_id": episode.episode_id,
        "source": episode.source,
        "schema_version": episode.schema_version,
        "joint_urad": [list(step.observation.joint_urad) for step in episode.steps],
        "actions": [step.action.kind for step in episode.steps],
        "target_transport": [step.action.target_transport for step in episode.steps],
    }
    # Keep a pure-Python fallback for environments without writeable numpy save.
    path.write_text(json.dumps(payload, ensure_ascii=False, sort_keys=True), encoding="utf-8")
