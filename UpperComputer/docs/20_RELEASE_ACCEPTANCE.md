# 最终发布验收基线（单元32文档）

状态：`in_progress_software_only`

本文件汇总当前可发布软件能力、测试证据、已知限制与延期硬件项。
它**不**表示真实电机动作验收已完成，也**不**表示协议 V2 已实施。

## 1. 版本

| 项 | 值 |
|---|---|
| 应用版本 | 0.1.0 |
| 协议运行时 | V1 兼容 |
| 默认 Transport | Mock / Serial |
| 默认串口波特率 | 115200 |

## 2. 已完成功能清单

- 工程基线、静态检查、pytest/pytest-qt
- V1 帧协议、命令 Codec、Mock/Serial Transport、DeviceSession
- 配置、SQLite Recorder、CSV/JSON 导出
- GUI 壳、连接页、Dashboard、六轴监控
- 参考资产导入、关节映射、FK、3D 工作区
- SafetyGate 与 Mock 手动控制
- 轨迹编辑、Mock 回放、Mock 示教
- Cartesian/IK 离线预览
- 标定候选与 Mock Homing 语义
- 诊断页、安全协议终端、诊断包
- 手柄/Recipe Mock、数据集接口、固件升级 dry-run
- 协议 V2 审批包、高波特率审批包

## 3. 自动化证据

本地开发机命令：

```powershell
uv run ruff format --check .
uv run ruff check .
uv run mypy
uv run pytest -q
```

发布前额外：

```powershell
uv run python packaging/build_portable.py
```

## 4. 打包产物约定

| 产物 | 路径 |
|---|---|
| 便携目录 | `dist/ZeroArmDesktop/` |
| 便携 ZIP | `dist/ZeroArmDesktop-0.1.0-portable.zip` |
| 便携清单 | `dist/ZeroArmDesktop-0.1.0-portable.manifest.json` |
| 安装包脚本 | `packaging/zeroarm-desktop.iss` |
| 安装包输出 | `dist/ZeroArmDesktop-0.1.0-setup.exe`（需 Inno Setup 编译） |

清单必须包含：

- 版本
- 生成 UTC 时间
- ZIP SHA-256
- 可执行文件 SHA-256
- 许可证说明

## 5. 已知限制

1. 协议 V2 仅审批包完成，未实施。
2. 高波特率仅审批包完成，默认仍 115200。
3. 机械臂未组装，真实动作验收未授权。
4. V1 缺失字段保持 `None/Unknown`，不伪造 0。
5. 软件 STOP 不是物理急停。
6. 固件页默认 dry-run，不自动刷写。
7. Cartesian 仅离线 ghost 预览。
8. 机器人模型 GPL-2.0 许可证必须随包保留。

## 6. 延期硬件标签

| 标签 | 含义 |
|---|---|
| `HW-DEFERRED-V2` | 等待“确认实施协议 V2” |
| `HW-DEFERRED-BAUD` | 等待高波特率批准与实测 |
| `HW-DEFERRED-ACTION` | 等待机械安全门与分项动作确认 |
| `HW-DEFERRED-READONLY-BOARD` | 需要真实板卡做只读 soak |

## 7. 发布门禁

软件可分发前至少满足：

```text
[x] 单元0～24软件能力完成
[x] R1～R14 Mock 主路径可演示（已提交）
[x] 用户指南 / 已知限制 / 能力矩阵文档已起草（工作区，见 docs/USER_GUIDE.md 等）
[x] 打包 dry-run 输入清单脚本已增强（macOS 可检文档齐备；Windows 真构建待做）
[ ] 便携包在干净Windows无系统Python环境启动
[ ] 安装/升级/卸载保留用户数据
[ ] 清单哈希已记录于实际 dist 产物
[ ] 用户另行授权版本标签/外部发布
```

当前结论：

```text
软件功能主线 R1～R14 已提交
R15 发布刷新半成品在工作区（未提交）
Windows 真打包与干净环境烟雾仍待做
真实板测与动作验收仍阻塞
```

## 8. R15 进行中备注（2026-08-01 晚）

- 详见 `docs/AGENT_HANDOFF_2026-08-01-LATE.md`。
- 本机若在 macOS：优先 `uv run python packaging/build_portable.py --dry-run`。
- Windows 上再执行完整 build，并把 ZIP/exe SHA-256 回填本节。
