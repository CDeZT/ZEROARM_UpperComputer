# 协议 V2 审批包

状态：`pending_user_approval`

本文件是单元24交付物。它只定义待批准的协议方案，**不修改 MCU 源码**，也不授权进入单元25。

批准口令：

```text
确认实施协议 V2
```

在收到该明确确认前，任何 Agent 不得：

- 修改 `zero_arm_mcu` 协议实现。
- 新增 V2 线上命令处理。
- 将 V2 标记为已完成。
- 把高波特率设为默认值。

## 1. 设计原则

1. 保留现有外层帧：
   ```text
   AA | LEN | CMD | PAYLOAD | CRC8 | 55
   ```
2. 保留 Dallas/Maxim CRC8，CRC 覆盖 `CMD + PAYLOAD`。
3. V1 与 V2 使用不同命令 ID，不通过长度猜版本。
4. 所有 V2 多字节字段统一大端。
5. 线上状态逐字段编码，禁止复制本机 C ABI。
6. 请求携带 `seq`，响应原样回显。
7. 快速状态包含 `device_time_ms` 和 `sample_seq`。
8. 高频状态与低频电机诊断分帧，避免超过 128 字节 TX 缓冲。
9. STOP 保留最高本地优先级，但不得称为物理急停。
10. 未知字段通过 schema minor / TLV 扩展；major 不兼容时明确拒绝。

## 2. 最终命令 ID 表

### 2.1 保留的 V1 命令

| ID | 名称 | 方向 | 说明 |
|---:|---|---|---|
| `0x00` | HELLO | 请求/响应 | 兼容入口，返回 `ZEROARM/1.0` 文本 |
| `0x01` | GET_STATE | 请求/响应 | 当前 60 字节 V1 ABI 布局 |
| `0x02` | ENABLE | 请求/响应 | 危险动作，沿用 V1 掩码 |
| `0x03` | DISABLE | 请求/响应 | 危险动作，沿用 V1 掩码 |
| `0x04` | STOP | 请求/响应 | 软件停止，非急停 |
| `0x05` | SET_JOINT_TARGET | 请求/响应 | 28 字节目标，大端关节 |
| `0x06` | HOME | 请求/响应 | 当前固件可能 `NOT_CONFIGURED` |
| `0x07` | TEACH_START | 请求/响应 | 危险动作 |
| `0x08` | TEACH_STOP | 请求/响应 | 危险动作 |
| `0x09` | CLEAR_FAULT | 请求/响应 | 状态恢复 |

### 2.2 拟新增 V2 命令

| ID | 名称 | 方向 | 说明 |
|---:|---|---|---|
| `0x10` | GET_CAPABILITIES | 请求/响应 | 协议、轴数、能力位、最大遥测率 |
| `0x11` | GET_STATE_V2 | 请求/响应 | 固定编码快速状态 |
| `0x12` | GET_MOTOR_DIAGNOSTICS | 请求/响应 | 速度、电流、驱动状态、反馈年龄 |
| `0x13` | SET_TELEMETRY | 请求/响应 | 启停主动遥测与频率 |
| `0x14` | GET_CONFIG | 请求/响应 | 读取限位、方向、零偏、减速比 |
| `0x15` | PING | 请求/响应 | RTT、设备时间、链路健康 |
| `0x16` | GET_FAULT_DETAIL | 请求/响应 | 故障位与逐轴来源 |
| `0x17` | GET_BUILD_INFO | 请求/响应 | Git SHA、构建类型、硬件版本 |
| `0x70` | EVENT_V2 | MCU→Host | 主动事件 |
| `0x71` | TELEMETRY_V2 | MCU→Host | 主动状态 |

首期危险动作仍走 V1 ID，降低审批面。后续可另开审批包引入带 `seq` 和执行语义的 V2 动作命令。

## 3. 公共头与端序

### 3.1 V2 请求最小头

```text
protocol_major : u8
protocol_minor : u8
seq            : u16 BE
```

### 3.2 V2 响应/事件公共头

