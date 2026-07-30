"""Bounded deterministic numerical IK for offline ghost preview."""

import math
from dataclasses import dataclass

import numpy as np
from numpy.typing import NDArray
from scipy.optimize import least_squares  # type: ignore[import-untyped]

from zeroarm_desktop.domain.models import JointVector
from zeroarm_desktop.model3d.fk import Matrix4, UrdfForwardKinematics


@dataclass(frozen=True, slots=True)
class IkSolution:
    joint_urad: JointVector
    seed_distance: float
    position_error_m: float
    singular: bool


@dataclass(frozen=True, slots=True)
class IkResult:
    solutions: tuple[IkSolution, ...]
    reason: str | None


class NumericalIkSolver:
    def __init__(self, kinematics: UrdfForwardKinematics) -> None:
        self.kinematics = kinematics
        entries = kinematics.mapping.entries
        self.lower = np.array([entry.robot_min_urad for entry in entries], dtype=float)
        self.upper = np.array([entry.robot_max_urad for entry in entries], dtype=float)

    def solve(self, target: Matrix4, seed: JointVector) -> IkResult:
        target_position = np.array([target[0][3], target[1][3], target[2][3]])
        if not np.isfinite(target_position).all() or np.linalg.norm(target_position) > 2:
            return IkResult((), "invalid_or_outside_workspace")
        seeds = [np.array(seed, dtype=float), (self.lower + self.upper) / 2]
        solutions: list[IkSolution] = []
        for start in seeds:
            result = least_squares(
                lambda values: self._residual(values, target_position),
                np.clip(start, self.lower, self.upper),
                bounds=(self.lower, self.upper),
                max_nfev=300,
            )
            quantized: JointVector = tuple(round(value) for value in result.x)
            if self.kinematics.mapping.validate_robot_limits(quantized):
                continue
            position = np.array(self.kinematics.forward(quantized).position_m)
            error = float(np.linalg.norm(position - target_position))
            if error > 0.0002:
                continue
            candidate = IkSolution(
                quantized,
                math.sqrt(
                    sum((left - right) ** 2 for left, right in zip(quantized, seed, strict=True))
                ),
                error,
                bool(np.linalg.matrix_rank(result.jac) < 3),
            )
            if all(
                max(abs(a - b) for a, b in zip(candidate.joint_urad, item.joint_urad, strict=True))
                > 10
                for item in solutions
            ):
                solutions.append(candidate)
        solutions.sort(key=lambda item: item.seed_distance)
        return IkResult(tuple(solutions), None if solutions else "no_feasible_solution_found")

    def _residual(
        self,
        values: NDArray[np.float64],
        target: NDArray[np.float64],
    ) -> NDArray[np.float64]:
        joints: JointVector = tuple(round(value) for value in values)
        position: NDArray[np.float64] = np.asarray(
            self.kinematics.forward(joints).position_m,
            dtype=np.float64,
        )
        return (position - target) / 0.001
