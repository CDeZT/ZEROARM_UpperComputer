# 上位机 Agent 交接（2026-08-01）

面向**下一个编码 Agent**。先读本文 + `IMPLEMENTATION_STATUS.md`，再动手。

## 1. 仓库与分支

| 项 | 值 |
|---|---|
| 上位机仓 | 本仓库 `ZEROARM_UpperComputer`，主目录 `UpperComputer/` |
| 分支 | `master` |
| 最新提交（交接时） | `cff0480` `feat(gui): wire session recording, evidence, and product page flows` |
| 远程 | `origin/master` 已含 R1～R14 |

交接前请现场执行：

```bash
git status --short
git log --oneline -10
cd UpperComputer && uv sync --locked && uv run pytest -q
```

## 2. 当前进度（事实）

```text
已完成：旧单元 0～24/27/28/29/32 软件基线
已完成：V1 迁移 R1～R14（含 Mock GUI 成品化接线）
下一单元：R15 打包/发布刷新（便携包烟雾、能力矩阵、干净环境启动）
协议 V2：pending，禁止在用户说「确认实施协议 V2」前改 MCU
真实动作：Serial 默认只读；Mock 可走动作；真机需单独授权
```

### R 计划完成表

| 单元 | 内容 | 状态 |
|---|---|---|
| R1 | V1 codec/fixture（含 bench/gripper） | 完成 |
| R2 | HardwareProfile / 互锁 / Unavailable 轴 | 完成 |
| R3 | Mock MCU 语义 | 完成 |
| R4 | Serial 只读板测工具与报告 | 完成（Win COM3 曾实测） |
| R5 | Dashboard/Monitor readiness | 完成 |
| R6 | HOME 0x1D 向导 | 完成（Mock） |
| R7 | 手动关节可用轴 + completion | 完成（Mock） |
| R8 | 空闲回零 + 受控退出 | 完成（Mock） |
| R9 | 轨迹逐点约束 | 完成 |
| R10 | 轨迹回放 ≤50Hz + evidence | 完成（Mock） |
| R11 | 示教 SafetyGate + raw/review | 完成（Mock） |
| R12 | 夹爪只读 Ping/Read | 完成 |
| R13 | 台架 Query + 协议终端白名单 | 完成 |
| R14 | 会话录制 / Evidence / 性能 / 页面接线 | 完成 |
| **R15** | **打包发布刷新** | **下一单元** |

## 3. 本机路径（按机器区分）

### 3.1 当前 macOS 开发机（交接现场）

| 用途 | 路径 |
|---|---|
| 上位机仓库 | `/Users/wangzilin/PycharmProjects/ZEROARM_UpperComputer` |
| MCU 源码（本机检出） | `/Users/wangzilin/STM32Cube/zero_arm_mcu` |
| 本地备忘（**未入库**） | 根目录 `MCU 源码路径.md` → 指向本机 MCU；**勿提交** |

### 3.2 文档中的 Windows 基线（历史交接）

| 用途 | 路径 |
|---|---|
| MCU（Win 交接原文） | `C:\Users\Administrator\CLionProjects\zero_arm_mcu` |
| 只读板测报告 | `UpperComputer/docs/reports/readonly_board_20260801.json` |

**注意**：仓库文档里的 Windows MCU 路径与本机 macOS 路径是**两台机器上的两份检出**，不是同一路径。以当前机器实际存在的目录为准。

## 4. 产品/硬件契约（不可忘）

- 协议：**仅 V1**（115200，单请求在途，GET_STATE 60B）。
- Profile：`zeroarm_g474_v1_partial`，可用轴 mask **`0x1D`**（J1/J3/J4/J5）。
- **J2/J6 Unavailable**，非零目标必须拒绝。
- HOME 顺序：**J5 → J4 → J3 → J1**；MCU 20s 无帧可自动回零；Desktop 另有 20s 操作者空闲回零。
- 域内关节单位：**int urad**。
- Serial：**禁止默认动作命令**；夹爪/台架只读诊断允许。
- 夹爪动作：未标定固定拒绝（`gripper_not_calibrated`）。

