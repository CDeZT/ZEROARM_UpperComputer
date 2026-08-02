# 上位机实施状态

更新时间：2026-08-02

**新 Agent 交接全文**：`AGENT_HANDOFF_2026-08-01-LATE.md`（路径、进度、启动句、已知问题）。

## 当前状态

```text
阶段：0.1.0 离线软件基线 + 当前 MCU V1 迁移主路径已通（Mock GUI 可演示）
旧版完成记录：单元0～24、27/28/29/32的软件基线
当前计划：V2 R0～R15
最近完成：2026-08-02 全项目缺陷整治（安全、会话、Recorder、分层、异步示教、UI/UX）
当前/下一单元：剩余 P1/P2 见 `PROJECT_AUDIT_2026-08-02.md`；真实 Serial 动作与 Windows 发布仍须专项授权/环境
最近代码 tip：63c52b5 — 文档提交后以 git log 现场为准
验证基线：pytest 294 passed / 4 skipped，coverage 89%；ruff format/check / mypy 全过
```

## 全项目缺陷整治（2026-08-02）

- 安全：连续点动/回放/示教期间禁止空闲 HOME；全局软件 STOP 停止本地调度并在授权会话发送 V1 STOP。
- 会话：请求超时、有限重连、`UnknownOutcome`、异步 `ActionRequest`、紧急 STOP 写队列优先级。
- 存储：测试数据根目录隔离；Recorder 的启动/工作线程 SQLite 故障会停止录制并反馈到 GUI。
- 架构：领域层不再依赖应用/协议等外层；Shell 不再绕过 `CommandService` 直发 HOME；移除重复旧主窗口。
- 退出：受控回零改为 QTimer 驱动，不再阻塞 GUI；等待链路空闲、经 SafetyGate HOME、持续观察 `homed 0x1D`，超时须确认。
- 示教：TEACH_START/STOP 等待异步 ACK；STOP 额外等待失能状态快照；跨线程快照经 Qt Signal 回 GUI 线程。
- UI/UX：导航可滚动、Dashboard 卡片化、浅色曲线主题修复、动作锁定原因前置、危险动作语义色、连接可取消。
- 原子提交：`b4ceec9`、`f222904`、`341aa05`、`cb2d0c0`、`065bc36`、`58909c3`、`63c52b5`。
- 最终覆盖率：89%（6661 statements，765 missed）；低覆盖模块与剩余产品缺口见专项审计。
- 未连接板卡、未发送真实动作、未改 MCU、未实施协议 V2。

## R15 完成记录（2026-08-02，macOS 可做部分）

- `build_portable.py --dry-run` 冒烟通过：8 项必需清单齐全（spec/iss/许可/manifest/文档），
  输出明确提示 Windows 为推荐构建主机。
- R15 半成品质量门修复并原子提交：`adbc738`（打包/GUI 修复）、`b47cb3b`（交接/验收文档）。
- Codex 工具链提交：`62b6d6a`（6 个项目级技能 + .gitignore）。
- 全页 UI 审查与修复提交：`9014466`（快捷键 Ctrl+D/Space、连接页状态机、轨迹页只读化、
  六轴曲线选择器等，详见 `docs/UI_REVIEW_2026-08-01.md`）；新增 3 个快捷键测试。
- qt-docs MCP 实测：**不覆盖 PySide6**，结论已写入 `docs/CODEX_TOOL_INVESTIGATION_REPORT.md` §11.5。
- 提交：`d92926b`（实测结论文档）。
- 未做（需 Windows 真机）：PyInstaller 实际构建、无 Python 环境启动烟雾、
  Inno 安装/升级/卸载实测、发布包 SHA256SUMS 真机核对。

## R14 + GUI 成品化完成记录

- `domain/evidence.py`：`OperationEvidence` + 有界 `EvidenceLog` JSON 导出。
- `application/session_recording.py`：连接生命周期绑定 SQLite `Recorder`，快照/事件入队。
- `application/performance.py`：链路 Hz / poll_coalesced / recorder drop 采样。
- 轨迹：`load/import/export` JSON；示教「另存」自动加载到轨迹编辑器。
- Recipe：准备后展开为轨迹并走 Mock 回放（SafetyGate）。
- 数据集：从示教 raw 生成 Episode 再导出。
- 标定页：对齐 HOME 0x1D / profile，去掉假 NOT_CONFIGURED 按钮。
- 诊断页：Recorder 统计 + Evidence 导出；Dashboard 会话指标。
- 测试：product flow / evidence / session recording；ruff/mypy/pytest 本轮验证。
- 硬件：未连接、未发动作命令。