```text
protocol_major : u8
protocol_minor : u8
kind           : u8   # 0=RESPONSE 1=EVENT 2=TELEMETRY
flags          : u8
seq            : u16 BE
device_time_ms : u32 BE
result         : u8
```

共 11 字节，全部多字节字段大端。

### 3.3 flags

| bit | 语义 |
|---:|---|
| 0 | accepted |
| 1 | completed |
| 2 | more fragments |
| 3 | state degraded/stale |
| 4～7 | reserved，发送必须为 0 |

## 4. GET_STATE_V2 字段表

公共头之后：

```text
state_schema_major : u8
state_schema_minor : u8
run_state          : u8
enabled_mask       : u8
homed_mask         : u8
moving_mask        : u8
online_mask        : u8
teach_mask         : u8
fault_flags        : u32 BE
target_generation  : u32 BE
sample_seq         : u32 BE
target_joint_urad  : 6 * i32 BE
actual_joint_urad  : 6 * i32 BE
```

估算：

```text
公共头 11
状态字段 62
合计约 73 字节 payload 区内容
整帧约 78 字节 < 128 字节 TX 缓冲
```

## 5. 能力位

```text
bit0  joint_target
bit1  enable_disable
bit2  stop
bit3  homing
bit4  teach
bit5  active_telemetry
bit6  motor_diagnostics
bit7  config_read
bit8  config_write_future
bit9  gripper
bit10 cartesian_on_mcu
bit11 firmware_update
```

GUI 必须按能力位禁用不存在的动作，不得只靠固件字符串猜测。

## 6. 兼容与回退

```text
连接
 -> V1 HELLO
 -> 尝试 GET_CAPABILITIES (0x10)
    -> NOT_IMPLEMENTED / 无响应：V1 兼容模式
    -> 成功且 major 兼容：V2 模式
    -> major 不兼容：只读并明确提示
```

### V1 模式

- 继续使用 60 字节 GET_STATE。
- 所有 V2 缺失字段显示 `None / V1未提供`。
- 默认最高 100 Hz 轮询，超时自动降频。
- 不启用主动遥测。

### V2 模式

- 优先 `GET_STATE_V2` 或 `TELEMETRY_V2`。
- 请求按 `seq` 关联。
- 同时记录 device time 与 PC monotonic time。
- 能力位驱动页面。

### 回退

1. 上位机配置强制 `protocol_mode=v1`。
2. MCU 固件保留 V1 命令处理。
3. 高波特率失败时回退 115200。
4. V2 解析失败时断线并提示，不猜测字段。

## 7. MCU 拟改动文件

仅在审批后进入单元25时修改，本单元不改：

```text
Protocol/Inc/protocol.h
Protocol/Src/protocol.c
Protocol/Src/messages.c
Robot/Inc/robot_types.h
Robot/Src/robot_state.c
App/Src/app_host_tx.c
App/Src/app_host_rx.c
Tests/test_protocol_*.c
Tests/test_messages_*.c
```

## 8. 资源影响预估

| 项目 | 预估 | 说明 |
|---|---:|---|
| 额外 RAM | 256～512 B | 请求跟踪、telemetry 缓冲、parser timeout 状态 |
| 额外 FLASH | 2～4 KB | 新命令表、编码、能力响应、主机测试夹具 |
| CPU | 中 | 100 Hz 固定编码低于 ABI memcpy 风险，但需实测 |
| UART | 中 | 100 Hz × ~80 B ≈ 8 KB/s；200 Hz 需独立高波特率审批 |

当前帧缓冲：

```text
PROTO_RX_BUF_SIZE = 128
PROTO_TX_BUF_SIZE = 128
```

V2 快速状态必须保持在该边界内。

## 9. 黄金帧 / Fixture 计划

本审批包固定以下 fixture ID，批准后在单元25/26实现并固化：

