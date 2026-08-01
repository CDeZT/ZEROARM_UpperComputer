"""Stable V1 frame fixtures derived from the current MCU implementation.

Every frame below is byte-for-byte frozen. Values follow the current MCU
baseline (zero_arm_mcu main @ 48c11d8):

- Protocol/Src/protocol.c: frame envelope AA | LEN | CMD | PAYLOAD | CRC8 | 55,
  CRC8 Dallas/Maxim reflected 0x8C initial 0x00 over CMD+PAYLOAD.
- Protocol/Src/messages.c: command handlers, result codes and payload layouts.
- Robot/Inc/robot_state.h / robot_types.h: 60-byte GET_STATE layout and the
  twelve fault bits.
- Motor/Inc/motor_types.h: 40-byte little-endian bench state and 7-byte
  protection response.
- Gripper/Inc/feetech_sts.h + GRIPPER_ST3215_GUIDE.md: gripper bridge
  payloads and the 3-byte `result | id | servo_error` response head.

SHA-256 values are registered in FIXTURE_SHA256 and asserted by
tests/protocol/test_v1_fixture_hashes.py.
"""

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class FrameFixture:
    fixture_id: str
    raw: bytes
    source: str


MCU_SOURCE = "zero_arm_mcu main @ 48c11d8, inspected 2026-08-01"
MCU_SOURCE_SHA256 = {
    "Protocol/Src/protocol.c": "8610a8c4795f2627122243c57187cbdcb2cc6f64caf887b1ad94b896ba5ece93",
    "Protocol/Src/messages.c": "9774db90652ea57620df282f11a280dfdd764c0a4a97f3aadbb4b469d66dfc4d",
}

