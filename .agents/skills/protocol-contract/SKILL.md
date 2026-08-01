---
name: protocol-contract
description: "ZeroArm V1 serial protocol contract review. Use when writing or reviewing codecs, parsers, golden fixtures, or protocol docs: frame envelope, command IDs, 60-byte GET_STATE layout, 28-byte SET_JOINT_TARGET, result codes, fault bits, endianness, and bounded parsing rules."
---

# V1 协议契约审查

权威来源：`docs/17_API_DATA_AND_FIXTURE_CONTRACTS.md`、
`src/zeroarm_desktop/protocol/*.py`、`tests/protocol/*`、
MCU 侧 `Protocol/Inc/protocol.h`、`Protocol/Src/messages.c`、`Robot/Inc/robot_types.h`。

## 线协议事实（V1，2026-08 基线）

```text
帧: AA | LEN | CMD | PAYLOAD | CRC8 | 55
LEN = 1 + len(PAYLOAD)；CRC8 = Dallas/Maxim reflected 0x8C, initial 0x00，覆盖 CMD+PAYLOAD
HELLO(0x00): 空请求 -> ASCII "ZEROARM/1.0"
GET_STATE(0x01): 空请求 -> 60 字节
ENABLE/DISABLE(0x02/0x03): mask 1B -> result 1B
STOP(0x04)/TEACH_STOP(0x08)/CLEAR_FAULT(0x09): 空 -> result 1B
SET_JOINT_TARGET(0x05): 28B -> result 1B
HOME(0x06)/TEACH_START(0x07): mask 1B -> result 1B
台架 0x20-0x27、夹爪 0x30-0x34：Debug 固件编译（CONFIG_MOTOR_BENCH_TEST=1）
```

## GET_STATE 60B 布局（小端）

```text
0..3   int32 run_state
4..27  6×int32 target urad
28..51 6×int32 actual urad
52     enabled_mask
53     homed_mask
54     moving_mask
55     reserved
56..59 uint32 fault_flags
```

必须用 `int.from_bytes(..., "little")` 逐字段解码，禁止 native ABI（`struct.unpack("@")`）。

## SET_JOINT_TARGET 28B（大端）

```text
0..23  6×int32 BE urad
24..25 uint16 BE duration_ms
26..27 uint16 BE gripper_u16
```

## 编解码规则

- 编码前校验：六轴数量、int 范围、duration 1..0xFFFF、gripper 0..0xFFFF、mask 1..0x3F。
- 解码严格校验 payload 长度；未知 result/fault/enum 保留 raw_value，不抛“未知”当失败。
- result 只表示请求函数返回值，不代表电机动作完成。
- fault 位：STARTUP(9)/HOMING(10)/ESTOP(11) 为 RESET-REQUIRED，CLEAR_FAULT 不可清除。

## 解析器规则

- 有界状态机，任意字节流不崩溃、不死循环、无无界增长。
- 非法 LEN 立即复位；CRC/ETX 错误计数后等待下一个 STX；噪声字节计数。
- 任意分块（粘包/拆包）结果一致；Hypothesis 随机字节覆盖。

## Fixture 纪律

- 新命令/字段必须先加黄金 fixture（`protocol/fixtures.py` + `FIXTURE_SHA256`），再实现 codec。
- fixture 来源注明 MCU commit 与日期；R4 板测后逐字节复核。
- 禁止改 fixture 去迁就实现；实现与 fixture 不一致 = 实现错误。

## 审查清单

- 帧长度/CRC/边界是否全覆盖测试？
- 60B/28B 是否硬编码长度并校验？
- 端序是否与文档一致（状态小端、目标大端）？
- 未知值是否保留原始值？
- 单在途是否被破坏？
- 新命令是否走审批（V2/新命令 ID 需用户确认）？
- 协议代码是否零 Qt/pyserial 依赖？
