# ZeroArm Desktop 用户指南（软件基线）

版本：0.1.0

## 1. 这是什么

ZeroArm Desktop 是面向个人使用的六轴机械臂调试与操作控制台：

- Mock 无板演示与故障注入
- Serial 只读连接（HELLO / GET_STATE / 夹爪与台架只读诊断）
- 回零向导、手动关节、轨迹、示教、Recipe、数据集、诊断（Mock 动作路径）

## 2. 启动方式

### 开发环境

```text
cd UpperComputer
uv sync --locked
uv run python -m zeroarm_desktop
```

常用参数：

```text
uv run python -m zeroarm_desktop --mock
uv run python -m zeroarm_desktop --safe-mode
uv run python -m zeroarm_desktop --version
uv run python -m zeroarm_desktop --log-level debug
```

### Windows 便携包

1. 解压 `ZeroArmDesktop-<version>-portable.zip` 到可写目录。
2. 运行 `ZeroArmDesktop/ZeroArmDesktop.exe`。
3. 默认进入安全 Mock 演示路径：连接页选择 Mock → 连接 → Operator 模式。

### Windows 安装包

1. 运行 `ZeroArmDesktop-<version>-setup.exe`（需先有便携目录产物并由 Inno Setup 编译）。
2. 默认 per-user 安装，不强制管理员。
3. 卸载时默认保留 `%LOCALAPPDATA%\ZeroArm Desktop` 用户数据。

## 3. 推荐演示路径（Mock）

```text
连接 Mock → 切换 Operator
 → 回零向导 / 标定页 HOME 0x1D
 → 手动关节（预览 / Arm / 发送 / 按住点动）
 → 轨迹验证 / 回放 / 导入导出
 → 示教（支撑确认 → Arm → 录制 → Review → 另存）
 → Recipe 验证并 Mock 回放
 → 数据集从示教生成 Episode
 → 夹爪/台架只读
 → 诊断（Recorder + Evidence 导出）
```

## 4. 安全提醒

- 软件「停止」按钮**不是**物理急停。
- Serial 连接默认禁止动作命令。
- 真实电机动作必须满足机械支撑、急停可用、地址与限位确认，并获得当前轮明确授权。
- 协议 V2 与高波特率变更需单独审批。

## 5. 数据与证据

- 会话库与导出默认位于用户数据目录。
- 诊断页可导出 Evidence JSON。
- 只读板测报告示例：`docs/reports/readonly_board_20260801.json`。

## 6. 故障排查

| 现象 | 建议 |
|---|---|
| 无法启动 | 使用便携包完整目录；检查杀毒隔离；尝试 `--safe-mode` |
| 3D 黑屏 | 检查 GPU/OpenGL；safe-mode 可跳过重型 3D 路径（若启用） |
| 串口找不到 | 安装 ST-Link VCP 驱动后刷新端口；确认线缆 |
| 动作按钮无效 | Observer 模式会锁定动作；Serial 默认只读 |
| 资产校验失败 | 重新解压完整包；勿删除 `resources/robot_model` |

更多限制见 `KNOWN_LIMITATIONS.md`。