V1_HELLO_REQUEST = FrameFixture("V1-HELLO-REQ", bytes.fromhex("AA 01 00 00 55"), MCU_SOURCE)
V1_HELLO_RESPONSE = FrameFixture(
    "V1-HELLO-RSP",
    bytes.fromhex("AA 0C 00 5A 45 52 4F 41 52 4D 2F 31 2E 30 E2 55"),
    MCU_SOURCE,
)
V1_RESULT_OK_CMD02 = FrameFixture(
    "V1-RESULT-OK-CMD02", bytes.fromhex("AA 02 02 00 91 55"), MCU_SOURCE
)
V1_STATE_READY_ZERO = FrameFixture(
    "V1-STATE-READY-ZERO",
    bytes.fromhex(
        "AA3D010100000000000000000000000000000000000000000000000000000000"
        "00000000000000000000000000000000000000000000000000000000000000F0"
        "55"
    ),
    "GET_STATE READY, all masks 0, fault 0; layout per robot_types.h",
)
V1_STATE_READY_HOMED_1D = FrameFixture(
    "V1-STATE-READY-HOMED-1D",
    bytes.fromhex(
        "AA3D010100000000000000000000000000000000000000000000000000000000"
        "0000000000000000000000000000000000000000000000001D00000000000033"
        "55"
    ),
    "GET_STATE READY, homed mask 0x1D (J1/J3/J4/J5), fault 0",
)
V1_STATE_STARTUP_FAULT = FrameFixture(
    "V1-STATE-STARTUP-FAULT",
    bytes.fromhex(
        "AA3D010500000000000000000000000000000000000000000000000000000000"
        "000000000000000000000000000000000000000000000000000000000200008B"
        "55"
    ),
    "GET_STATE FAULT with STARTUP bit9 set (required limits not active)",
)
V1_STATE_ESTOP_FAULT = FrameFixture(
    "V1-STATE-ESTOP-FAULT",
    bytes.fromhex(
        "AA3D010500000000000000000000000000000000000000000000000000000000"
        "00000000000000000000000000000000000000000000000000000000080000E1"
        "55"
    ),
    "GET_STATE FAULT with ESTOP bit11 set (PD15 latched, reset required)",
)
V1_ENABLE_MASK_1D = FrameFixture(
    "V1-ENABLE-MASK-1D", bytes.fromhex("AA 02 02 1D F1 55"), MCU_SOURCE
)
V1_HOME_MASK_1D = FrameFixture(
    "V1-HOME-MASK-1D", bytes.fromhex("AA 02 06 1D CA 55"), "HOME request with profile mask 0x1D"
)
V1_TARGET_MIXED_SIGNS = FrameFixture(
    "V1-TARGET-MIXED-SIGNS",
    bytes.fromhex(
        "AA 1D 05 80 00 00 00 FF E8 08 2E FF FF FF FF 00 00 00 00 00 17 F7 D2 "
        "7F FF FF FF 12 34 AB CD C1 55"
    ),
    "SET_JOINT_TARGET 28B: -2^31,-1570770,-1,0,1570770,2^31-1 BE; duration 0x1234; gripper 0xABCD",
)
V1_TARGET_FORBIDDEN_J2 = FrameFixture(
    "V1-TARGET-FORBIDDEN-J2",
    bytes.fromhex(
        "AA 1D 05 00 00 00 00 00 17 F7 D2 00 00 00 00 00 00 00 00 00 00 00 00 "
        "00 00 00 00 03 E8 00 00 D3 55"
    ),
    "28B target with non-zero J2 (90 deg); MUST be rejected by HardwareProfile, never sent (R2)",
)
V1_TARGET_FORBIDDEN_J6 = FrameFixture(
    "V1-TARGET-FORBIDDEN-J6",
    bytes.fromhex(
        "AA 1D 05 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 "
        "00 17 F7 D2 03 E8 00 00 80 55"
    ),
    "28B target with non-zero J6 (90 deg); MUST be rejected by HardwareProfile, never sent (R2)",
)
V1_BENCH_QUERY_MOTOR1 = FrameFixture(
    "V1-BENCH-QUERY-MOTOR1", bytes.fromhex("AA 02 20 01 9F 55"), MCU_SOURCE
)
V1_BENCH_ENABLE_MOTOR1 = FrameFixture(
    "V1-BENCH-ENABLE-MOTOR1", bytes.fromhex("AA 02 21 01 5B 55"), MCU_SOURCE
)
V1_BENCH_MOVE_REL_MOTOR1 = FrameFixture(
    "V1-BENCH-MOVE-REL-MOTOR1",
    bytes.fromhex("AA 0B 24 01 01 00 00 2A 30 00 64 00 32 02 55"),
    "BENCH_MOVE_REL: motor 1, dir 1, 10800 tenths deg (BE), 100 tenths RPM (BE), 50 RPM/s (BE)",
)
V1_BENCH_GET_PROTECTION_MOTOR3 = FrameFixture(
    "V1-BENCH-GET-PROTECTION-MOTOR3", bytes.fromhex("AA 02 26 03 89 55"), MCU_SOURCE
)
V1_BENCH_GET_PROTECTION_RSP_MOTOR3 = FrameFixture(
    "V1-BENCH-GET-PROTECTION-RSP-MOTOR3",
    bytes.fromhex("AA 08 26 03 00 64 0D AC 01 2C E6 55"),
    "protection response 7B: motor 3, 100 C, 3500 mA, 300 ms (all BE)",
)
V1_BENCH_SET_PROTECTION = FrameFixture(
    "V1-BENCH-SET-PROTECTION",
    bytes.fromhex("AA 09 27 03 01 00 64 0D AC 01 2C 58 55"),
    "BENCH_SET_PROTECTION: motor 3, save=1, 100 C, 3500 mA, 300 ms (all BE)",
)
V1_BENCH_QUERY_RSP_MOTOR1 = FrameFixture(
    "V1-BENCH-QUERY-RSP-MOTOR1",
    bytes.fromhex(
        "AA 29 20 01 01 00 00 39 30 00 00 0C FE FF FF 34 12 83 00 02 00 00 00 "
        "03 00 00 00 01 00 00 00 2A 00 00 00 07 00 00 00 09 00 00 00 11 55"
    ),
    "bench state 40B LE: motor 1 online, pos 12345, vel -500, cur 0x1234, "
    "status 0x0083, fault 2, txerr 3, fb 1, samples 42, submit 7, send 9",
)
V1_GRIPPER_PING_ID1 = FrameFixture(
    "V1-GRIPPER-PING-ID1", bytes.fromhex("AA 02 30 01 73 55"), MCU_SOURCE
)
V1_GRIPPER_PING_RSP_ID1 = FrameFixture(
    "V1-GRIPPER-PING-RSP-ID1",
    bytes.fromhex("AA 04 30 00 01 00 8C 55"),
    "gripper ping response: result OK, id 1, servo_error 0",
)
V1_GRIPPER_READ_ID1_POS = FrameFixture(
    "V1-GRIPPER-READ-ID1-POS",
    bytes.fromhex("AA 04 31 01 38 02 8B 55"),
    "gripper read: id 1, register 0x38, length 2",
)
V1_GRIPPER_READ_RSP_ID1 = FrameFixture(
    "V1-GRIPPER-READ-RSP-ID1",
    bytes.fromhex("AA 06 31 00 01 00 18 05 F0 55"),
    "gripper read response: OK, id 1, servo_error 0, data 18 05",
)
V1_GRIPPER_MOVE_ID1 = FrameFixture(
    "V1-GRIPPER-MOVE-ID1",
    bytes.fromhex("AA 07 33 01 08 00 03 E8 14 41 55"),
    "gripper move: id 1, position 0x0800 (BE), speed 1000 (BE), accel 20",
)
V1_GRIPPER_TORQUE_ID1_ON = FrameFixture(
    "V1-GRIPPER-TORQUE-ID1-ON", bytes.fromhex("AA 03 34 01 01 DA 55"), MCU_SOURCE
)
V1_BAD_CRC = FrameFixture("V1-BAD-CRC", bytes.fromhex("AA 01 00 01 55"), MCU_SOURCE)
V1_BAD_ETX = FrameFixture("V1-BAD-ETX", bytes.fromhex("AA 01 00 00 54"), MCU_SOURCE)
V1_LEN_ZERO = FrameFixture("V1-LEN-ZERO", bytes.fromhex("AA 00"), MCU_SOURCE)
V1_LEN_128 = FrameFixture("V1-LEN-128", bytes.fromhex("AA 80"), MCU_SOURCE)

