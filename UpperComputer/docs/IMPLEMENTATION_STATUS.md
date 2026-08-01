# 上位机实施状态

更新时间：2026-08-01

## 当前状态

```text
阶段：0.1.0 离线软件基线已存在，正在迁移到当前 MCU V1
旧版完成记录：单元0～24、27/28/29/32的软件基线
当前计划：V2 R0～R15
最近完成：R0 文档与契约迁移
当前/下一单元：R2 HardwareProfile 与互锁域
当前代码修改：R1 已完成（协议合同/fixture 对齐），本单元已提交
```

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

- MCU 仓库：`C:\Users\Administrator\CLionProjects\zero_arm_mcu`，当前检查基线
  `main` @ `48c11d8`。
- 当前兼容协议仍为 V1：115200、60 字节 GET_STATE、一个请求在途。
- 可用/回零轴：J1、J3、J4、J5，mask `0x1D`；J2/J6 当前 Unavailable。
- HOME 已实现，顺序 J5→J4→J3→J1；20 秒无主机帧且空闲时自动回零。GET_STATE
  同样会重置 MCU 计时，因此 R8 将另建 20 秒无用户动作的 Desktop 主动 HOME。
- PD15 为低有效 E-stop，触发后必须复位。
- J3 0～135°、J4 -90～90°、J5 -35～135°，存在 J3/J4/J5 强制互锁。
- MotionTask 20 ms 是轮询周期，普通目标生产路径不是持续 50 Hz MCU 插值流。
- 调试固件包含台架 `0x20～0x27` 和夹爪 STS `0x30～0x34` 命令。

完整事实见 `21_MCU_CURRENT_BASELINE.md`。

## 状态边界

MCU 的 J1/J3/J4/J5 已有现场动作与自动回零测试，不再描述为“机械臂尚未组装且
所有硬件事实未知”。但 Desktop 当前 Serial 动作路径尚未按新契约逐项验收，因此：

- Mock 成功不能声明真实 Desktop 动作通过。
- MCU 脚本实测不能自动声明 GUI/Session/SafetyGate 的真实动作路径通过。
- 后续只在 R6/R7/R8/R10/R11/R12/R13 对应范围和本轮授权内发送动作。
- J2/J6 不进入当前真实动作范围；夹爪未安装/标定时只开放只读诊断。

## 当前待办

1. R1：让上位机协议合同/fixture 覆盖当前 result、fault、bench 和 gripper 命令。**已完成（2026-08-01）**。
2. R2：建立 partial HardwareProfile、Unavailable 轴和 J3/J4/J5 路径约束。
3. R3～R5：升级 Mock、完成真实只读板测和 GUI 状态迁移。
4. R6 以后：按 HOME、手动控制、Desktop空闲/退出回零、轨迹、示教、夹爪逐项验收。

## 保持独立的未来路线

- 协议 V2：审批包仅为提案，未批准实施。
- 高波特率：默认仍为 115200。
- TCP/MQTT、联网发布、模型策略真实控制：不阻塞当前 V1 主线，另行规划和授权。

## 工作区保护

仓库当前已有 `.idea` 修改和未跟踪文件，它们不是本轮规划内容，不清理、不覆盖、
不提交。后续单元每轮必须重新运行 `git status --short`。
