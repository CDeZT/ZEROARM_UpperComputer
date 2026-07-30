"""Mock-only Recipe runner that expands to trajectory points."""

from collections.abc import Mapping
from dataclasses import dataclass
from enum import Enum

from zeroarm_desktop.domain.recipe import Recipe, expand_recipe_to_points
from zeroarm_desktop.domain.trajectory import Trajectory, TrajectoryPoint


class RecipeRunnerState(Enum):
    IDLE = "idle"
    READY = "ready"
    RUNNING = "running"
    ABORTED = "aborted"
    COMPLETED = "completed"


@dataclass(frozen=True, slots=True)
class RecipeProgress:
    state: RecipeRunnerState
    point_count: int
    current_index: int
    reason: str | None = None


class RecipeRunner:
    def __init__(self) -> None:
        self.progress = RecipeProgress(RecipeRunnerState.IDLE, 0, -1)
        self._points: tuple[TrajectoryPoint, ...] = ()

    def prepare(
        self,
        recipe: Recipe,
        *,
        available_trajectories: Mapping[str, Trajectory] | None = None,
    ) -> RecipeProgress:
        self._points = expand_recipe_to_points(
            recipe,
            available_trajectories=available_trajectories,
        )
        self.progress = RecipeProgress(RecipeRunnerState.READY, len(self._points), -1)
        return self.progress

    def start_mock(self) -> RecipeProgress:
        if self.progress.state is not RecipeRunnerState.READY:
            raise RuntimeError("recipe is not prepared")
        self.progress = RecipeProgress(RecipeRunnerState.RUNNING, len(self._points), 0)
        return self.progress

    def advance(self) -> RecipeProgress:
        if self.progress.state is not RecipeRunnerState.RUNNING:
            return self.progress
        next_index = self.progress.current_index + 1
        if next_index >= len(self._points):
            self.progress = RecipeProgress(
                RecipeRunnerState.COMPLETED,
                len(self._points),
                len(self._points) - 1,
            )
        else:
            self.progress = RecipeProgress(
                RecipeRunnerState.RUNNING,
                len(self._points),
                next_index,
            )
        return self.progress

    def abort(self, reason: str) -> RecipeProgress:
        self.progress = RecipeProgress(
            RecipeRunnerState.ABORTED,
            len(self._points),
            self.progress.current_index,
            reason,
        )
        return self.progress

    @property
    def points(self) -> tuple[TrajectoryPoint, ...]:
        return self._points
