"""Diagnostic snapshot, bundle hashes, and path redaction tests."""

import json
import zipfile
from pathlib import Path

from zeroarm_desktop.application.diagnostics import (
    DiagnosticsSnapshot,
    create_diagnostic_bundle,
)


def test_diagnostic_bundle_is_redacted_and_hashed(tmp_path: Path) -> None:
    snapshot = DiagnosticsSnapshot(
        "1.0",
        "ready",
        "C:\\Users\\Alice\\firmware",
        {"path": "C:/Users/Alice/data"},
        {},
        (),
    )
    output = create_diagnostic_bundle(snapshot, tmp_path / "bundle.zip")
    with zipfile.ZipFile(output) as archive:
        diagnostics = archive.read("diagnostics.json").decode()
        manifest = json.loads(archive.read("manifest.json"))
        assert "Alice" not in diagnostics
        assert "<USER_HOME>" in diagnostics
        assert set(manifest["files"]) == {"diagnostics.json", "versions.json"}