## 5. Mock GUI 已可演示路径

```text
连接 Mock → Operator
 → 回零向导 / 标定页 HOME
 → 手动关节（预览/Arm/发送/按住点动）
 → 轨迹验证/回放/导入导出
 → 示教（支撑确认→Arm→录制→Review→另存→自动进轨迹编辑器）
 → Recipe 验证并 Mock 回放
 → 数据集从示教生成 Episode
 → 夹爪/台架只读
 → 诊断（Recorder + Evidence 导出）
 → Dashboard 会话 Hz/drop 指标
```

启动：

```bash
cd UpperComputer
uv sync --locked
uv run python -m zeroarm_desktop
# 质量门
uv run ruff format --check .
uv run ruff check .
uv run mypy
uv run pytest -q
```

## 6. 关键源码地图

```text
src/zeroarm_desktop/
  domain/          hardware_profile, safety, trajectory, evidence, recipe, dataset
  protocol/        v1_codec, fixtures, stream_parser
  transport/       mock_device（MCU 语义）, serial_transport
  application/     device_session, playback, teach, recorder, session_recording,
                   performance, recipe_runner
  gui/shell.py     导航与全局接线
  gui/pages/       全部功能页
  gui/viewmodels/  home, manual_joint, trajectory, teach, snapshot, idle_monitor
```

## 7. 已知限制 / 脏文件

- `tests/model3d/test_assets.py`：本机 `resources/robot_model/licenses/GPL-2.0.txt` 与 manifest 哈希可能不一致（预存）；全量 pytest 时可用 `--ignore=tests/model3d/test_assets.py` 或先修资产哈希。
- 工作区常见**勿提交**项：`.idea/`、`.DS_Store`、根目录 `MCU 源码路径.md`（本地路径备忘）。
- Cartesian 仍以离线 IK + ghost 为主；固件页 dry-run；手柄无真 HID（虚拟映射/Recipe 回放）。
- 真实 Serial 动作、示教松轴、协议 V2、高波特率均需用户明确授权。

## 8. 下一 Agent 建议任务

1. **R15（优先）**：刷新/验证 Windows 便携包（`packaging/`）、无系统 Python 烟雾、资源与会话库路径、能力矩阵与 `20_RELEASE_ACCEPTANCE.md` 勾选。
2. 可选：修复 robot_model 资产哈希使 `test_assets` 绿。
3. 可选：固件页进度 UI、Cartesian RPY/多解、手柄真输入——不阻塞 R15。
4. 仅当用户说 **「确认实施协议 V2」** 才进入 MCU 协议实施。

## 9. 一句话启动（复制给新 Agent）

```text
读取 UpperComputer/docs/AGENT_HANDOFF_2026-08-01.md 与 IMPLEMENTATION_STATUS.md，以 git 最新 master 为准；从 R15 打包/发布刷新开始，遵守 AGENTS.md 与 SafetyGate，保持 V1 兼容，不把 V2 当已实现，Serial 默认只读、不执行未授权真实动作；完成实现、测试、文档与独立提交后停止报告。
```

## 10. 必读清单（顺序）

1. 本文  
2. `IMPLEMENTATION_STATUS.md`  
3. `UpperComputer/AGENTS.md`  
4. `PROJECT_SPEC.yaml`  
5. `17_API_DATA_AND_FIXTURE_CONTRACTS.md`（改接口时）  
6. 当前单元相关页（R15 → `08_PACKAGING_RELEASE_OPERATIONS.md`、`20_RELEASE_ACCEPTANCE.md`）  
7. 涉及协议时：本机 MCU `Protocol/` + 文档 V1 事实，**不要**用 V2 提案字段  