## R11～R13 完成记录（示教 + 夹爪/台架只读）

- R11 示教：`TeachViewModel` 走 `SafetyGate` `GRAVITY_RELEASE`（支撑确认、可用轴 mask
  0x1D、状态互斥）；`TeachRecorder` IDLE/ARMED/RECORDING/REVIEW；TEACH_STOP 后失能复核
  且不自动 ENABLE；raw 另存轨迹带 `parent_raw_sha256`。Mock 拒绝 J2/J6/空 mask。
- R12 夹爪：`DeviceSession.send_gripper_ping/read` 只读（Serial 亦可用）；动作门固定
  `gripper_not_calibrated`；GUI `夹爪/台架只读` 页。
- R13 台架：`send_bench_query/get_protection` + 协议终端白名单；命令审计；Mock 返回
  fixture 黄金响应；禁止任意 HEX 透传。
- 测试：teach/gripper GUI E2E + mock 语义；ruff/mypy 通过；pytest 254 passed / 4 skipped
  （`test_assets` 因本机 `licenses/GPL-2.0.txt` 完整性与 manifest 不一致预存失败，与本轮无关）。
- 硬件：未连接板卡、未发送动作命令；真实示教/夹爪动作仍需单独授权。

## R10 完成记录（真实轨迹回放 V1 语义）

- `application/playback.py`：`MIN_SEND_INTERVAL_NS=20ms`（Desktop 50Hz 主机限频）、
  `PlaybackSupervisor`（逐点完成观察：moving==0 且 |actual-target|≤35_000 urad →
  completed；故障或 2s 超时 → faulted/unknown_outcome，不自动重发）、
  `PlaybackEvidence`（playback_id/点索引/发送时间/目标/result/快照代数/outcome）。
- `gui/viewmodels/trajectory.py`：回放启动与每个点都走 `CommandService/SafetyGate`
  （TRAJECTORY 家族 + 逐点 JOINT_TARGET preview/arm/execute）；回放期间暂停轮询
  占用单在途请求槽，发送后主动 GET_STATE 推进，结束/中止后恢复轮询；证据记录
  accepted → completed/unknown_outcome。
- `application/device_session.py`：新增 `resume_polling()`（与 R8 的 `pause_polling()` 对称）。
- `gui/pages/trajectory.py`：状态栏显示 evidence 数量与 abort reason。
- `gui/shell.py`：模式切换接线 `trajectory_view_model.set_mode`。
- 测试：纯引擎 50Hz latest-target（20ms 内多个到期点只发最新、不 burst）、
  Supervisor completed/faulted/unknown_outcome；GUI Mock E2E 回放完整轨迹并核对证据
  与轮询恢复；pytest 全量 250 passed / 4 skipped；ruff/mypy 通过。
- 硬件：本轮未连接板卡、未发送动作命令；真实轨迹回放仍需单独授权。

## R9 完成记录（轨迹/Cartesian 逐点约束迁移）

- `domain/trajectory.py`：`validate_trajectory` 从旧 `JointModelMapping.validate_robot_limits`
  切换为 `HardwareProfile + InterlockPolicy + PathValidator`；每个轨迹点执行 profile
  范围/不可用轴/互锁目标校验，相邻点执行过渡校验，并保留时间单调、速度、gripper 范围检查。
  新增 `require_partial_profile_points`（J2/J6 非零即拒绝）与
  `PARTIAL_PROFILE_UNAVAILABLE_AXES`，明确 partial profile 轨迹格式。
- `domain/hardware_profile.py`：`PathValidator` 升级——每个点都做互锁目标校验（此前只做
  相邻过渡），新增 `PathIssue`（point_index/code/joint_index/detail），`PathValidation`
  保留 `errors`/`reasons()` 兼容接口；detail 包含具体角度与阈值。
- `domain/recipe.py`：`expand_recipe_to_points` 默认位姿 J2 对齐 partial profile（置 0）。
- GUI：轨迹页新增 `trajectory_constraint_report` 详细约束报告（点/关节/阈值），
  状态栏验证文本显示前 4 项带位置的问题。
- 验证：危险中间点（终点合法仍拒绝）、降 J3 未清障、J2/J6 非零、J1 continuous
  大值、单点互锁违规、detail 报告均有测试；ruff/mypy 通过；pytest 全量
  247 passed / 4 skipped。

## R8 完成记录（自动回零与受控退出）

