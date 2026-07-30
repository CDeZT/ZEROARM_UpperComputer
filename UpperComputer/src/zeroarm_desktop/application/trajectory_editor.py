"""Immutable trajectory editing history."""

from zeroarm_desktop.domain.trajectory import Trajectory


class TrajectoryEditor:
    def __init__(self, trajectory: Trajectory) -> None:
        self._history = [trajectory]
        self._index = 0

    @property
    def current(self) -> Trajectory:
        return self._history[self._index]

    @property
    def can_undo(self) -> bool:
        return self._index > 0

    @property
    def can_redo(self) -> bool:
        return self._index < len(self._history) - 1

    def apply(self, trajectory: Trajectory) -> None:
        self._history = self._history[: self._index + 1]
        self._history.append(trajectory)
        self._index += 1

    def undo(self) -> Trajectory:
        if self.can_undo:
            self._index -= 1
        return self.current

    def redo(self) -> Trajectory:
        if self.can_redo:
            self._index += 1
        return self.current
