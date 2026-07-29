"""Throttled 3D scene ViewModel with latest Snapshot semantics."""

from PySide6.QtCore import QObject, QTimer, Signal, Slot

from zeroarm_desktop.application.device_session import DeviceSession
from zeroarm_desktop.domain.models import JointVector, RobotSnapshot
from zeroarm_desktop.model3d.scene import RobotScene, RobotSceneBuilder
from zeroarm_desktop.transport.base import Subscription


class Workspace3DViewModel(QObject):
    scene_changed = Signal(object)
    _snapshot_received = Signal(object)

    def __init__(self, builder: RobotSceneBuilder) -> None:
        super().__init__()
        self.builder = builder
        self._latest: RobotSnapshot | None = None
        self._ghost: JointVector | None = None
        self._subscription: Subscription | None = None
        self._snapshot_received.connect(self._ingest)
        self._timer = QTimer(self)
        self._timer.setInterval(17)
        self._timer.timeout.connect(self.render_now)
        self._timer.start()

    def bind_session(self, session: DeviceSession | None) -> None:
        if self._subscription is not None:
            self._subscription.cancel()
            self._subscription = None
        self._latest = None
        if session is not None:
            self._subscription = session.subscribe_snapshots(self._snapshot_received.emit)
            self._latest = session.latest_snapshot

    def set_ghost_target(self, target: JointVector | None) -> None:
        self._ghost = target
        self.render_now()

    @Slot(object)
    def _ingest(self, snapshot: RobotSnapshot) -> None:
        self._latest = snapshot

    @Slot()
    def render_now(self) -> RobotScene:
        scene = self.builder.build(self._latest, ghost_target=self._ghost)
        self.scene_changed.emit(scene)
        return scene

    def close(self) -> None:
        self._timer.stop()
        self.bind_session(None)
