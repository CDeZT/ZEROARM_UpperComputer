"""Bounded diagnostics snapshot and redacted ZIP bundle generation."""

import hashlib
import json
import re
import zipfile
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path

from zeroarm_desktop.application.device_session import DeviceSession
from zeroarm_desktop.version import __version__


@dataclass(frozen=True, slots=True)
class DiagnosticsSnapshot:
    app_version: str
    session_state: str
    firmware: str | None
    session_statistics: dict[str, object]
    parser_statistics: dict[str, object]
    capability_gaps: tuple[str, ...]


def collect_diagnostics(session: DeviceSession | None) -> DiagnosticsSnapshot:
    if session is None:
        return DiagnosticsSnapshot(__version__, "disconnected", None, {}, {}, _GAPS)
    return DiagnosticsSnapshot(
        __version__,
        session.state.value,
        session.identity.hello_text if session.identity else None,
        asdict(session.statistics),
        asdict(session._parser.statistics),
        _GAPS,
    )


def create_diagnostic_bundle(snapshot: DiagnosticsSnapshot, output: Path) -> Path:
    output.parent.mkdir(parents=True, exist_ok=True)
    files = {
        "diagnostics.json": _redact(json.dumps(asdict(snapshot), ensure_ascii=False, indent=2)),
        "versions.json": json.dumps({"app": snapshot.app_version}, indent=2),
    }
    manifest = {
        "schema_version": 1,
        "generated_utc": datetime.now(UTC).isoformat(),
        "redaction_version": 1,
        "files": {
            name: hashlib.sha256(content.encode()).hexdigest() for name, content in files.items()
        },
    }
    with zipfile.ZipFile(output, "w", zipfile.ZIP_DEFLATED) as archive:
        for name, content in files.items():
            archive.writestr(name, content)
        archive.writestr("manifest.json", json.dumps(manifest, indent=2))
    return output


def _redact(text: str) -> str:
    text = re.sub(r'[A-Za-z]:\\+Users\\+[^" ]+', r"<USER_HOME>", text, flags=re.IGNORECASE)
    return re.sub(r"[A-Za-z]:/Users/[^/\" ]+", "<USER_HOME>", text, flags=re.IGNORECASE)


_GAPS = (
    "device_time: V1未提供",
    "sample_sequence: V1未提供",
    "velocity/current/online: V1未提供",
    "UART/CAN逐项计数: V1未提供",
    "Homing阶段: V1未提供",
)
