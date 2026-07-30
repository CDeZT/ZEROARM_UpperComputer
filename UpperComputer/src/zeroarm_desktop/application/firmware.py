"""Firmware artifact inspection and argument-array programmer runner."""

import hashlib
import re
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True, slots=True)
class FirmwareArtifact:
    path: Path
    sha256: str
    size: int
    extension: str


@dataclass(frozen=True, slots=True)
class FlashRequest:
    artifact: FirmwareArtifact
    expected_sha256: str
    tool_path: Path
    target_mcu: str
    stlink_sn: str | None
    verify: bool
    reset_after: bool


@dataclass(frozen=True, slots=True)
class FlashResult:
    success: bool
    command: tuple[str, ...]
    stdout: str
    stderr: str
    hello_after_reset: str | None


def inspect_firmware_artifact(path: Path) -> FirmwareArtifact:
    if not path.is_file():
        raise FileNotFoundError(f"firmware artifact missing: {path}")
    extension = path.suffix.lower()
    if extension not in {".elf", ".bin", ".hex"}:
        raise ValueError("firmware extension must be .elf, .bin, or .hex")
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    return FirmwareArtifact(path.resolve(), digest, path.stat().st_size, extension)


def build_programmer_command(request: FlashRequest) -> tuple[str, ...]:
    if request.artifact.sha256 != request.expected_sha256:
        raise ValueError("firmware hash mismatch")
    if request.target_mcu != "STM32G474":
        raise ValueError("unsupported target MCU")
    if not request.tool_path.name:
        raise ValueError("programmer tool path is empty")
    command = [
        str(request.tool_path),
        "-c",
        f"port=SWD sn={request.stlink_sn}" if request.stlink_sn else "port=SWD",
        "-w",
        str(request.artifact.path),
    ]
    if request.verify:
        command.append("-v")
    if request.reset_after:
        command.extend(["-rst", "-run"])
    return tuple(command)


class FirmwareService:
    def __init__(
        self,
        runner: Callable[[Sequence[str]], tuple[int, str, str]],
        *,
        hello_probe: Callable[[], str] | None = None,
    ) -> None:
        self._runner = runner
        self._hello_probe = hello_probe

    def flash(self, request: FlashRequest) -> FlashResult:
        command = build_programmer_command(request)
        code, stdout, stderr = self._runner(command)
        hello = None
        if code == 0 and request.reset_after and self._hello_probe is not None:
            hello = self._hello_probe()
            if hello != "ZEROARM/1.0":
                return FlashResult(False, command, stdout, stderr, hello)
        return FlashResult(code == 0, command, stdout, stderr, hello)


def parse_programmer_success(stdout: str) -> bool:
    return bool(re.search(r"File download complete|Download verified successfully", stdout, re.I))
