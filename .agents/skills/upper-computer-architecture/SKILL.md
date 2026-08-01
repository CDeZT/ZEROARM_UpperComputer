---
name: upper-computer-architecture
description: Enforce and review the ZeroArm Desktop PySide6 upper-computer layered architecture. Use when designing new modules, refactoring, or auditing dependency direction, module boundaries, immutable state flow, thread ownership, and testability seams in src/zeroarm_desktop.
---

# 上位机架构规约

## 目标

保证 `src/zeroarm_desktop` 分层清晰、依赖单向、跨线程状态安全、可脱离 GUI 测试。
本项目权威基线：`UpperComputer/AGENTS.md` §6、`docs/02_TECHNICAL_ARCHITECTURE.md`、
`docs/15_IMPLEMENTATION_BLUEPRINT.md`、`docs/17_API_DATA_AND_FIXTURE_CONTRACTS.md`。
现场代码与文档冲突时，以代码和测试为准并指出差异。

## 分层与依赖方向

```text
gui/pages + gui/viewmodels + gui/shell + gui/theme
        ↓ Signal/Slot（不可变对象）
application/（DeviceSession、Playback、Teach、Recorder、Performance、Firmware…）
        ↓
domain/（models、safety、hardware_profile、trajectory、recipe、calibration、dataset、evidence）
        ↓
protocol/（crc8、frame_codec、stream_parser、v1_codec、fixtures）
        ↓
transport/（base、serial_transport、mock、mock_device、discovery）
```

旁路：`model3d/`、`infrastructure/`（config、database、paths、export）只作为适配器，
不反向依赖 GUI。

## 铁律

1. `domain` 不得 import Qt、pyserial、sqlite 连接、STM32 工具、GUI 页面或 model3d。
2. `gui` 页面/ViewModel 不得直接 import pyserial、sqlite 底层连接、协议字节操作。
3. View 不得直接调用业务方法写状态；UI→逻辑必须经过 Signal/Slot 或 ViewModel 方法。
4. 跨线程传递完整不可变对象（`RobotSnapshot`、`SessionEvent`），不共享可变数组。
5. 高频数据用 latest-value；队列必须有界并公开丢弃/拒绝计数。
6. 危险命令（ENABLE/HOME/TEACH/轨迹/夹爪动作）必须经过统一 `CommandService`/`SafetyGate`，
   不允许页面、手柄、终端各写一套。
7. 所有线上关节位置为 int urad；UI 边界才转 deg/rad。

## 模块职责（一句话）

| 模块 | 职责 | 禁止 |
|---|---|---|
| domain/models | 不可变数据模型 | 依赖上层 |
| domain/safety | 纯确定性安全决策（preview/arm/execute） | 弹窗、串口副作用 |
| protocol | 字节编解码与解析 | 依赖 Qt/串口 |
| transport | 打开/关闭/读写/订阅字节与状态事件 | 协议语义 |
| application/device_session | 状态机、单在途、轮询、快照发布 | 直接操作 UI |
| application/playback/teach | 单调调度、录制状态机 | 追赶积压、覆盖 raw |
| gui/viewmodels | 不可变 ViewState、节流渲染 | 阻塞 IO |
| gui/pages | 纯展示与交互收集 | 业务逻辑堆积 |
| infrastructure | SQLite/配置/路径适配 | 被 domain 依赖 |

## 审查清单

按严重度输出问题列表，每条给出文件与行号：

- 主窗口或页面类是否过大（职责 > 2 个）？
- 串口/协议/sqlite 是否泄漏进 View？
- 状态是否散落（多个全局可变单例）？
- 跨线程是否直接调用 Widget 方法（未走 queued signal）？
- 订阅是否在 widget 销毁后取消（幽灵更新）？
- 新模块是否容易测试（seam 是否清晰、是否可注入 fake）？
- 是否用 `setGeometry`/绝对坐标（应使用 layout）？
- 是否绕过 SafetyGate 发送动作命令？
- 是否用 `time.time()` 调度轨迹（应 monotonic）？
- 是否把 V1 缺失字段显示为 0（应 Unknown）？

## 输出格式

```text
架构审查报告
严重 [P0/P1/P2/P3] 违规: 文件:行 — 规则 — 建议
合规确认: 列出检查过的关键边界
```

只报告可执行结论，不重写代码除非用户明确要求。
