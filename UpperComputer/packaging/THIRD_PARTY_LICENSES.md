# Third-party license inventory

This inventory is generated for packaging unit 28/29. Exact package versions are
pinned in `uv.lock`.

| Package | Use | License family |
|---|---|---|
| PySide6 | GUI | LGPL/commercial (Qt for Python) |
| pyqtgraph | Charts / OpenGL helpers | MIT |
| PyOpenGL | OpenGL bindings | BSD-style |
| numpy | Numeric arrays | BSD |
| scipy | Offline IK | BSD |
| pyserial | Serial transport | BSD |
| pydantic | Config validation | MIT |
| platformdirs | User data paths | MIT |
| PyInstaller | Portable packaging | GPL with exception / bootloader terms |

Robot model assets under `resources/robot_model` are covered by GPL-2.0 as copied
from the reference project and retained in `resources/robot_model/licenses/`.

The ZeroArm Desktop application code itself is marked Proprietary in
`pyproject.toml` and must not be redistributed without owner authorization.
