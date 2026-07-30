"""Mock teach state machine and immutable raw recording."""

import hashlib
import json
from collections import deque
from dataclasses import dataclass
from datetime import datetime
from enum import Enum

from zeroarm_desktop.domain.models import RobotSnapshot
from zeroarm_desktop.domain.trajectory import Trajectory, TrajectoryPoint


class TeachState(Enum):
    IDLE = "idle"
    RECORDING = "recording"
    REVIEW = "review"


@dataclass(frozen=True, slots=True)
class TeachSample:
    pc_monotonic_ns: int
    wall_utc: datetime
    device_time_ms: int | None
    sample_sequence: int | None
    joint_urad: tuple[int, int, int, int, int, int]


@dataclass(frozen=True, slots=True)
class RawTeachRecording:
    joint_mask: int
    samples: tuple[TeachSample, ...]
    dropped_samples: int
    sha256: str


class TeachRecorder:
    def __init__(self, capacity: int = 60_000) -> None:
        self.state = TeachState.IDLE
        self._samples: deque[TeachSample] = deque(maxlen=capacity)
        self._dropped = 0

    def start(self) -> None:
        self._samples.clear()
        self._dropped = 0
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
            )
        )

    def stop(self, joint_mask: int) -> RawTeachRecording:
        self.state = TeachState.REVIEW
        payload = json.dumps(
            [(sample.pc_monotonic_ns, sample.joint_urad) for sample in self._samples],
            separators=(",", ":"),
        ).encode()
        return RawTeachRecording(
            joint_mask,
            tuple(self._samples),
            self._dropped,
            hashlib.sha256(payload).hexdigest(),
        )


def recording_to_trajectory(recording: RawTeachRecording, name: str) -> Trajectory:
    if not recording.samples:
        raise ValueError("teach recording is empty")
    start = recording.samples[0].pc_monotonic_ns
    points = tuple(
        TrajectoryPoint(sample.pc_monotonic_ns - start, sample.joint_urad, 0)
        for sample in recording.samples
    )
    return Trajectory(1, name, points, "processed", {"parent_raw_sha256": recording.sha256})
