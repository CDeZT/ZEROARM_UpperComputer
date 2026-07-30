"""Trajectory editor ViewModel and 3D cursor integration."""

from PySide6.QtCore import QObject, Signal

from zeroarm_desktop.application.trajectory_editor import TrajectoryEditor
from zeroarm_desktop.domain.trajectory import (
    Trajectory,
    TrajectoryPoint,
    resample_linear,
    smooth_moving_average,
    validate_trajectory,
)


class TrajectoryViewModel(QObject):
    changed = Signal(object)
    ghost_changed = Signal(object)

    def __init__(self) -> None:
        super().__init__()
        initial = Trajectory(
            1,
            "Demo trajectory",
            (
                TrajectoryPoint(0, (0, 1_570_770, 0, 0, 0, 0), 0),
                TrajectoryPoint(1_000_000_000, (87_266, 1_570_770, 0, 0, 0, 0), 0),
                TrajectoryPoint(2_000_000_000, (0, 1_570_770, 0, 0, 0, 0), 0),
            ),
            "created",
            {},
        )
        self.editor = TrajectoryEditor(initial)

    @property
    def trajectory(self) -> Trajectory:
        return self.editor.current

    def select(self, index: int) -> None:
        self.ghost_changed.emit(self.trajectory.points[index].joint_urad)

    def resample(self) -> None:
        self.editor.apply(resample_linear(self.trajectory, 100_000_000))
        self.changed.emit(self.trajectory)

    def smooth(self) -> None:
        self.editor.apply(smooth_moving_average(self.trajectory))
        self.changed.emit(self.trajectory)

    def undo(self) -> None:
        self.changed.emit(self.editor.undo())

    def redo(self) -> None:
        self.changed.emit(self.editor.redo())

    def validation_text(self) -> str:
        report = validate_trajectory(self.trajectory)
        if report.valid:
            return f"有效 | {report.point_count}点 | {report.duration_ns / 1e9:.3f}s"
        return "拒绝: " + ", ".join(issue.code for issue in report.issues)
