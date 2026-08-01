"""Packaging script and installer definition tests."""

from pathlib import Path

from zeroarm_desktop.cli import parse_launch_options
from zeroarm_desktop.version import __version__

ROOT = Path(__file__).resolve().parents[2]


def test_portable_spec_and_builder_exist() -> None:
    spec = (ROOT / "packaging" / "zeroarm-desktop.spec").read_text(encoding="utf-8")
    builder = (ROOT / "packaging" / "build_portable.py").read_text(encoding="utf-8")
    assert "ZeroArmDesktop" in spec
    assert "resources" in spec
    assert "PyInstaller" in builder
    assert "sha256" in builder
    assert "portable.zip" in builder
    assert "dry_run_inventory" in builder
    assert "SHA256SUMS" in builder


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
    assert __version__ in release
    assert (ROOT / "docs" / "USER_GUIDE.md").is_file()
    assert (ROOT / "docs" / "KNOWN_LIMITATIONS.md").is_file()
    assert (ROOT / "docs" / "CAPABILITY_MATRIX.md").is_file()


def test_cli_launch_options_parse() -> None:
    options = parse_launch_options(
        ["--mock", "--safe-mode", "--diagnostics", "--log-level", "debug"]
    )
    assert options.mock is True
    assert options.safe_mode is True
    assert options.diagnostics is True
    assert options.log_level == "debug"
    assert options.show_version is False


def test_packaging_dry_run_inventory() -> None:
    import importlib.util

    path = ROOT / "packaging" / "build_portable.py"
    spec = importlib.util.spec_from_file_location("zeroarm_build_portable", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    inventory = module.dry_run_inventory()
    assert inventory["version"] == __version__
    assert inventory["mode"] == "dry_run_inventory"
    assert any("USER_GUIDE.md" in item for item in inventory["required_present"])
