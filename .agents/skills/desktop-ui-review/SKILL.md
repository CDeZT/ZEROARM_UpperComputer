---
name: desktop-ui-review
description: Desktop UI review workflow for the ZeroArm PySide6 console. Use when asked to review or audit pages, dialogs, navigation, interactions, states, accessibility, or visual consistency before commit. Combines Qt design principles, design-engineering taste, industrial safety, state completeness, keyboard/high-DPI, and UI-thread performance.
---

# 桌面 UI 审查

综合来源：qt-ui-design（信息层级/布局/审计）、emil-design-eng（动效品味/克制）、
工业上位机安全要求（docs/07_SAFETY_AND_HARDWARE_GATES.md）、
upper-computer-ux（本仓库 UX 规约）。

## 流程

1. 收集上下文：目标页面源码、`docs/03_GUI_UX_SPECIFICATION.md` 对应章节、
   theme.py 的 Design Token；必要时截图。
2. 按下列维度逐项检查。
3. 输出 P0–P3 分级报告；具体修改用 Before/After 表，只对用户确认项给代码。

## 检查维度

### 1. 任务与信息层级
- 用户能否一眼知道“这个页面是做什么的、现在该点什么”？
- 主操作是否唯一突出；是否存在多个竞争性按钮？
- 是否存在操作死路（错误后无法恢复）？

### 2. 状态完整性
- loading / empty / error / 正常 四态是否齐全？
- 连接、执行、失败、超时、重连、故障反馈是否可区分？
- V1 缺失字段是否显示 Unknown 而非 0？

### 3. 危险操作与安全
- 动作按钮是否显示目标/轴/速度，并走统一 SafetyGate？
- Arm 是否短时效、不持久化、失焦/断线撤销？
- “软件停止 ≠ 急停”文案是否明确？
- 报警是否“颜色+文字”双通道？

### 4. 高 DPI 与键盘
- 布局是否全 QLayout、无固定像素定位？
- 快捷键（Ctrl+L/Ctrl+D/Esc/Space）是否生效且不因子控件吞键失效？
- Tab 顺序、焦点可见性、按钮可读文本？

### 5. 性能与线程
- GUI 线程是否无阻塞 IO/数据库批写/固件进程等待？
- 高频刷新是否 latest-value + 60FPS 节流？
- 订阅是否随 widget 销毁解除？

### 6. 视觉一致性
- 颜色/圆角/间距/字号是否来自 theme.py token？
- 深浅主题是否都可用且危险色保持语义？
- 动效是否克制（≤300ms、服务状态解释、高频路径无动画）？

## 输出格式

```text
页面: <route>（file:line）
P0 安全/功能阻断: ...
P1 明显体验问题: ...
P2 一致性与细节: ...
P3 建议（可选）: ...
页面级结论: 1 句话
```
