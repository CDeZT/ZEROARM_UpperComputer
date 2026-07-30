"""Offline Cartesian IK ghost preview page."""

from PySide6.QtWidgets import QDoubleSpinBox, QFormLayout, QLabel, QPushButton, QVBoxLayout, QWidget

from zeroarm_desktop.application.device_session import DeviceSession
from zeroarm_desktop.model3d.fk import identity_matrix
from zeroarm_desktop.model3d.ik import NumericalIkSolver


class CartesianPage(QWidget):
    def __init__(
        self, solver: NumericalIkSolver, session_provider: object, ghost_callback: object
    ) -> None:
        super().__init__()
        self.setObjectName("page_cartesian")
        self.solver = solver
        self.provider = session_provider
        self.ghost_callback = ghost_callback
        title = QLabel("Cartesian / IK 离线预览")
        title.setObjectName("page_title")
        form = QFormLayout()
        self.inputs = []
        for axis, value in zip("XYZ", (0.0, -172.631, 181.5), strict=True):
            field = QDoubleSpinBox()
            field.setRange(-1000, 1000)
            field.setDecimals(3)
            field.setValue(value)
            field.setObjectName(f"cartesian_{axis.lower()}_mm")
            form.addRow(f"{axis} (mm)", field)
            self.inputs.append(field)
        solve = QPushButton("求解并更新Ghost")
        solve.setObjectName("solve_ik_button")
        solve.clicked.connect(self.solve)
        self.status = QLabel("仅离线预览 | V1无Cartesian命令 | 禁止发送")
        self.status.setObjectName("ik_status")
        layout = QVBoxLayout(self)
        layout.addWidget(title)
        layout.addLayout(form)
        layout.addWidget(solve)
        layout.addWidget(self.status)
        layout.addStretch()

    def solve(self) -> None:
        session = getattr(self.provider, "session", None)
        seed = (
            session.latest_snapshot.actual_joint_urad
            if isinstance(session, DeviceSession) and session.latest_snapshot
            else (0, 3_141_539, -1_570_770, 0, 1_570_770, 0)
        )
        matrix = [list(row) for row in identity_matrix()]
        for index, field in enumerate(self.inputs):
            matrix[index][3] = field.value() / 1000
        target = tuple(tuple(row) for row in matrix)
        result = self.solver.solve(target, seed)  # type: ignore[arg-type]
        if not result.solutions:
            self.status.setText(f"未找到可行解: {result.reason} | 仅离线")
            return
        solution = result.solutions[0]
        if callable(self.ghost_callback):
            self.ghost_callback(solution.joint_urad)
        self.status.setText(
            f"候选={len(result.solutions)} | "
            f"FK误差={solution.position_error_m * 1000:.4f}mm | Ghost only"
        )
