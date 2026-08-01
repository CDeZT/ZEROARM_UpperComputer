"""Teach state machine, immutable raw recording, and post-stop review."""

from __future__ import annotations

import hashlib
import json
from collections import deque
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from time import monotonic_ns

from zeroarm_desktop.domain.models import RobotSnapshot
from zeroarm_desktop.domain.trajectory import Trajectory, TrajectoryPoint


class TeachState(Enum):
    IDLE = "idle"
    ARMED = "armed"
    RECORDING = "recording"
    REVIEW = "review"


@dataclass(frozen=True, slots=True)
class TeachSample:
    pc_monotonic_ns: int
    wall_utc: datetime
    device_time_ms: int | None
    sample_sequence: int | None
    joint_urad: tuple[int, int, int, int, int, int]
    run_state_raw: int
    enabled_mask: int | None


@dataclass(frozen=True, slots=True)
class RawTeachRecording:
    joint_mask: int
    samples: tuple[TeachSample, ...]
    dropped_samples: int
    sha256: str
    started_monotonic_ns: int
    stopped_monotonic_ns: int


@dataclass(frozen=True, slots=True)
class TeachStopReview:
    """Post-stop checks: disabled axes remain off and no auto-ENABLE."""

    joint_mask: int
    enabled_mask: int | None
    disabled_ok: bool
    run_state_raw: int | None
    sample_count: int
    dropped_samples: int
    duration_ns: int
    warnings: tuple[str, ...]


class TeachRecorder:
    def __init__(self, capacity: int = 60_000) -> None:
        self.state = TeachState.IDLE
        self.joint_mask = 0
        self._samples: deque[TeachSample] = deque(maxlen=capacity)
        self._dropped = 0
        self._started_ns = 0
        self._stopped_ns = 0
        self._last_recording: RawTeachRecording | None = None
        self._last_review: TeachStopReview | None = None

    @property
    def sample_count(self) -> int:
        return len(self._samples)

    @property
    def dropped_samples(self) -> int:
        return self._dropped

    @property
    def recording_span_ns(self) -> int:
        if len(self._samples) < 2:
            return 0
        return max(0, self._samples[-1].pc_monotonic_ns - self._samples[0].pc_monotonic_ns)

    @property
    def last_recording(self) -> RawTeachRecording | None:
        return self._last_recording

    @property
    def last_review(self) -> TeachStopReview | None:
        return self._last_review

    def reset(self) -> None:
        self.state = TeachState.IDLE
        self.joint_mask = 0
        self._samples.clear()
        self._dropped = 0
        self._started_ns = 0
        self._stopped_ns = 0
        self._last_recording = None
        self._last_review = None

    def mark_armed(self, joint_mask: int) -> None:
        if self.state not in {TeachState.IDLE, TeachState.ARMED, TeachState.REVIEW}:
            raise RuntimeError("cannot arm while recording")
        if joint_mask <= 0 or joint_mask > 0x3F:
            raise ValueError("joint_mask invalid")
        self.joint_mask = joint_mask
        self.state = TeachState.ARMED
        self._samples.clear()
        self._dropped = 0
        self._last_recording = None
        self._last_review = None

    def start(self, joint_mask: int | None = None) -> None:
        mask = self.joint_mask if joint_mask is None else joint_mask
        if mask <= 0 or mask > 0x3F:
            raise ValueError("joint_mask invalid")
        self.joint_mask = mask
        self._samples.clear()
        self._dropped = 0
        self._started_ns = monotonic_ns()
        self._stopped_ns = 0
        self.state = TeachState.RECORDING

    def append(self, snapshot: RobotSnapshot) -> None:
        if self.state is not TeachState.RECORDING:
            return
        if len(self._samples) == self._samples.maxlen:
            self._dropped += 1
        self._samples.append(
            TeachSample(
                snapshot.received_monotonic_ns,
                snapshot.received_wall_utc,
                snapshot.device_time_ms,
                snapshot.sample_sequence,
                snapshot.actual_joint_urad,
                snapshot.run_state_raw,
                snapshot.enabled_mask,
            )
        )

    def stop(
        self, snapshot: RobotSnapshot | None = None
    ) -> tuple[RawTeachRecording, TeachStopReview]:
        if self.state is not TeachState.RECORDING:
            raise RuntimeError("teach is not recording")
        if snapshot is not None:
            self.append(snapshot)
        self._stopped_ns = monotonic_ns()
        self.state = TeachState.REVIEW
        payload = json.dumps(
            [(sample.pc_monotonic_ns, sample.joint_urad) for sample in self._samples],
            separators=(",", ":"),
        ).encode()
        recording = RawTeachRecording(
            self.joint_mask,
            tuple(self._samples),
            self._dropped,
            hashlib.sha256(payload).hexdigest(),
            self._started_ns,
            self._stopped_ns,
        )
        review = build_stop_review(recording, snapshot)
        self._last_recording = recording
        self._last_review = review
        return recording, review


def build_stop_review(
    recording: RawTeachRecording,
    snapshot: RobotSnapshot | None,
) -> TeachStopReview:
    enabled = snapshot.enabled_mask if snapshot is not None else None
    run_state = snapshot.run_state_raw if snapshot is not None else None
    warnings: list[str] = []
    disabled_ok = enabled is not None and (enabled & recording.joint_mask) == 0
    if enabled is None:
        warnings.append("enabled_mask_unknown")
    elif not disabled_ok:
        warnings.append("taught_axes_still_enabled")
    if run_state is None:
        warnings.append("run_state_unknown")
    elif run_state == 3:
        warnings.append("still_teaching")
    warnings.append("not_auto_enabled")
    return TeachStopReview(
        recording.joint_mask,
        enabled,
        disabled_ok,
        run_state,
        len(recording.samples),
        recording.dropped_samples,
        max(0, recording.stopped_monotonic_ns - recording.started_monotonic_ns),
        tuple(warnings),
    )


def recording_to_trajectory(recording: RawTeachRecording, name: str) -> Trajectory:
    if not recording.samples:
        raise ValueError("teach recording is empty")
    start = recording.samples[0].pc_monotonic_ns
    points = tuple(
        TrajectoryPoint(sample.pc_monotonic_ns - start, sample.joint_urad, 0)
        for sample in recording.samples
    )
    return Trajectory(
        1,
        name,
        points,
        "processed",
        {
            "parent_raw_sha256": recording.sha256,
            "source": "teach",
            "joint_mask": recording.joint_mask,
            "dropped_samples": recording.dropped_samples,
        },
    )
