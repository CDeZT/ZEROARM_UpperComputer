# ZeroArm Desktop 已知限制

版本：0.1.0  
更新：2026-08-01  
协议运行时：V1 兼容（115200）

本文件随便携包/安装包分发。它**不**表示真实电机动作验收已完成，也**不**表示协议 V2 已实施。

## 1. 协议与硬件

| 限制 | 说明 |
|---|---|
| 协议仅 V1 | GET_STATE 60 字节、单请求在途；V2 审批包已有但未批准实施 |
| 默认波特率 115200 | 高波特率审批包存在，默认不启用 |
| Serial 默认只读 | 真实 ENABLE/DISABLE/STOP/HOME/TEACH/SET_JOINT_TARGET 需单独授权 |
| Partial profile | 可用轴 mask `0x1D`（J1/J3/J4/J5）；J2/J6 为 Unavailable |
| 夹爪动作 | 未标定固定拒绝；只读 Ping/Read 可用 |
| 软件 STOP | 不是物理急停；仅停止 Mock 点动/回放等软件动作 |

## 2. 功能边界

| 限制 | 说明 |
|---|---|
| Cartesian / IK | 离线 ghost 预览为主；不开放真机发送 |
| 手柄输入 | 无真 HID；虚拟映射 / Recipe 回放 |
| 固件页 | 默认 dry-run，不自动刷写 |
| 3D 模型 | 参考 URDF/STL，GPL-2.0 许可证必须随包保留 |
| 用户数据 | 写入 `%LOCALAPPDATA%/ZeroArm Desktop/`（macOS/Linux 为 platformdirs 用户数据目录），不写 Program Files |

## 3. 发布与环境

| 限制 | 说明 |
|---|---|
| 首发平台 | Windows x64；源码跨平台，macOS 打包非本轮验收重点 |
| 干净环境 | 便携包目标：无系统 Python 可启动 Mock 演示 |
| 驱动 | 不静默安装 ST-Link / VCP 驱动 |
| 杀毒/OpenGL | 部分环境可能误报 PyInstaller 产物或缺少 GPU 加速 |

## 4. 延期标签

- `HW-DEFERRED-V2`：等待「确认实施协议 V2」
- `HW-DEFERRED-BAUD`：等待高波特率批准与实测
- `HW-DEFERRED-ACTION`：等待机械安全门与分项动作确认
- `HW-DEFERRED-READONLY-BOARD`：需要真实板卡做只读 soak（已有 2026-08-01 报告样本）
