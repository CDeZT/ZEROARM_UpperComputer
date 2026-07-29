"""Headless-testable actual/ghost scene construction."""

from collections import deque
from dataclasses import dataclass

from zeroarm_desktop.domain.models import JointVector, RobotSnapshot
from zeroarm_desktop.model3d.fk import LinkTransform, Matrix4, UrdfForwardKinematics


@dataclass(frozen=True, slots=True)
class SceneLink:
    link_name: str
    transform: Matrix4
    rgba: tuple[float, float, float, float]


@dataclass(frozen=True, slots=True)
class RobotScene:
    generation: int | None
    actual_links: tuple[SceneLink, ...]
    ghost_links: tuple[SceneLink, ...]
    trajectory_tail: tuple[tuple[float, float, float], ...]
    status_text: str
    hardware_mapping_verified: bool


class RobotSceneBuilder:
    def __init__(self, kinematics: UrdfForwardKinematics, *, tail_capacity: int = 600) -> None:
        self.kinematics = kinematics
        self._tail: deque[tuple[float, float, float]] = deque(maxlen=tail_capacity)

    def build(
        self,
        snapshot: RobotSnapshot | None,
        *,
        ghost_target: JointVector | None = None,
    ) -> RobotScene:
        if snapshot is None:
            return RobotScene(None, (), (), tuple(self._tail), "未连接", False)
        actual_fk = self.kinematics.forward(snapshot.actual_joint_urad)
        self._tail.append(actual_fk.position_m)
        actual = self._scene_links(actual_fk.links, (0.35, 0.72, 0.78, 1.0))
        ghost: tuple[SceneLink, ...] = ()
        if ghost_target is not None:
            ghost = self._scene_links(
                self.kinematics.forward(ghost_target).links,
                (0.25, 0.65, 1.0, 0.28),
            )
        return RobotScene(
            snapshot.generation,
            actual,
            ghost,
            tuple(self._tail),
            "模型映射已验证 | 实机零点与方向待装机确认",
            False,
        )

    @staticmethod
    def _scene_links(
        transforms: tuple[LinkTransform, ...],
        color: tuple[float, float, float, float],
    ) -> tuple[SceneLink, ...]:
        return tuple(SceneLink(item.link_name, item.world_from_link, color) for item in transforms)
