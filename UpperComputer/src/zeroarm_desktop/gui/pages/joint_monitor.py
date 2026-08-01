"""Six-axis table and bounded target/actual/error plots."""

import pyqtgraph as pg  # type: ignore[import-untyped]
from PySide6.QtCore import Slot
from PySide6.QtWidgets import QGridLayout, QLabel, QVBoxLayout, QWidget

from zeroarm_desktop.gui.viewmodels.snapshot import SnapshotViewModel, SnapshotViewState


class JointMonitorPage(QWidget):
    def __init__(self, view_model: SnapshotViewModel) -> None:
        super().__init__()
        self.setObjectName("page_joint_monitor")
        title = QLabel("六轴监控")
        title.setObjectName("page_title")
        headers = ("轴", "目标 urad", "实际 urad", "误差 urad", "速度", "电流", "Online")
        grid = QGridLayout()
        for column, text in enumerate(headers):
            grid.addWidget(QLabel(text), 0, column)
        self.rows: list[list[QLabel]] = []
        for axis in range(6):
            row = [QLabel(f"J{axis + 1}")] + [QLabel("--") for _ in range(6)]
            for column, label in enumerate(row):
                label.setObjectName(f"joint_{axis + 1}_column_{column}")
                grid.addWidget(label, axis + 1, column)
            self.rows.append(row)
        self.plot = pg.PlotWidget()
        self.plot.setObjectName("joint_plot")
        self.plot.addLegend()
        colors = ("#4ac6b7", "#55a7ff", "#ffb454")
        self.curves = [
            self.plot.plot(name=name, pen=pg.mkPen(color, width=2))
            for name, color in zip(("J1 Target", "J1 Actual", "J1 Error"), colors, strict=True)
        ]
        layout = QVBoxLayout(self)
        layout.setContentsMargins(36, 32, 36, 32)
        layout.addWidget(title)
        layout.addLayout(grid)
        layout.addWidget(self.plot, 1)
        view_model.state_changed.connect(self.apply_state)

    @Slot(object)
    def apply_state(self, state: SnapshotViewState) -> None:
        for row, joint in zip(self.rows, state.joints, strict=False):
            if joint.index - 1 in state.unavailable_axes:
                row[0].setText(f"J{joint.index} (Unavailable)")
                for label in row[1:]:
                    label.setText("--")
                continue
            texts = (
                str(joint.target_urad),
                str(joint.actual_urad),
                str(joint.error_urad),
                joint.velocity_text,
                joint.current_text,
                joint.online_text,
            )
            for label, value in zip(row[1:], texts, strict=True):
                label.setText(value)
        if not state.samples:
            return
        x = [
            (sample.monotonic_ns - state.samples[0].monotonic_ns) / 1_000_000_000
            for sample in state.samples
        ]
        target = [sample.target[0] for sample in state.samples]
        actual = [sample.actual[0] for sample in state.samples]
        error = [
            target_value - actual_value
            for target_value, actual_value in zip(target, actual, strict=True)
        ]
        for curve, series in zip(self.curves, (target, actual, error), strict=True):
            curve.setData(x, series)
