---
name: device-state-machine
description: ZeroArm 设备状态机规约。Use when designing or reviewing session/device state transitions (connection handshake, polling, action execution, auto-reconnect, timeout, cancel, fault), single-inflight rules, UnknownOutcome handling, and the corresponding UI feedback in the upper-computer console.
---

# 设备状态机规约

参考实现：`application/device_session.py`（SessionState）、`domain/safety.py`（Arm 上下文）、
`application/playback.py`、`application/teach.py`、`transport/base.py`（LinkState）。

## 状态集合

```text
LinkState:    CLOSED -> OPENING -> OPEN -> CLOSING / FAILED
SessionState: DISCONNECTED -> OPENING -> HANDSHAKING -> READONLY_READY
              -> RECONNECT_WAIT / CLOSING / FAULTED
PlaybackState: IDLE -> PLAYING <-> PAUSED -> COMPLETED / ABORTED
TeachState:    IDLE -> ARMED -> RECORDING -> REVIEW
```

## 迁移铁律

1. 握手顺序固定 HELLO → GET_STATE → READONLY_READY；第一个快照后才启动轮询。
2. V1 同一时刻最多一个请求在途；新轮询遇到在途请求跳过并计 `poll_coalesced`，不排队。
3. 自动重连只恢复只读观察；重连后模式回 Observer，Arm/hold/teach/playback 全部撤销。
4. 危险命令超时结果是 `UnknownOutcome`，禁止自动重发；显示“结果未知”而非“失败可重试”。
5. 发送危险命令前暂停轮询占用单在途槽；结束/中止后恢复轮询。
6. STOP 在软件优先级上高于普通动作，但不等同物理急停。
7. 连接更换/模式切换/窗口失焦/设备睡眠/校准变化 → disarm 所有 Arm 上下文。
8. 受控退出：Mock 未回零先 HOME 0x1D（有界等待 ≤5s 观察证据）；RESET-REQUIRED 故障需用户确认。

## UI 反馈矩阵

| 事件 | 反馈 |
|---|---|
| 握手步骤 | 连接页时间线逐步显示 |
| 状态过期 | 动作按钮禁用并提示新鲜度 |
| 执行成功 | 显示 result raw + 状态观察（moving=0 且误差≤2°） |
| 执行失败/拒绝 | 显示 SafetyGate 拒绝码与可执行建议 |
| 超时 | “结果未知”，不提供重发按钮 |
| 重连 | 徽章进入 RECONNECT_WAIT，动作全禁用 |
| 断线 | 停止 hold/playback，保留诊断数据 |

## 审查清单

- 是否有未覆盖状态（例如 CLOSING 中再点连接）？
- 是否有非法迁移未防护？
- 状态与 UI 是否不同步（状态变了按钮没变）？
- 超时/取消路径是否泄漏在途请求或订阅？
- 自动重连是否会恢复动作状态？
- 状态机是否纯逻辑可测（不依赖 Qt 定时器）？

输出：状态矩阵缺漏表 + 违规路径（文件:行）。