- 生产文件：`src/zeroarm_desktop/gui/viewmodels/idle_monitor.py`（新增）：
  `OperatorIdleHomeMonitor`——Desktop operator-idle 20 秒倒计时（500ms tick），
  到点且会话动作授权（Mock）→ `HomeViewModel.start_home()` 走 SafetyGate；
  Serial 只读 → "跳过"提示；GET_STATE 轮询不重置此计时器（与 MCU link-silence 区分）。
- `src/zeroarm_desktop/gui/shell.py`：接线 idle_monitor、状态栏自动回零倒计时、
  `closeEvent` 受控退出：RESET-REQUIRED 故障 → 确认后退出（默认 QMessageBox，
  可通过 `confirm_fault_exit` 注入以便自动化测试确定性退出）；Mock 未回零 →
  暂停轮询 → HOME 0x1D → 有界等待（≤5s）→ 证据记录后断开。
- `src/zeroarm_desktop/application/device_session.py`：新增 `pause_polling()`，
  受控退出前停止后台轮询线程，消除单在途请求与动作命令的竞态。
- 测试：`tests/gui/test_idle_shutdown.py`（新增 6 个测试）；`test_dashboard_monitor.py`
  与 `test_home_page.py` 的故障用例注入确定性退出确认。
- 挂起问题修复：R8 引入后 `tests/gui/test_dashboard_monitor.py` 在 teardown 的
  `closeEvent` 中弹出模态 `QMessageBox.warning`（STARTUP/ESTOP 故障路径），
  offscreen 环境无用户点击导致进程挂死/崩溃；修复为可注入确认回调后
  `tests/gui` 36 passed（5.0s）。
- 验证：ruff format/check 通过；mypy 通过；pytest 全量 241 passed / 4 skipped。
- 硬件：本轮未连接板卡、未发送任何动作命令；受控退出仅在 Mock 上验收。

## R7 完成记录（手动关节 Mock 控制）

- `gui/viewmodels/manual_joint.py`：轴下拉仅 J1/J3/J4/J5（available_axes）；
  J2/J6 preview 抛 ValueError；发送后 completion 观察（moving==0 且
  |error|≤35_000 urad → "目标到达"；5s 超时 → "UnknownOutcome"）。
- `gui/pages/manual_joint.py`：preview/arm/send 三步按钮、hold-to-run（仅 Mock）。
- 测试：`tests/gui/test_manual_joint.py` 9 个（轴过滤/互锁拒绝/到达/Mock E2E/
  Observer 拒绝/失焦撤销/全局停止）。
- 提交：`06fb8d7`。

## R6 完成记录（HOME 0x1D 向导）

- `gui/viewmodels/home.py`：`HomeViewModel`——start_home 走 SafetyGate
  （mask 0x1D）、clear_fault（FAULT_CLEAR 族，允许 FAULT 状态）、100ms 进度监控
  （HOMED 完整 → 完成；fault → RESET-REQUIRED 提示）。
- `gui/pages/home.py`：向导页（固定顺序 J5 → J4 → J3 → J1、进度、清除故障按钮）。
- `DeviceSession` 动作 API：send_enable/send_disable/send_stop/send_home/
  send_clear_fault（Serial 由 actions_allowed=False 拒绝）。
- 提交：`5787ff4`。

## R2 完成记录（HardwareProfile 与互锁域）

- 生产文件：`src/zeroarm_desktop/domain/hardware_profile.py`（新增）：`HardwareProfile`
  （`zeroarm_g474_v1_partial`：J1 continuous、J2/J6 Unavailable、J3 0-135°、J4 -90-90°、
  J5 -35-135°，mask 0x1D）、`JointCapability`、`InterlockPolicy`（MCU `joint_config.c`
  端点/过渡语义精确复刻）、`PathValidator`（逐点+相邻过渡校验）、`evaluate_readiness`
  （运动授权/回零完整/故障分类）。
- `domain/safety.py` 改用 profile+policy（移除对 model3d 的反向依赖）；`model3d/joint_mapping.py`
  的 robot 范围对齐新契约；示例数据（轨迹/食谱/数据集/台架 ghost）统一 J2=0。
- 验证：J2/J6 非零必拒绝、J1 continuous、J3/J4/J5 边界、降 J3 顺序（J4 居中/J5 收回）、
  危险中间点拒绝；pytest 全量 207 passed（R2 提交时）。
- 提交：`05e5921`。

## R3 完成记录（Mock 语义升级）

