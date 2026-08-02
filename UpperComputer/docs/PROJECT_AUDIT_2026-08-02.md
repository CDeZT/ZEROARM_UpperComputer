# ZeroArm 上位机全项目审计（2026-08-02）

## 结论

当前项目是一个测试覆盖较好的 **Mock/只读 V1 工程原型**，不是已完成真实机械臂验收的生产上位机。
本轮修掉了已能通过源码、测试和离屏界面复现的高风险缺陷，但“测试全绿”不能替代真实串口动作、Windows
安装和机械安全验收。任何把 0.1.0 描述为完整成品的说法都不成立。

## 本轮 Before / After

| 范围 | Before | After | 仍不能宣称 |
|---|---|---|---|
| 安全 | 空闲 HOME 可与连续点动交错；软件 STOP 只停本地定时器 | 活动动作阻断 HOME；STOP 进入授权设备链路并具有队列最高优先级 | 不能替代物理急停 |
| 会话 | 请求可永久挂起；重连无界；动作结果假定同步 | 超时、有限重连、UnknownOutcome、异步请求、STOP 抢占 | 未经真实动作链路验收 |
| 存储 | 测试污染用户目录；SQLite 失败后 Recorder 可能继续假装工作 | 数据根可注入；故障停止、丢弃并显示 | 尚无完整会话查询/删除/导出产品功能 |
| 架构 | domain 反向 import application/protocol；两个 MainWindow；Shell 直发 HOME | 领域边界可执行测试；单一 Shell；HOME 统一走 SafetyGate | Shell 仍是 705 行组合根/控制器 |
| UI/UX | 动作按钮先允许点击再报错；导航截断；浅色曲线黑底；层级弱 | 锁定原因前置、导航滚动、曲线随主题、动作语义色、连接可取消 | 尚未完成逐工作流按钮状态机和完整无障碍验收 |

## 剩余问题（不粉饰）

### P1 — 阻止“生产完成”声明

1. `DeviceSession` 的真实 Serial 动作仍被故意锁定；HOME、手动关节、轨迹、示教仅 Mock E2E。没有真实板卡动作证据。
2. Cartesian 只有 IK/Ghost；固件页只有检查与 dry-run；手柄页只有模拟采样；这些是明确的半成品，不是完整功能。
3. 没有会话浏览/筛选/回放/删除，Recorder 目前基本只有写入链路；“诊断数据管理”远未完成。
4. Windows PyInstaller/Inno 的真实构建、安装、升级、卸载、无 Python 干净机启动尚未验收。
5. `gui/shell.py` 仍承担组合、路由、全局状态、安全退出和大量接线。705 行说明模块边界仍偏浅，后续功能会继续放大修改半径。

### P2 — 明显产品与维护债务

1. 轨迹暂停/继续/中止、示教开始/停止等按钮尚未全部按各自工作流状态精确启停；当前主要是会话级粗粒度门控。
2. Arm 5 秒没有可视倒计时；用户只看到文本，临界过期时体验差。
3. 串口枚举、诊断压缩导出、若干 JSON 文件操作仍在 GUI 线程；数据或驱动变慢时会卡界面。
4. 页面直接调用 `default_data_root()`，路径/保存策略未统一为可注入服务；测试性和便携模式扩展性一般。
5. 中文字符串散落，未接 `tr()`/翻译资源；设置、关于、右侧快照/事件检查器仍缺失。
6. 无自动对比度门禁、完整键盘 Tab 顺序检查、屏幕阅读器实测；只能说已改善 accessibility，不能说合规。
7. 协议 fixture 主要来自 MCU 源码和构造帧；虽然 COM3 只读板测有历史记录，仍缺本轮实机抓帧逐字节复核。

## 技能与工具选择

按开发环境方案和现场技术栈，使用现有的 `systematic-debugging`、`tdd`、`device-state-machine`、
`protocol-contract`、`upper-computer-architecture`、`pyside6-development`、`upper-computer-ux`、
`desktop-ui-review`、`qt-ui-design`、`emil-design-eng` 与 PDF 检查流程。现有技能已覆盖本轮任务，
未擅自安装 PlatformIO、QML、Playwright、Figma 或重型编排插件。

## 验证证据

- `ruff check src tests`：通过。
- `mypy src`：82 个源文件通过。
- `pytest -q`：294 passed / 4 skipped。
- `pytest --cov=zeroarm_desktop`：89%（6661 statements，765 missed）。
- GUI：Qt offscreen 下验收最小窗口、深/浅主题、Dashboard、Monitor、Manual；黑底仅为旧跨页 backing-store 截图伪影，独立窗口复核正常。
- 本轮没有连接板卡、没有发送真实动作、没有修改 MCU、没有实施协议 V2。
