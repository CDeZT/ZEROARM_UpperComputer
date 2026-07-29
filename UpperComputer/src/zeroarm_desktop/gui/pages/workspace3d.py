"""OpenGL robot workspace with an explicit headless/unavailable fallback."""

from pathlib import Path

from PySide6.QtCore import Slot
from PySide6.QtGui import QGuiApplication, QMatrix4x4
from PySide6.QtWidgets import QLabel, QVBoxLayout, QWidget

from zeroarm_desktop.gui.viewmodels.workspace3d import Workspace3DViewModel
from zeroarm_desktop.model3d.mesh import load_binary_stl
from zeroarm_desktop.model3d.scene import RobotScene


class Workspace3DPage(QWidget):
    def __init__(self, view_model: Workspace3DViewModel, asset_root: Path) -> None:
        super().__init__()
        self.setObjectName("page_workspace_3d")
        self._renderer: OpenGLRobotRenderer | None = None
        title = QLabel("3D 工作区")
        title.setObjectName("page_title")
        self.status = QLabel("等待设备状态")
        self.status.setObjectName("workspace_3d_status")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 20, 24, 20)
        layout.addWidget(title)
        layout.addWidget(self.status)
        if QGuiApplication.platformName() not in {"offscreen", "minimal"}:
            try:
                self._renderer = OpenGLRobotRenderer(asset_root)
                layout.addWidget(self._renderer.widget, 1)
            except (ImportError, RuntimeError, ValueError) as error:
                self.status.setText(f"OpenGL不可用 | 已降级为场景数据模式: {error}")
        else:
            self.status.setText("Offscreen环境: 3D场景数据可用 | OpenGL渲染已禁用")
        view_model.scene_changed.connect(self.apply_scene)

    @Slot(object)
    def apply_scene(self, scene: RobotScene) -> None:
        self.status.setText(scene.status_text)
        if self._renderer is not None:
            self._renderer.set_scene(scene)


class OpenGLRobotRenderer:
    def __init__(self, asset_root: Path) -> None:
        import pyqtgraph.opengl as gl  # type: ignore[import-untyped]

        self._gl = gl
        self.widget = gl.GLViewWidget()
        self.widget.setObjectName("workspace_3d_view")
        self.widget.setCameraPosition(distance=0.9, elevation=25, azimuth=40)
        grid = gl.GLGridItem()
        grid.setSize(1, 1)
        grid.setSpacing(0.05, 0.05)
        self.widget.addItem(grid)
        axis = gl.GLAxisItem()
        axis.setSize(0.2, 0.2, 0.2)
        self.widget.addItem(axis)
        package = asset_root / "URDF_XG_Robot_Arm_Urdf_V1_1/meshes"
        self._geometry = {
            name: load_binary_stl(package / f"{name}.STL", link_name=name)
            for name in ("base_link", "link1", "link2", "link3", "link4", "link5", "ee_link")
        }
        self._actual = self._create_items((0.35, 0.72, 0.78, 1.0))
        self._ghost = self._create_items((0.25, 0.65, 1.0, 0.28))
        self._tail = gl.GLLinePlotItem(color=(1.0, 0.65, 0.2, 0.9), width=2)
        self.widget.addItem(self._tail)

    def _create_items(self, color: tuple[float, float, float, float]) -> dict[str, object]:
        items = {}
        for name, geometry in self._geometry.items():
            mesh_data = self._gl.MeshData(vertexes=geometry.triangles)
            item = self._gl.GLMeshItem(
                meshdata=mesh_data, color=color, smooth=False, shader="shaded"
            )
            item.setGLOptions("translucent" if color[3] < 1 else "opaque")
            self.widget.addItem(item)
            items[name] = item
        return items

    def set_scene(self, scene: RobotScene) -> None:
        for items, links in ((self._actual, scene.actual_links), (self._ghost, scene.ghost_links)):
            visible = {link.link_name for link in links}
            for name, item in items.items():
                item.setVisible(name in visible)  # type: ignore[attr-defined]
            for link in links:
                values = [value for row in link.transform for value in row]
                items[link.link_name].setTransform(QMatrix4x4(*values))  # type: ignore[attr-defined]
        if scene.trajectory_tail:
            import numpy as np

            self._tail.setData(pos=np.asarray(scene.trajectory_tail, dtype=np.float32))
