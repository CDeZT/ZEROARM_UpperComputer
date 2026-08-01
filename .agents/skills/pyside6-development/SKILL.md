---
name: pyside6-development
description: "PySide6 Widgets development rules for ZeroArm Desktop. Use when writing or reviewing GUI code: MVC via ViewModels, Signal/Slot boundaries, QThread/QThreadPool, application-level QSS theming, layout managers, high DPI, stable objectName conventions, and pytest-qt testing."
---

# PySide6 开发规约

本项目使用 **PySide6（不是 PyQt6）**：`from PySide6.QtCore import Signal`（不是 pyqtSignal），
`pytest-qt` 的 `qt_api = "pyside6"`（pyproject.toml 已配置）。
与 `AGENTS.md` §6.2 配套执行，本技能是代码级细则。

## 铁律

1. GUI 线程不执行阻塞串口、SQLite 批写、批量 IK、固件烧录。
2. 跨线程用 queued signal 或明确有界队列；worker 不直接更新 Widget。
3. View 不得 import pyserial、sqlite 连接、协议字节操作。
4. 高频输入由 ViewModel 节流到渲染频率（≤60 FPS）。
5. Widget 销毁后取消订阅，避免幽灵更新和泄漏。
6. 所有危险按钮调用同一个 CommandService/SafetyGate，禁止页面直发。

## 结构

每页 = `PageWidget` + `PageViewModel(QObject)`：

- ViewModel 持有业务依赖（Session/Service），对外只发不可变 ViewState 和 Signal。
- Widget 只做布局、交互收集和显示；不写业务判断。
- 页面 objectName：`page_<name>`；按钮/控件 objectName 稳定，供 pytest-qt 定位。

## 信号槽

```python
class ManualJointViewModel(QObject):
    status_changed = Signal(str)
    ghost_target_changed = Signal(object)  # 只发不可变对象
```

- 跨线程连接必须保证接收方在 GUI 线程（用 Signal 桥或 `Qt.ConnectionType.QueuedConnection`）。
- 循环中连接 lambda 必须绑定默认参数：`clicked.connect(lambda checked=False, name=route: ...)`。
- 旧结果不得覆盖新任务：异步结果带 generation/operation id，过期直接丢弃。

## QSS 主题

- 在 `QApplication`/`MainWindow` 级别 `setStyleSheet`，用 objectName/class 选择器。
- 颜色集中在 `gui/theme.py`（DARK_THEME/LIGHT_THEME），禁止逐控件内联样式。
- 深浅主题都测试；危险按钮保持红色语义。

## 布局与高 DPI

- 一律 QVBoxLayout/QHBoxLayout/QGridLayout/QFormLayout + stretch；禁止 setGeometry/move。
- 默认窗口 1440×900、最小 1280×720；100/150/200% DPI 下验收。
- 控件尺寸用 size policy + 布局间距，不用固定像素。

## 测试

- ViewModel 逻辑可脱离 GUI 测试（纯 Python + pytest）。
- GUI 测试用 `pytest-qt` + `QT_QPA_PLATFORM=offscreen`；
  `window.findChild(QPushButton, "object_name")` 定位控件。
- 连接/断开、失焦、Esc、断线、模式切换必须有测试。
- 高频输入用注入测试：100 Hz 快照下渲染不积压。

## 审查清单

- 是否有阻塞调用在主线程（`sleep`、`wait`、`serial.read` 直接调用）？
- 是否直接用 `pyqtSignal`/`PyQt6` import？
- 是否 setGeometry/固定坐标？
- 是否漏掉订阅取消？
- 是否绕过 SafetyGate 发动作？
- 是否在 ViewModel 里 import pyserial/sqlite？