| Fixture ID | 说明 |
|---|---|
| `V2-CAP-REQ` | GET_CAPABILITIES 请求 |
| `V2-CAP-RSP` | 能力响应，含 major/minor/flags/seq |
| `V2-STATE-REQ` | GET_STATE_V2 请求 |
| `V2-STATE-RSP` | 快速状态响应，含 device_time/sample_seq |
| `V2-PING-REQ` | PING 请求 |
| `V2-PING-RSP` | PING 响应 |
| `V2-BAD-MAJOR` | major 不兼容拒绝 |
| `V2-TIMEOUT-RESYNC` | parser inter-byte timeout 后恢复 |
| `V2-SEQ-ECHO` | 响应 seq 回显 |

所有多字节字段必须有明确十六进制大端向量，不允许“结构体 dump”。

## 10. Parser timeout 设计

V2 必须增加帧内超时：

```text
收到 STX 后，若在 T_frame_idle 内未完成整帧：
  -> 丢弃当前部分帧
  -> etx/length/timeout 计数 +1
  -> 回到 WAIT_STX
```

建议默认：

```text
T_frame_idle = 20 ms
```

可用配置覆盖，但不得依赖“等待下一个 STX 碰巧救回”。

## 11. 主机队列 / 重试 / 去重

| 类别 | 策略 |
|---|---|
| 只读轮询 | 可合并最新请求；超时后降频 |
| 危险动作 | 超时显示 `UNKNOWN_OUTCOME`，禁止自动重试 |
| seq | 主机生成单调 seq；响应必须回显 |
| 重复响应 | 同 seq 重复响应计入诊断，不重复应用状态 |
| 乱序 | V1 无 seq；V2 丢弃旧 seq 或标记 degraded |
| 写队列 | 有界；满则拒绝并计数 |

## 12. 测试矩阵

### 12.1 主机 / 单元测试

- 黄金帧编解码。
- 端序。
- seq 回显。
- major/minor 协商。
- V1 回退。
- 未知命令 / 未知能力位保留。
- 超时、重复、乱序、噪声、截断。
- 128 字节边界。

### 12.2 Sanitizer / 交叉编译

- 主机 ASan/UBSan。
- STM32 Debug/Release 交叉编译。
- 栈/堆静态预算检查。

### 12.3 只读板测

允许：

```text
HELLO
GET_CAPABILITIES
GET_STATE / GET_STATE_V2
PING
GET_BUILD_INFO
GET_FAULT_DETAIL
```

禁止：

```text
ENABLE
DISABLE
STOP
HOME
TEACH_START
TEACH_STOP
SET_JOINT_TARGET
任意轨迹/示教/Cartesian 动作
```

### 12.4 性能门

| ID | 目标 |
|---|---|
| PERF-V2-100 | 100 Hz GET_STATE_V2 稳定，无无界队列增长 |
| PERF-V2-DROP | sample_seq 丢样可检测并计数 |
| PERF-V2-CPU | MCU 与上位机 CPU/延迟报告机器与 P95 |

200 Hz 与 460800/921600 不在本包默认批准范围，另走高波特率审批 A-002。

## 13. 上位机迁移方案

批准并完成 MCU 单元25后：

1. 单元26 增加协商状态机。
2. Domain 模型继续用 `None` 表达缺失字段。
3. Diagnostics 显示 V2 seq / device time。
4. SafetyGate 不因 V2 自动放行动作。
5. 记录器同时保存 PC monotonic 与 device time。
6. 打包测试覆盖 V1-only 与 V2 固件矩阵。

## 14. 明确不在本包范围

- 不修改 MCU。
- 不实施高波特率默认值。
- 不实施危险动作 V2 命令。
- 不实施 config write。
- 不实施 Cartesian on MCU。
- 不把软件 STOP 升级为安全认证急停。
- 不授权真实电机动作。

## 15. 审批检查清单

```text
[ ] 命令 ID 无冲突
[ ] 全部 V2 多字节字段大端
[ ] GET_STATE_V2 不超过 128 字节帧缓冲
[ ] V1 保留且可回退
[ ] parser inter-byte timeout 已定义
[ ] 危险命令超时不自动重试
[ ] 资源影响可接受
[ ] 只读板测计划完整
[ ] 用户明确回复：确认实施协议 V2
```

当前结论：

```text
审批包已完成
MCU 未修改
等待用户明确批准后才能进入单元25
```
