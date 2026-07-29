"""Dallas/Maxim CRC-8 used by the current MCU protocol."""

CRC8_DALLAS_MAXIM_CHECK = 0xA1


def crc8_dallas_maxim(data: bytes | bytearray | memoryview) -> int:
    """Return reflected Dallas/Maxim CRC-8 with an initial value of zero."""
    crc = 0
    for value in data:
        for _ in range(8):
            mix = (crc ^ value) & 0x01
            crc >>= 1
            if mix:
                crc ^= 0x8C
            value >>= 1
    return crc
