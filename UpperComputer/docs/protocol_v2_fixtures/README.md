# Protocol V2 Fixture Registry

本目录只登记审批后的 fixture ID 与语义，不包含已批准的最终二进制黄金帧实现。

状态：`pending_user_approval`

| Fixture ID | Direction | Command | Purpose |
|---|---|---:|---|
| `V2-CAP-REQ` | Host→MCU | `0x10` | GET_CAPABILITIES request with seq |
| `V2-CAP-RSP` | MCU→Host | `0x10` | Capability response, big-endian multi-byte fields |
| `V2-STATE-REQ` | Host→MCU | `0x11` | GET_STATE_V2 request |
| `V2-STATE-RSP` | MCU→Host | `0x11` | Fast state with device_time_ms and sample_seq |
| `V2-PING-REQ` | Host→MCU | `0x15` | PING request |
| `V2-PING-RSP` | MCU→Host | `0x15` | PING response |
| `V2-BAD-MAJOR` | MCU→Host | any V2 | Reject incompatible protocol major |
| `V2-TIMEOUT-RESYNC` | stream | n/a | Parser inter-byte timeout returns to WAIT_STX |
| `V2-SEQ-ECHO` | MCU→Host | any V2 | Response must echo request seq |

批准并进入单元25/26后，再把逐字节十六进制向量与 SHA-256 固化到测试代码。
