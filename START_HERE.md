# ZEROARM 工作交接入口

更新时间：2026-08-01

## 1. 交付范围

本交接包同时覆盖两个后续工作流：

1. ZeroArm 桌面上位机（`UpperComputer/`）委托开发与发布。
2. `zero_arm_mcu` 固件审计、修复与实机验收（源码在**独立 MCU 仓库**）。

上位机和 MCU 可并行，但必须共享当前 **V1 协议事实**。协议 V2 仍是提案；任何一侧都不能把提案字段当成已存在能力。

## 2. 上位机入口（优先）

```text
UpperComputer/
├── README.md
├── AGENTS.md
├── PROJECT_SPEC.yaml
├── README_DEVELOPMENT.md
└── docs/
    ├── AGENT_HANDOFF_2026-08-01.md   ← 新 Agent 先读
    ├── IMPLEMENTATION_STATUS.md     ← 现场进度基线
    └── ...
```

### 2.1 新 Agent 必读顺序

1. `UpperComputer/docs/AGENT_HANDOFF_2026-08-01.md`
2. `UpperComputer/docs/IMPLEMENTATION_STATUS.md`
3. `UpperComputer/AGENTS.md`
4. `UpperComputer/PROJECT_SPEC.yaml`
5. 当前单元相关文档（见交接文第 10 节）

### 2.2 一句话启动上位机

```text
读取 UpperComputer/docs/AGENT_HANDOFF_2026-08-01.md 与 IMPLEMENTATION_STATUS.md，以 git 最新 master 为准；从 R15 打包/发布刷新开始，遵守 AGENTS.md 与 SafetyGate，保持 V1 兼容，不把 V2 当已实现，Serial 默认只读、不执行未授权真实动作；完成实现、测试、文档与独立提交后停止报告。
```

### 2.3 当前上位机事实（2026-08-01）

| 项 | 状态 |
|---|---|
| 技术栈 | Python ≥3.12,<3.14 + PySide6 + uv |
| Transport | Mock + Serial（首发）；TCP/MQTT 未做 |
| 协议 | **仅 V1**；V2 审批包已有，**未批准实施 |
| 旧主线 | 单元 0～24 / 27 / 28 / 29 / 32 软件基线已有 |
| V1 迁移 | **R1～R14 已完成**（见 IMPLEMENTATION_STATUS） |
| **下一单元** | **R15 打包/发布刷新** |
| Mock GUI | 连接→回零→手动→轨迹→示教→Recipe→数据集→诊断 可演示 |
| Serial | 默认只读；夹爪/台架只读诊断可用 |
| 真机动作 | **blocked**，需用户按安全门单独授权 |
| 最新提交 | `cff0480`（以 `git log` 现场为准） |

启动与质量门：

```bash
cd UpperComputer
uv sync --locked
uv run python -m zeroarm_desktop
uv run ruff check . && uv run mypy && uv run pytest -q
```

## 3. MCU 入口

MCU **不在**本仓库源码树内，交接资料：

```text
handoff/2026-07-28/
├── ZEROARM_MCU_HANDOFF_V2.md
├── ZEROARM_MCU_AGENT_INSTRUCTIONS_V2.md
└── ZEROARM_MCU_HANDOFF_STATUS_V2.yaml

docx/Reference_plan/
├── ZEROARM_MCU_FIRMWARE_DESIGN_V1.md
├── ZEROARM_MCU_FIRMWARE_CODE_REFERENCE_V1.md
├── ZEROARM_MCU_AUDIT_REMEDIATION_MASTER_PLAN_V2.md
└── ZEROARM_MCU_AUDIT_MATRIX_V2.yaml
```

### 3.1 MCU 源码路径（按机器）

| 环境 | 路径 | 说明 |
|---|---|---|
| 文档/Win 历史基线 | `C:\Users\Administrator\CLionProjects\zero_arm_mcu` | 交接原文 |
| 当前 macOS 开发机 | `/Users/wangzilin/STM32Cube/zero_arm_mcu` | 本机检出；本地备忘文件**未入库** |

以**当前机器实际存在的目录**为准，不要假设仓库内有一份 MCU 源码。

一句话继续 MCU：

```text
读取 handoff/2026-07-28 和 docx/Reference_plan，以本机 MCU 源码、git status 和现场测试为准，从 next_defect 逐项修复；每缺陷独立提交与回归，不夹带 dirty，不执行机械动作。
```

## 4. 参考 3D 资产

运行时资产已在 `UpperComputer/resources/robot_model/`（带 manifest）。  
参考工程体积大，默认不整仓复制；禁止依赖桌面绝对路径运行产品。

历史候选（Windows）：

```text
C:\Users\Administrator\Downloads\zero-robotic-arm-master
C:\Users\Administrator\CLionProjects\zero_arm_mcu\docx\Reference_project\zero-robotic-arm-master
```

## 5. 安全结论

- 部分轴（J1/J3/J4/J5）在 MCU 侧曾有现场动作测试；**Desktop Serial 动作路径仍未按新契约全面验收**。
- 默认可：Mock 全流程、HELLO、GET_STATE、夹爪/台架只读、烧录 verify（无动作）。
- 默认不可：真实 ENABLE / DISABLE / STOP / HOME / TEACH / SET_JOINT_TARGET / 轨迹动作。
- 协议 V2、高波特率、真机示教松轴均需用户明确确认。

## 6. 工作区注意

- 勿提交：`.idea/`、`.DS_Store`、本机 `MCU 源码路径.md`。
- 资产测试：`tests/model3d/test_assets.py` 可能因 license 文件哈希与 manifest 不一致失败（预存问题）。
- 用户偏好：中文交流；完成任务后可独立 commit（按用户规则）；不 force push。
