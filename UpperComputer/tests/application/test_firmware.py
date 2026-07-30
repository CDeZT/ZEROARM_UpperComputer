"""Firmware inspection, argument arrays, and fake process runner tests."""

from pathlib import Path

import pytest

from zeroarm_desktop.application.firmware import (
    FirmwareService,
    FlashRequest,
    build_programmer_command,
    inspect_firmware_artifact,
    parse_programmer_success,
)


def test_inspect_and_build_command(tmp_path: Path) -> None:
    artifact_path = tmp_path / "zero_arm_mcu.elf"
    artifact_path.write_bytes(b"\x7fELF-test")
    artifact = inspect_firmware_artifact(artifact_path)
    request = FlashRequest(
        artifact,
        artifact.sha256,
        Path("STM32_Programmer_CLI.exe"),
        "STM32G474",
        "SN123",
        True,
        True,
    )
    command = build_programmer_command(request)
    assert command[0] == "STM32_Programmer_CLI.exe"
    assert "sn=SN123" in command[2]
    assert str(artifact_path.resolve()) in command
    assert "-v" in command
    assert "-rst" in command


def test_hash_mismatch_and_fake_runner(tmp_path: Path) -> None:
    artifact_path = tmp_path / "zero_arm_mcu.bin"
    artifact_path.write_bytes(b"firmware")
    artifact = inspect_firmware_artifact(artifact_path)
    with pytest.raises(ValueError, match="hash mismatch"):
        build_programmer_command(
            FlashRequest(
                artifact,
                "0" * 64,
                Path("tool"),
                "STM32G474",
                None,
                True,
                False,
            )
        )
    service = FirmwareService(
        lambda command: (0, "File download complete", ""),
        hello_probe=lambda: "ZEROARM/1.0",
    )
    result = service.flash(
        FlashRequest(
            artifact,
            artifact.sha256,
            Path("tool"),
            "STM32G474",
            None,
            True,
            True,
        )
    )
    assert result.success
    assert result.hello_after_reset == "ZEROARM/1.0"
    assert parse_programmer_success(result.stdout)