FIXTURE_SHA256 = {
    "V1-HELLO-REQ": "cd45f5af3c93c9611a678098cc734a15eb3983e6fbb0f5316ed051da4c983508",
    "V1-HELLO-RSP": "f534bc1bb81d13375e5655607c3ed96b1e732638b636795cc9d75158efb8f3d5",
    "V1-RESULT-OK-CMD02": "409719564cb8ea3e38fc0f23bd1b8045be8dd37c8c0010f471e9aae3c4b88415",
    "V1-STATE-READY-ZERO": "fee969e408a5a1a202c401e0705ef0d4189c19c4a6cad339b646f81c56c80546",
    "V1-STATE-READY-HOMED-1D": "3862b08f19932809581ec60089ca43d5dba6c26bbb4cdb13a1ed850b63f456d9",
    "V1-STATE-STARTUP-FAULT": "b37a9d5e1043c3ff3b0a6e49695ef32fc2e269c8c39797ad3505870cee379fd4",
    "V1-STATE-ESTOP-FAULT": "bc49cfdf79baf78e1c410a08c5e6343dffa8fcd24a673c1e57661bbee81a7e96",
    "V1-ENABLE-MASK-1D": "8e3d3ab77347d896f4de73e70cc929c7091e1d3192641c27c8f1939b1eb2fce2",
    "V1-HOME-MASK-1D": "90830fec9e3030ad272a61c7f69d5c940504ecb785c7d31556edeaec8521501a",
    "V1-TARGET-MIXED-SIGNS": "4893de4ff5484ec37c503aae12175d3092e51a44785240b32c027cce0df602c8",
    "V1-TARGET-FORBIDDEN-J2": "6cb5da9cac171f7bf22d80ff005250ffa67737b3ba83c0086dddd9b0c4e31e84",
    "V1-TARGET-FORBIDDEN-J6": "c616750f7cf0d477132fde68f01535b9f943ae19b29479f3d273a5838090f064",
    "V1-BENCH-QUERY-MOTOR1": "8f9c8f1ae29345517f290bf51de81cd8cb98f38ac9d6e62ac7838c2da08f4389",
    "V1-BENCH-ENABLE-MOTOR1": "a32aa82a553f389470bfe86a61c519dfae7971f11597081090303901bd92dde0",
    "V1-BENCH-MOVE-REL-MOTOR1": "fd3e6f77a16bb499363ea962945db15a79e28d48d16f5b98d423f1ba9b500ddf",
    "V1-BENCH-GET-PROTECTION-MOTOR3": (
        "aaa5797df371953600087dff83d1e90489a116e806c5e9095124f02890952c0e"
    ),
    "V1-BENCH-GET-PROTECTION-RSP-MOTOR3": (
        "89be2b8b2bb608a25893d40114036531e899c53069118ddd96d8e4d94f75df38"
    ),
    "V1-BENCH-SET-PROTECTION": "ca9c6bd4d6d305ee04776a633dce5b988df824009738fcd01e80ce806786dc5b",
    "V1-BENCH-QUERY-RSP-MOTOR1": "48daf24c888d45d48fc78150ee843ee420f259e0b1c64d447c97e97ece0bcbe3",
    "V1-GRIPPER-PING-ID1": "a10b33d54cbbd9892df1a9c289819a5fe077295040d654b8efbab7b953fd86e7",
    "V1-GRIPPER-PING-RSP-ID1": "0a2a856b8f0558fd15047cb2dc0d63fcee501521916d8f08df1cc40546211018",
    "V1-GRIPPER-READ-ID1-POS": "113f24a43302a55bf5f097fe7ffa1400658dcd396de99e340f7e8c116c0e8dd8",
    "V1-GRIPPER-READ-RSP-ID1": "6d58eb199562ba3d3bb5f44baaf9184b36c094533ef478eb2796b59dce4eaa2d",
    "V1-GRIPPER-MOVE-ID1": "f43fdece630b61ad9f0ad58fca7d5b08ce455709adf4d17d7bf597678a688489",
    "V1-GRIPPER-TORQUE-ID1-ON": "90c6af7059e25525d6bf83fb94944c3ee8d50e55be0b2c3a9d93d968e7ca3e47",
    "V1-BAD-CRC": "7676f28679315a2fc928fd632e7094088adb557ba7c432b41bc44189a5fba188",
    "V1-BAD-ETX": "1208f3725e920c35b2084894cc8f0effd848a06e78ab1af1fd1409e917ab0863",
    "V1-LEN-ZERO": "0d2f5112a34074511256c9482485e4d03936d202729aa169f1e2a9fa6018e2ce",
    "V1-LEN-128": "93a9d25d89ad218b7966b1a5286921a73010439034ded629865f26b7ce0ea179",
}
"""Registered SHA-256 for every fixture ID in this module."""


