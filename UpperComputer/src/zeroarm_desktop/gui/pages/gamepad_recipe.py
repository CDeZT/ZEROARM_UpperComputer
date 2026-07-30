"""Mock gamepad mapping and Recipe static-check page."""

from PySide6.QtWidgets import QLabel, QPushButton, QTextEdit, QVBoxLayout, QWidget

from zeroarm_desktop.application.gamepad import (
    DEFAULT_GAMEPAD_PROFILE,
    GamepadSample,
    map_sample_to_joint_steps,
)
from zeroarm_desktop.application.recipe_runner import RecipeRunner
from zeroarm_desktop.domain.recipe import Recipe, RecipeStep, recipe_to_json, validate_recipe


class GamepadRecipePage(QWidget):
    def __init__(self) -> None:
        super().__init__()
        self.setObjectName("page_gamepad_recipe")
        self.runner = RecipeRunner()
        title = QLabel("手柄与 Recipe (Mock Only)")
        title.setObjectName("page_title")
        self.status = QLabel("默认Observer | 动作仅Mock | 所有意图经SafetyGate")
        self.status.setObjectName("gamepad_recipe_status")
        self.preview = QTextEdit()
        self.preview.setObjectName("recipe_preview")
        self.preview.setReadOnly(True)
        validate = QPushButton("验证示例Recipe")
        validate.setObjectName("validate_recipe_button")
        validate.clicked.connect(self.validate_demo)
        hold = QPushButton("模拟手柄Hold映射")
        hold.setObjectName("simulate_gamepad_hold")
        hold.clicked.connect(self.simulate_hold)
        release = QPushButton("模拟失焦/松手停止")
        release.setObjectName("simulate_gamepad_release")
        release.clicked.connect(self.simulate_release)
        layout = QVBoxLayout(self)
        for widget in (title, self.status, validate, hold, release, self.preview):
            layout.addWidget(widget)

    def validate_demo(self) -> None:
        recipe = Recipe(
            1,
            "demo",
            (
                RecipeStep("wait_ms", wait_ms=100),
                RecipeStep(
                    "set_joint_target",
                    joint_urad=(10_000, 1_570_770, 0, 0, 0, 0),
                    duration_ms=200,
                ),
            ),
            {},
        )
        issues = validate_recipe(recipe)
        self.preview.setPlainText(recipe_to_json(recipe))
        if issues:
            self.status.setText("Recipe拒绝: " + ",".join(issue.code for issue in issues))
            return
        progress = self.runner.prepare(recipe)
        self.status.setText(f"Recipe有效 | points={progress.point_count} | Mock runner READY")

    def simulate_hold(self) -> None:
        steps = map_sample_to_joint_steps(
            GamepadSample((0.5, -0.2, 0.0, 0.0, 0.0, 0.0), (True,), True),
            DEFAULT_GAMEPAD_PROFILE,
        )
        self.status.setText(f"Hold映射 steps={steps} | 未直写Transport")

    def simulate_release(self) -> None:
        steps = map_sample_to_joint_steps(
            GamepadSample((0.5, -0.2, 0.0, 0.0, 0.0, 0.0), (False,), False),
            DEFAULT_GAMEPAD_PROFILE,
        )
        self.runner.abort("focus_or_release")
        self.status.setText(f"失焦/松手停止 | steps={steps} | runner ABORTED")