- `transport/mock_device.py` 重写：启动限位门（0x1D，FAULT_STARTUP）、有序 HOME
  （J5→J4→J3→J1，HOMING 期间未授权）、E-stop 锁存（reset-required，仅 `simulate_reset` 解除）、
  20 秒无帧自动回零（虚拟时钟 `advance_time_ms`，deterministic）、J2/J6 非零目标 ERR_RANGE、
  ENABLE/DISABLE/STOP/CLEAR_FAULT 全语义、TEACH 未授权、运动期间 run_state 保持 READY
  （moving_mask 表达，与 MCU 一致）。
- `transport/mock.py`：`MockSettings` 扩展 + `transport.device` 暴露注入点。
- 测试：`tests/transport/test_mock_mcu_semantics.py`（14 个语义测试）。
- 提交：`109c5d8`。

## R4 完成记录（Serial 只读板卡验收）

- 工具：`tools/readonly_board_report.py`（HELLO/GET_STATE 只读 soak + 命令审计 + fixture
  语义匹配报告）；`DeviceSession.parser_statistics` 暴露。
- 实测（2026-08-01，COM3 ST-Link VCP，板载固件）：
  - HELLO `ZEROARM/1.0` 成功；60 秒 soak：429 snapshots、0 CRC/长度/噪声错误、
    0 unexpected frames；`fixture_semantics_match = V1-STATE-READY-HOMED-1D`
    （run_state READY、fault 0、homed_mask 0x1D）——R1 黄金帧得到实机验证。
  - 命令审计：仅 HELLO×1 + GET_STATE×430，动作命令 0。
  - 报告：`docs/reports/readonly_board_20260801.json`。
- 提交：`3856b82`、`3ba0495`。

## R5 完成记录（连接/Dashboard/Monitor 迁移）

- `gui/viewmodels/snapshot.py`：`SnapshotViewState` 增加 readiness/fault 名称/未知位/
  Unavailable 轴/新鲜度/自动回零警告；run_state 用 V1RunState 枚举。
- `gui/pages/dashboard.py`：profile/readiness（运动授权/回零/RESET-REQUIRED）/故障位
  名称+未知位/新鲜度/自动回零提示；J2/J6 显示 Unavailable。
- `gui/pages/joint_monitor.py`：Unavailable 轴行标记。
- 测试覆盖：正常启动门（READY/授权/未回零警告）、STARTUP fault、ESTOP fault、
  unknown run_state/fault 位、freshness。
- 提交：`66444ce`。

## 现有 0.1.0 可复用资产

## R1 完成记录（2026-08-01）

- 范围：当前 V1 Codec 与 fixture 对齐（命令枚举、result/fault 解码、台架/夹爪合同、当前板卡 fixture）。
- 生产文件：`src/zeroarm_desktop/protocol/v1_codec.py`（新增 `V1BenchCommand`、`V1GripperCommand`、
  `V1FaultFlag`、`RESET_REQUIRED_FAULTS`、`decode_fault_flags`、`V1GripperResultCode`、
  `BenchState`、`MotorProtection`、`GripperResponse` 及 bench/gripper 全部编解码方法）、
  `src/zeroarm_desktop/protocol/fixtures.py`（7→29 个黄金帧，含 GET_STATE 三种状态、
  HOME 0x1D、28B 目标、台架 8 帧、夹爪 6 帧；`FIXTURE_SHA256` 登记全部帧哈希）。
- 测试：`tests/protocol/test_v1_fixture_hashes.py`（新增，哈希/解析/长度），
  `tests/protocol/test_v1_codec.py`（扩展 bench/gripper/fault/fixture 用例）。
- 证据：ruff format/check 通过；mypy 通过；pytest 全量 186 passed / 4 skipped
  （旧基线 136）。
- MCU 依据：`zero_arm_mcu` `main` @ `48c11d8`（Protocol/Robot/Config/Motor/Gripper 源码逐文件核验）。
- 硬件：未连接；只读板测未运行（`not_run`：本轮无板卡）。未发送任何动作命令。
- 已知限制：fixture 按 MCU 源码+上位机 CRC 构造，尚未经实机抓帧逐字节复核（R4 板测时核对）。

## 现有 0.1.0 可复用资产

- Python 3.12/3.13、PySide6、src layout、uv、ruff、mypy、pytest 工程已建立。
- CRC8、V1 frame/stream parser、V1 Codec、Mock/Serial Transport、DeviceSession 已存在。
- SQLite Recorder、CSV/JSON、完整 GUI 壳、Dashboard、六轴监控已存在。
- URDF/STL、关节映射、FK/IK、actual/ghost 3D 工作区已存在。
- SafetyGate、Mock 手动控制、轨迹编辑/回放、Mock 示教、Recipe、数据集接口已存在。
- 诊断、受限协议终端、固件 dry-run、PyInstaller 和 Inno Setup 资产已存在。
- 旧状态记录为全量 136 pytest passed；代码开发恢复时必须现场重新运行，不能把旧数字
  当成当前验证结果。

