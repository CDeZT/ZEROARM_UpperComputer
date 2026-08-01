"""Mock gamepad mapping and Recipe prepare/run via trajectory playback."""

from PySide6.QtWidgets import QLabel, QPushButton, QTextEdit, QVBoxLayout, QWidget

from zeroarm_desktop.application.gamepad import (
    DEFAULT_GAMEPAD_PROFILE,
    GamepadSample,
    map_sample_to_joint_steps,
)
from zeroarm_desktop.application.recipe_runner import RecipeRunner
from zeroarm_desktop.domain.recipe import Recipe, RecipeStep, recipe_to_json, validate_recipe
from zeroarm_desktop.domain.trajectory import Trajectory
from zeroarm_desktop.gui.viewmodels.trajectory import TrajectoryViewModel


class GamepadRecipePage(QWidget):
    def __init__(self, trajectory_view_model: TrajectoryViewModel) -> None:
        super().__init__()
        self.setObjectName("page_gamepad_recipe")
        self.trajectory_view_model = trajectory_view_model
        self.runner = RecipeRunner()
        title = QLabel("手柄与 Recipe (Mock)")
        title.setObjectName("page_title")
        self.status = QLabel("默认 Observer | Recipe 可展开为轨迹后 Mock 回放 | 经 SafetyGate")
        self.status.setObjectName("gamepad_recipe_status")
        self.status.setWordWrap(True)
        self.preview = QTextEdit()
        self.preview.setObjectName("recipe_preview")
        self.preview.setReadOnly(True)
        validate = QPushButton("验证并准备示例 Recipe")
        validate.setObjectName("validate_recipe_button")
        validate.clicked.connect(self.validate_demo)
        run = QPushButton("加载到轨迹并 Mock 回放")
        run.setObjectName("run_recipe_button")
        run.clicked.connect(self.run_demo)
        hold = QPushButton("模拟手柄 Hold 映射")
        hold.setObjectName("simulate_gamepad_hold")
        hold.clicked.connect(self.simulate_hold)
        release = QPushButton("模拟失焦/松手停止")
        release.setObjectName("simulate_gamepad_release")
        release.clicked.connect(self.simulate_release)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(36, 32, 36, 32)
        for widget in (title, self.status, validate, run, hold, release, self.preview):
            layout.addWidget(widget)

    def validate_demo(self) -> None:
        recipe = self._demo_recipe()
        issues = validate_recipe(recipe)
        self.preview.setPlainText(recipe_to_json(recipe))
        if issues:
            self.status.setText("Recipe拒绝: " + ",".join(issue.code for issue in issues))
            return
        progress = self.runner.prepare(recipe)
        self.status.setText(f"Recipe有效 | points={progress.point_count} | runner READY")

    def run_demo(self) -> None:
        try:
            if self.runner.progress.point_count <= 0:
                self.validate_demo()
            if self.runner.progress.point_count <= 0:
                raise RuntimeError("Recipe 未准备")
            self.runner.start_mock()
            trajectory = Trajectory(
                1,
                "recipe_demo",
                self.runner.points,
                "recipe",
                {"source": "gamepad_recipe_page"},
            )
            self.trajectory_view_model.load_trajectory(trajectory)
            self.trajectory_view_model.start_playback()
            self.status.setText(f"Recipe 已加载并启动 Mock 回放 | points={len(trajectory.points)}")
        except (PermissionError, RuntimeError, ValueError) as error:
            self.runner.abort(str(error))
            self.status.setText(f"Recipe 运行失败: {error}")

    def simulate_hold(self) -> None:
        steps = map_sample_to_joint_steps(
            GamepadSample((0.5, -0.2, 0.0, 0.0, 0.0, 0.0), (True,), True),
            DEFAULT_GAMEPAD_PROFILE,
        )
        self.status.setText(f"Hold映射 steps={steps} | 未直写 Transport | 可接手动点动")

    def simulate_release(self) -> None:
        steps = map_sample_to_joint_steps(
            GamepadSample((0.5, -0.2, 0.0, 0.0, 0.0, 0.0), (False,), False),
            DEFAULT_GAMEPAD_PROFILE,
        )
        self.runner.abort("focus_or_release")
        self.trajectory_view_model.abort_playback("gamepad_release")
        self.status.setText(f"失焦/松手停止 | steps={steps} | runner ABORTED")

    @staticmethod
    def _demo_recipe() -> Recipe:
        return Recipe(
            1,
            "demo",
            (
                RecipeStep("wait_ms", wait_ms=100),
                RecipeStep(
                    "set_joint_target",
                    joint_urad=(20_000, 0, 0, 0, 0, 0),
                    duration_ms=200,
                ),
                RecipeStep(
                    "set_joint_target",
                    joint_urad=(0, 0, 0, 0, 0, 0),
                    duration_ms=200,
                ),
            ),
            {},
        )
