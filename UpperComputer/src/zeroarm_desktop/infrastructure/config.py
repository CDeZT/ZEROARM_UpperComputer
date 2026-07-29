"""Versioned user configuration with explicit safe defaults."""

from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class AppConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal[1] = 1
    transport_kind: Literal["mock", "serial"] = "mock"
    serial_port: str | None = None
    serial_baudrate: int = Field(default=115200, gt=0)
    poll_rate_hz: Literal[20, 50, 100] = 20
    auto_reconnect: bool = False
    theme: Literal["dark", "light"] = "dark"
    plot_window_seconds: int = Field(default=60, ge=5, le=600)


class ConfigStore:
    def __init__(self, path: Path) -> None:
        self.path = path

    def load(self) -> AppConfig:
        if not self.path.exists():
            return AppConfig()
        return AppConfig.model_validate_json(self.path.read_text(encoding="utf-8"))

    def save(self, config: AppConfig) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.path.with_suffix(self.path.suffix + ".tmp")
        temporary.write_text(config.model_dump_json(indent=2), encoding="utf-8")
        temporary.replace(self.path)

    def export_dict(self, config: AppConfig) -> dict[str, object]:
        return config.model_dump(mode="json")