## 当前 MCU 事实

- MCU **不在**本仓；路径按机器：
  - Win 文档基线：`C:\Users\Administrator\CLionProjects\zero_arm_mcu`
  - 当前 macOS 开发机：`/Users/wangzilin/STM32Cube/zero_arm_mcu`
- 协议核验基线曾用：`main` @ `48c11d8`（以本机 MCU `git rev-parse HEAD` 为准）。
- 当前兼容协议仍为 V1：115200、60 字节 GET_STATE、一个请求在途。
- 可用/回零轴：J1、J3、J4、J5，mask `0x1D`；J2/J6 当前 Unavailable。
- HOME 已实现，顺序 J5→J4→J3→J1；20 秒无主机帧且空闲时自动回零。GET_STATE
  同样会重置 MCU 计时；Desktop 另有 20 秒无操作者动作的主动 HOME（R8）。
- PD15 为低有效 E-stop，触发后必须复位。
- J3 0～135°、J4 -90～90°、J5 -35～135°，存在 J3/J4/J5 强制互锁。
- MotionTask 20 ms 是轮询周期，普通目标生产路径不是持续 50 Hz MCU 插值流。
- 调试固件包含台架 `0x20～0x27` 和夹爪 STS `0x30～0x34` 命令。

## 状态边界

MCU 的 J1/J3/J4/J5 已有现场动作与自动回零测试，不再描述为“机械臂尚未组装且
所有硬件事实未知”。但 Desktop 当前 Serial 动作路径尚未按新契约逐项验收，因此：

- Mock 成功不能声明真实 Desktop 动作通过。
- MCU 脚本实测不能自动声明 GUI/Session/SafetyGate 的真实动作路径通过。
- 后续只在 R6/R7/R8/R10/R11/R12/R13 对应范围和本轮授权内发送动作。
- J2/J6 不进入当前真实动作范围；夹爪未安装/标定时只开放只读诊断。

## 当前待办

1. R1：协议合同/fixture 覆盖 result、fault、bench、gripper。**已完成（2026-08-01）**。
2. R2：HardwareProfile、Unavailable 轴和 J3/J4/J5 路径约束。**已完成（2026-08-01）**。
3. R3：Mock 当前 MCU 语义升级。**已完成（2026-08-01）**。
4. R4：Serial 只读板卡验收。**已完成（2026-08-01，COM3 实测通过）**。
5. R5：连接/Dashboard/Monitor GUI 状态迁移。**已完成（2026-08-01）**。
6. R6：HOME 0x1D 向导。**已完成（2026-08-01，Mock E2E）**。
7. R7：手动关节控制（仅可用轴 + completion 观察）。**已完成（2026-08-01，Mock）**。
8. R8：Desktop 空闲回零 + 受控退出。**已完成（2026-08-01，Mock）**。
9. R9：轨迹逐点约束。**已完成**。
10. R10：真实轨迹回放语义。**已完成**。
11. R11：真实示教。**已完成（2026-08-01，Mock E2E）**。
12. R12：夹爪只读诊断。**已完成（2026-08-01，Mock）**。
13. R13：台架/协议终端只读。**已完成（2026-08-01，Mock）**。
14. R14：数据/性能 + GUI 成品化接线。**已完成（2026-08-01，Mock）**。
15. R15：打包/发布刷新。**代码完成（2026-08-02，macOS dry-run 冒烟通过）；Windows 真机构建/安装验收待做（真实动作类仍需单独授权）**。

## 保持独立的未来路线

- 协议 V2：审批包仅为提案，未批准实施。
- 高波特率：默认仍为 115200。
- TCP/MQTT、联网发布、模型策略真实控制：不阻塞当前 V1 主线，另行规划和授权。

## 工作区保护

常见勿提交：`.idea/`、`.DS_Store`、根目录本机 `MCU 源码路径.md`。  
它们不是功能交付内容，不清理、不覆盖、不提交。每轮开始必须 `git status --short`。

## 给下一 Agent 的停止点

- **现在停在 R15 代码完成 / Windows 真机构建验收之前。**
- 不要重做 R1～R15 代码，除非回归失败。
- 用户换 Agent 时优先读 `AGENT_HANDOFF_2026-08-01-LATE.md` 与本文件顶部。
