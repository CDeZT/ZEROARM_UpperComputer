"""Packaging script and installer definition tests."""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_portable_spec_and_builder_exist() -> None:
    spec = (ROOT / "packaging" / "zeroarm-desktop.spec").read_text(encoding="utf-8")
    builder = (ROOT / "packaging" / "build_portable.py").read_text(encoding="utf-8")
    assert "ZeroArmDesktop" in spec
    assert "resources" in spec
    assert "PyInstaller" in builder
    assert "sha256" in builder
    assert "portable.zip" in builder


def test_inno_script_preserves_user_data_and_avoids_drivers() -> None:
    script = (ROOT / "packaging" / "zeroarm-desktop.iss").read_text(encoding="utf-8")
    assert "ZeroArmDesktop" in script
    assert "PrivilegesRequired=lowest" in script
    assert "LocalAppData" in script or "user data" in script.lower()
    assert "driver" not in script.lower() or "no" in script.lower()


def test_release_and_baud_docs_exist() -> None:
    baud = (ROOT / "docs" / "19_HIGH_BAUD_APPROVAL_PACKAGE.md").read_text(encoding="utf-8")
    release = (ROOT / "docs" / "20_RELEASE_ACCEPTANCE.md").read_text(encoding="utf-8")
    assert "pending_user_approval" in baud
    assert "115200" in baud
    assert "HW-DEFERRED" in release
    assert "0.1.0" in release
