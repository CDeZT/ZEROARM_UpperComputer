"""Lightweight link/GUI performance snapshot for soak and status surfaces."""

from __future__ import annotations

from dataclasses import dataclass
from time import monotonic_ns

from zeroarm_desktop.application.device_session import DeviceSession, SessionStatistics
from zeroarm_desktop.application.recorder import RecorderStatistics


@dataclass(frozen=True, slots=True)
class PerformanceSnapshot:
    schema_version: int
    measured_monotonic_ns: int
    window_s: float
    snapshot_hz: float
    requests_sent: int
    responses_received: int
    poll_coalesced: int
    unexpected_frames: int
    recorder_written: int
    recorder_dropped: int
    notes: tuple[str, ...]


class PerformanceSampler:
    """Estimate snapshot rate from successive SessionStatistics samples."""

    def __init__(self) -> None:
        self._previous: SessionStatistics | None = None
        self._previous_ns: int | None = None

    def sample(
        self,
        session: DeviceSession | None,
        recorder_stats: RecorderStatistics | None = None,
    ) -> PerformanceSnapshot:
        now = monotonic_ns()
        stats = session.statistics if session is not None else SessionStatistics()
        window_s = 0.0
        snapshot_hz = 0.0
        if self._previous is not None and self._previous_ns is not None:
            window_s = max(1e-9, (now - self._previous_ns) / 1e9)
            delta = stats.snapshots_published - self._previous.snapshots_published
            snapshot_hz = max(0.0, delta / window_s)
        self._previous = stats
        self._previous_ns = now
        recorder = recorder_stats or RecorderStatistics()
        notes: list[str] = []
        if stats.poll_coalesced:
            notes.append("poll_coalesced>0")
        if recorder.events_dropped:
            notes.append("recorder_drops>0")
        if stats.unexpected_frames:
            notes.append("unexpected_frames>0")
        return PerformanceSnapshot(
            schema_version=1,
            measured_monotonic_ns=now,
            window_s=window_s,
            snapshot_hz=snapshot_hz,
            requests_sent=stats.requests_sent,
            responses_received=stats.responses_received,
            poll_coalesced=stats.poll_coalesced,
            unexpected_frames=stats.unexpected_frames,
            recorder_written=recorder.events_written,
            recorder_dropped=recorder.events_dropped,
            notes=tuple(notes),
        )
