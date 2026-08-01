"""Shared test configuration."""

import os
from pathlib import Path

import pytest
from pytest import MonkeyPatch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


@pytest.fixture(autouse=True)
def _isolate_zeroarm_user_data(tmp_path: Path, monkeypatch: MonkeyPatch) -> None:
    """Never let a test write configuration or recordings to real user data."""
    monkeypatch.setenv("ZEROARM_DATA_ROOT", str(tmp_path / "zeroarm-user-data"))
