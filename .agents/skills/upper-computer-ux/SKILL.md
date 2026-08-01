---
name: upper-computer-ux
description: "ZeroArm 上位机 UI/UX 规约。Use when designing or reviewing pages of the PySide6 desktop console: information hierarchy, primary/secondary actions, real-time data, curves, logs, parameters, alarms, connection status feedback, danger confirmation, Design Tokens, high DPI, keyboard and accessibility."
---

# 上位机 UX 规约

适用对象：ZeroArm Desktop（PySide6 Widgets 工业上位机）。先读
`docs/03_GUI_UX_SPECIFICATION.md` 与 `src/zeroarm_desktop/gui/theme.py`，遵循已有约定。

## 页面通用规则

1. 每页一个主操作，其余按钮视觉弱化；同组 CTA 不超过两个。
2. 状态反馈 <400ms；耗时 >1s 显示进度；>10s 显示预计时间。
3. 每个异步区必须有 loading / error / empty 三态，错误文案可行动（“做什么能恢复”）。
4. 按钮文案用动词（连接、断开、发送、停止），危险按钮固定 `global_stop_button` 样式。
5. 危险动作（HOME/ENABLE/TEACH/发送目标）必须显示轴掩码、目标、速度，并走统一 SafetyGate；
   Arm 短时效 5 秒，超时自动取消；不持久化 armed。
6. 软件“停止”按钮文案必须注明“软件停止，非急停”。

## 实时数据与曲线

- 高频状态用 latest-value，GUI 渲染 ≤60 FPS；暂停只停显示，不停采集和记录。
- 曲线用固定容量 ring（默认 60s 窗口），显示实际 Hz、丢样、poll_coalesced。
- V1 缺失字段（velocity/current/online/device_time）显示 `-- / V1 未提供`，不伪造 0。
- 未知 enum/result/fault 保留原始值，同时给出已知解释。

## 报警与故障

- 报警必须“颜色 + 文字/图标”，不能只靠颜色。
- 故障显示原始位值 + 已知位中文解释 + 未知位计数。
- RESET-REQUIRED（STARTUP/HOMING/ESTOP）提示“断电复位 MCU”，CLEAR_FAULT 不可清除。
- 危险状态（FAULT/未回零/未授权）下禁用动作按钮并说明原因。

## 连接状态反馈

状态机文案与禁用规则：

| 状态 | 界面表现 | 动作按钮 |
|---|---|---|
| 未连接 | 徽章“未连接”，连接按钮可用 | 全禁用 |
| OPENING/HANDSHAKING | 时间线显示步骤 | 禁用 |
| READONLY_READY | “只读已连接”，显示固件/协议 | 只读命令可用 |
| RECONNECT_WAIT | 提示自动重连只恢复只读 | 全禁用 |
| FAULTED | 显示失败原因 | 仅诊断 |

## Design Token

- 从 `gui/theme.py` 的深/浅主题取色，不散落裸色值：
  主色 `#167d72`（深）/`#0f766e`（浅）、危险 `#6b2a2a`/`#b91c1c`、
  背景 `#111820`/`#f3f5f7`、文本 `#dbe5ec`/`#17212b`。
- 字号：基础 13px，页标题 24px/700，次级说明用主题色不新造字号层级。
- 圆角/间距：按钮 6px、输入 5px、布局 spacing 10px，保持全局一致。

## 高 DPI、键盘与无障碍

- 布局一律 QLayout，禁止固定像素定位；默认窗口 1440×900，最小 1280×720。
- 快捷键：Ctrl+L 连接页、Ctrl+D 诊断、Esc 取消/停止点动、Space 软件 STOP（输入框聚焦也生效）。
- Tab 顺序从主操作开始；按钮必须有可读文本；焦点环可见。
- 主题切换不改变安全语义；危险按钮在深浅主题下都保持红色系。

## 动效克制（工业上位机红线）

- 动画只服务于状态解释（toast 进入/退出、加载指示、状态迁移），禁止炫技。
- UI 动画 ≤300ms，高频路径（点动、轮询刷新）不动画。
- 报警与故障展示优先于任何视觉效果；不因动画降低实时数据刷新性能。

## 审查输出

按 P0–P3 列出问题（文件:行 — 规则 — 建议），并给出一句页面级结论。
具体修改建议用 Before/After 表，仅对用户确认的改动给出。
