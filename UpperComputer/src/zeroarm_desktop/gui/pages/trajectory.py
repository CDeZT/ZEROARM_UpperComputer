"""Versioned trajectory table, import/export, processing, and playback page."""

from pathlib import Path

import pyqtgraph as pg  # type: ignore[import-untyped]
from PySide6.QtWidgets import (
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from zeroarm_desktop.domain.trajectory import Trajectory, validate_trajectory
from zeroarm_desktop.gui.viewmodels.trajectory import TrajectoryViewModel
from zeroarm_desktop.infrastructure.paths import default_data_root


class TrajectoryPage(QWidget):
    def __init__(self, view_model: TrajectoryViewModel) -> None:
        super().__init__()
        self.setObjectName("page_trajectory")
        self.view_model = view_model
        title = QLabel("轨迹编辑器")
        title.setObjectName("page_title")
        self.table = QTableWidget()
        self.table.setObjectName("trajectory_table")
        self.table.setColumnCount(8)
        self.table.setHorizontalHeaderLabels(("t(s)", "J1", "J2", "J3", "J4", "J5", "J6", "Grip"))
        self.table.currentCellChanged.connect(
            lambda row, column, old_row, old_column: self._select(row)
        )
        self.plot = pg.PlotWidget()
        self.plot.setObjectName("trajectory_plot")
        self.status = QLabel()
        self.status.setObjectName("trajectory_status")
        self.constraint_report = QLabel()
        self.constraint_report.setObjectName("trajectory_constraint_report")
        self.constraint_report.setWordWrap(True)
        buttons = QHBoxLayout()
        for name, text, operation in (
            ("trajectory_validate_button", "验证", self._validate),
            ("trajectory_import_button", "导入 JSON", self._import_json),
            ("trajectory_export_button", "导出 JSON", self._export_json),
            ("trajectory_resample_button", "重采样 10Hz", view_model.resample),
            ("trajectory_smooth_button", "平滑", view_model.smooth),
            ("trajectory_undo_button", "撤销", view_model.undo),
            ("trajectory_redo_button", "重做", view_model.redo),
            ("playback_start_button", "Mock回放", self._playback_start),
            ("playback_pause_button", "暂停", view_model.pause_playback),
            ("playback_resume_button", "继续", view_model.resume_playback),
            ("playback_abort_button", "中止", view_model.abort_playback),
        ):
            button = QPushButton(text)
            button.setObjectName(name)
            button.clicked.connect(operation)
            buttons.addWidget(button)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(28, 24, 28, 24)
        layout.addWidget(title)
        layout.addLayout(buttons)
        layout.addWidget(self.table, 1)
        layout.addWidget(self.plot, 1)
        layout.addWidget(self.status)
        layout.addWidget(self.constraint_report)
        view_model.changed.connect(self.apply_trajectory)
        self.apply_trajectory(view_model.trajectory)

    def apply_trajectory(self, trajectory: Trajectory) -> None:
        self.table.setRowCount(len(trajectory.points))
        self.plot.clear()
        times = [point.time_ns / 1e9 for point in trajectory.points]
        for row, point in enumerate(trajectory.points):
            values = (f"{point.time_ns / 1e9:.3f}", *point.joint_urad, point.gripper_u16)
            for column, value in enumerate(values):
                self.table.setItem(row, column, QTableWidgetItem(str(value)))
        for axis in range(6):
            self.plot.plot(times, [point.joint_urad[axis] for point in trajectory.points])
        self._validate()

    def _select(self, row: int) -> None:
        if 0 <= row < len(self.view_model.trajectory.points):
            self.view_model.select(row)

    def _validate(self) -> None:
        progress = self.view_model.playback.progress
        reason = f" reason={progress.reason}" if progress.reason else ""
        self.status.setText(
            f"{self.view_model.validation_text()} | Playback {progress.state.value} | "
            f"sent={progress.points_sent} dropped={progress.late_points_dropped}"
            f" evidence={len(self.view_model.evidence)}{reason}"
        )
        report = validate_trajectory(self.view_model.trajectory)
        if report.valid:
            self.constraint_report.setText(f"逐点约束: 通过 ({report.point_count} 点)")
            return
        lines = [f"逐点约束: 拒绝 {len(report.issues)} 项"]
        for issue in report.issues[:8]:
            location = f"点{issue.point_index}" if issue.point_index is not None else "全局"
            joint = f" J{issue.joint_index + 1}" if issue.joint_index is not None else ""
            detail = f" | {issue.detail}" if issue.detail else ""
            lines.append(f"- {location}{joint} {issue.code}{detail}")
        self.constraint_report.setText("\n".join(lines))

    def _playback_start(self) -> None:
        try:
            self.view_model.start_playback()
        except (PermissionError, RuntimeError, ValueError) as error:
            self.status.setText(str(error))

    def _import_json(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, "导入轨迹 JSON", str(default_data_root() / "trajectories"), "JSON (*.json)"
        )
        if not path:
            return
        try:
            text = Path(path).read_text(encoding="utf-8")
            trajectory = self.view_model.import_json_text(text)
            self.status.setText(f"已导入 {trajectory.name} | points={len(trajectory.points)}")
        except (OSError, ValueError, TypeError, KeyError) as error:
            self.status.setText(f"导入失败: {error}")

    def _export_json(self) -> None:
        directory = default_data_root() / "trajectories"
        directory.mkdir(parents=True, exist_ok=True)
        path, _ = QFileDialog.getSaveFileName(
            self,
            "导出轨迹 JSON",
            str(directory / f"{self.view_model.trajectory.name}.json"),
            "JSON (*.json)",
        )
        if not path:
            return
        try:
            Path(path).write_text(self.view_model.export_json_text(), encoding="utf-8")
            self.status.setText(f"已导出: {Path(path).name}")
        except OSError as error:
            self.status.setText(f"导出失败: {error}")