def all_fixtures() -> tuple[FrameFixture, ...]:
    return (
        V1_HELLO_REQUEST,
        V1_HELLO_RESPONSE,
        V1_RESULT_OK_CMD02,
        V1_STATE_READY_ZERO,
        V1_STATE_READY_HOMED_1D,
        V1_STATE_STARTUP_FAULT,
        V1_STATE_ESTOP_FAULT,
        V1_ENABLE_MASK_1D,
        V1_HOME_MASK_1D,
        V1_TARGET_MIXED_SIGNS,
        V1_TARGET_FORBIDDEN_J2,
        V1_TARGET_FORBIDDEN_J6,
        V1_BENCH_QUERY_MOTOR1,
        V1_BENCH_ENABLE_MOTOR1,
        V1_BENCH_MOVE_REL_MOTOR1,
        V1_BENCH_GET_PROTECTION_MOTOR3,
        V1_BENCH_GET_PROTECTION_RSP_MOTOR3,
        V1_BENCH_SET_PROTECTION,
        V1_BENCH_QUERY_RSP_MOTOR1,
        V1_GRIPPER_PING_ID1,
        V1_GRIPPER_PING_RSP_ID1,
        V1_GRIPPER_READ_ID1_POS,
        V1_GRIPPER_READ_RSP_ID1,
        V1_GRIPPER_MOVE_ID1,
        V1_GRIPPER_TORQUE_ID1_ON,
        V1_BAD_CRC,
        V1_BAD_ETX,
        V1_LEN_ZERO,
        V1_LEN_128,
    )
