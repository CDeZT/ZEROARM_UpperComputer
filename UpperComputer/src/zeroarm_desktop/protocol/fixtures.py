"""Stable V1 frame fixtures derived from the current MCU implementation."""

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class FrameFixture:
    fixture_id: str
    raw: bytes
    source: str


MCU_SOURCE = "zero_arm_mcu Protocol/Src/protocol.c and messages.c, inspected 2026-07-29"
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
V1_BAD_CRC = FrameFixture("V1-BAD-CRC", bytes.fromhex("AA 01 00 01 55"), MCU_SOURCE)
V1_BAD_ETX = FrameFixture("V1-BAD-ETX", bytes.fromhex("AA 01 00 00 54"), MCU_SOURCE)
V1_LEN_ZERO = FrameFixture("V1-LEN-ZERO", bytes.fromhex("AA 00"), MCU_SOURCE)
V1_LEN_128 = FrameFixture("V1-LEN-128", bytes.fromhex("AA 80"), MCU_SOURCE)
