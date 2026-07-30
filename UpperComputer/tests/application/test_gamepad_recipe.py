"""Gamepad mapping and Recipe validation tests."""

from zeroarm_desktop.application.gamepad import (
    DEFAULT_GAMEPAD_PROFILE,
    GamepadSample,
    apply_deadzone,
    map_sample_to_joint_steps,
)
from zeroarm_desktop.application.recipe_runner import RecipeRunner, RecipeRunnerState
from zeroarm_desktop.domain.recipe import (
    Recipe,
    RecipeStep,
    recipe_from_json,
    recipe_to_json,
    validate_recipe,
)


def test_deadzone_and_hold_mapping() -> None:
    assert apply_deadzone(0.05, 0.12) == 0.0
    assert apply_deadzone(1.0, 0.12) == 1.0
    hold = map_sample_to_joint_steps(
        GamepadSample((1.0, 0.0, 0.0, 0.0, 0.0, 0.0), (True,), True),
        DEFAULT_GAMEPAD_PROFILE,
    )
    release = map_sample_to_joint_steps(
        GamepadSample((1.0, 0.0, 0.0, 0.0, 0.0, 0.0), (False,), False),
        DEFAULT_GAMEPAD_PROFILE,
    )
    assert hold[0] > 0
    assert release == (0, 0, 0, 0, 0, 0)


def test_recipe_json_and_runner_abort() -> None:
    recipe = Recipe(
        1,
        "demo",
        (
            RecipeStep("wait_ms", wait_ms=50),
            RecipeStep(
                "set_joint_target", joint_urad=(1_000, 1_570_770, 0, 0, 0, 0), duration_ms=100
            ),
        ),
        {},
    )
    assert recipe_from_json(recipe_to_json(recipe)) == recipe
    assert not validate_recipe(recipe)
    runner = RecipeRunner()
    runner.prepare(recipe)
    runner.start_mock()
    runner.abort("focus_loss")
    assert runner.progress.state is RecipeRunnerState.ABORTED
