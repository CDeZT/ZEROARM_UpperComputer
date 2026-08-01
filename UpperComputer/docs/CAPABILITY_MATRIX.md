# ZeroArm Desktop 能力矩阵（R15）

版本：0.1.0  
更新：2026-08-01

图例：`full` 完整可用 · `mock` 仅 Mock · `readonly` 只读 · `offline` 离线预览 · `deferred` 延期

| 能力 | Mock | Serial | 备注 |
|---|---|---|---|
| 连接 / HELLO / GET_STATE | full | full | V1 兼容 |
| Dashboard / 六轴监控 readiness | full | full | partial profile 0x1D |
| HOME 0x1D 向导 | mock | deferred | Serial 动作需授权 |
| 手动关节 preview/arm/send/hold | mock | deferred | 仅可用轴 J1/J3/J4/J5 |
| 操作者空闲回零 + 受控退出 | mock | readonly skip | Serial 跳过动作 |
| 轨迹约束 / 导入导出 | full | full(验证) | 逐点 partial profile |
| 轨迹回放 ≤50Hz + evidence | mock | deferred | 主机限频 20ms |
| 示教 SafetyGate + raw/review | mock | deferred | 不自动 ENABLE |
| 夹爪 Ping/Read | full | readonly | 动作固定 not_calibrated |
| 台架 Query / 协议终端白名单 | full | readonly | 禁止任意 HEX 透传 |
| Cartesian IK | offline | offline | ghost 预览 |
| 手柄 / Recipe | mock | deferred | 无真 HID |
| 数据集 Episode 导出 | full | full | 从示教 raw 生成 |
| 会话录制 / Evidence / 性能采样 | full | full | SQLite + JSON |
| 固件升级 | dry-run | dry-run | 不自动刷写 |
| Windows 便携包 | packaging | packaging | 无系统 Python 目标 |
| 安装包 (Inno) | packaging | packaging | 需本机 Inno 编译 |
| 协议 V2 | deferred | deferred | 待用户确认口令 |
| 高波特率 | deferred | deferred | 默认 115200 |

## 发布验收勾选（软件）

```text
[x] R1～R14 Mock 主路径可演示
[x] 打包脚本 / Inno 定义 / 许可证清单存在
[x] 用户指南与已知限制文档存在
[x] 能力矩阵存在
[ ] Windows 干净环境无系统 Python 启动烟雾（需 Windows 机）
[ ] 安装/升级/卸载保留用户数据（需 Inno 编译后实测）
[ ] 清单哈希已记录于实际 dist 产物
[ ] 用户授权外部发布
```
