"""Build and verify the portable Windows bundle."""

from __future__ import annotations

import hashlib
import json
import platform
import shutil
import subprocess
import sys
import zipfile
from datetime import UTC, datetime
from pathlib import Path

from zeroarm_desktop.version import __version__

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DIST_DIR = PROJECT_ROOT / "dist"
BUILD_DIR = PROJECT_ROOT / "build"
SPEC = PROJECT_ROOT / "packaging" / "zeroarm-desktop.spec"
BUNDLE_DIR = DIST_DIR / "ZeroArmDesktop"
ZIP_PATH = DIST_DIR / f"ZeroArmDesktop-{__version__}-portable.zip"
MANIFEST_PATH = DIST_DIR / f"ZeroArmDesktop-{__version__}-portable.manifest.json"
SHA256SUMS_PATH = DIST_DIR / "SHA256SUMS.txt"
DOCS_TO_BUNDLE = (
    "docs/USER_GUIDE.md",
    "docs/KNOWN_LIMITATIONS.md",
    "docs/CAPABILITY_MATRIX.md",
    "packaging/THIRD_PARTY_LICENSES.md",
)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        while True:
            chunk = stream.read(1024 * 1024)
            if not chunk:
                break
            digest.update(chunk)
    return digest.hexdigest()


def build() -> None:
    if platform.system() != "Windows":
        print(
            "warning: portable Windows EXE is intended to be built on Windows; "
            f"current host is {platform.system()}",
            file=sys.stderr,
        )
    command = [
        sys.executable,
        "-m",
        "PyInstaller",
        "--noconfirm",
        "--clean",
        str(SPEC),
    ]
    subprocess.run(command, cwd=PROJECT_ROOT, check=True)


def stage_release_docs() -> list[str]:
    staged: list[str] = []
    docs_dir = BUNDLE_DIR / "docs"
    licenses_dir = BUNDLE_DIR / "licenses"
    docs_dir.mkdir(parents=True, exist_ok=True)
    licenses_dir.mkdir(parents=True, exist_ok=True)
    for relative in DOCS_TO_BUNDLE:
        source = PROJECT_ROOT / relative
        if not source.is_file():
            raise FileNotFoundError(f"release document missing: {relative}")
        if relative.endswith("THIRD_PARTY_LICENSES.md"):
            target = licenses_dir / source.name
        else:
            target = docs_dir / source.name
        shutil.copy2(source, target)
        staged.append(str(target.relative_to(PROJECT_ROOT)).replace("\\", "/"))
    return staged


def verify_bundle() -> dict[str, object]:
    exe = BUNDLE_DIR / "ZeroArmDesktop.exe"
    candidates = [
        BUNDLE_DIR / "resources" / "robot_model" / "manifest.json",
        BUNDLE_DIR / "_internal" / "resources" / "robot_model" / "manifest.json",
    ]
    resources = next((path for path in candidates if path.is_file()), None)
    if not exe.is_file():
        raise FileNotFoundError(f"portable executable missing: {exe}")
    if resources is None:
        raise FileNotFoundError("robot model resources missing from portable bundle")

    staged_docs = stage_release_docs()
    # onedir layout places datas under _internal; frozen runtime resolves via sys._MEIPASS.
    return {
        "exe": str(exe.relative_to(PROJECT_ROOT)).replace("\\", "/"),
        "exe_sha256": sha256_file(exe),
        "exe_size_bytes": exe.stat().st_size,
        "resources_manifest": str(resources.relative_to(PROJECT_ROOT)).replace("\\", "/"),
        "resources_manifest_present": True,
        "docs_staged": staged_docs,
    }


def write_zip_and_manifest(bundle_info: dict[str, object]) -> dict[str, object]:
    if ZIP_PATH.exists():
        ZIP_PATH.unlink()
    with zipfile.ZipFile(ZIP_PATH, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for path in BUNDLE_DIR.rglob("*"):
            if path.is_file():
                archive.write(path, path.relative_to(DIST_DIR).as_posix())

    licenses = {
        "application": "Proprietary",
        "robot_model": "GPL-2.0",
        "bundled_runtime": "See third-party packages in uv.lock",
        "third_party_inventory": "packaging/THIRD_PARTY_LICENSES.md",
    }
    capability = {
        "protocol": "V1",
        "profile": "zeroarm_g474_v1_partial",
        "available_axes_mask": "0x1D",
        "serial_actions_default": "readonly",
        "mock_actions": True,
        "protocol_v2": "pending_user_approval",
    }
    manifest = {
        "schema_version": 2,
        "product": "ZeroArm Desktop",
        "version": __version__,
        "generated_utc": datetime.now(UTC).isoformat(),
        "host": {
            "system": platform.system(),
            "machine": platform.machine(),
            "python": platform.python_version(),
        },
        "bundle_dir": "dist/ZeroArmDesktop",
        "zip": ZIP_PATH.name,
        "zip_sha256": sha256_file(ZIP_PATH),
        "zip_size_bytes": ZIP_PATH.stat().st_size,
        "bundle": bundle_info,
        "capability": capability,
        "licenses": licenses,
        "notes": [
            "Portable bundle does not require system Python.",
            "Mock demo is the default safe mode.",
            "Protocol V2 MCU implementation remains approval-gated.",
            "Clean Windows smoke without system Python is required before external release.",
        ],
    }
    MANIFEST_PATH.write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    SHA256SUMS_PATH.write_text(
        "\n".join(
            [
                f"{manifest['zip_sha256']}  {ZIP_PATH.name}",
                f"{bundle_info['exe_sha256']}  ZeroArmDesktop/ZeroArmDesktop.exe",
                f"{sha256_file(MANIFEST_PATH)}  {MANIFEST_PATH.name}",
                "",
            ]
        ),
        encoding="utf-8",
    )
    return manifest


def dry_run_inventory() -> dict[str, object]:
    """Validate packaging inputs without invoking PyInstaller (cross-platform)."""
    required = [
        SPEC,
        PROJECT_ROOT / "packaging" / "zeroarm-desktop.iss",
        PROJECT_ROOT / "packaging" / "THIRD_PARTY_LICENSES.md",
        PROJECT_ROOT / "resources" / "robot_model" / "manifest.json",
        PROJECT_ROOT / "docs" / "USER_GUIDE.md",
        PROJECT_ROOT / "docs" / "KNOWN_LIMITATIONS.md",
        PROJECT_ROOT / "docs" / "CAPABILITY_MATRIX.md",
        PROJECT_ROOT / "docs" / "20_RELEASE_ACCEPTANCE.md",
    ]
    missing = [str(path.relative_to(PROJECT_ROOT)) for path in required if not path.is_file()]
    if missing:
        raise FileNotFoundError(f"packaging inputs missing: {missing}")
    return {
        "schema_version": 1,
        "mode": "dry_run_inventory",
        "version": __version__,
        "host": platform.system(),
        "required_present": [str(path.relative_to(PROJECT_ROOT)) for path in required],
        "pyinstaller_build_recommended_host": "Windows",
        "notes": [
            "Use --build on Windows to produce ZeroArmDesktop.exe and portable zip.",
            "Inno Setup compiles packaging/zeroarm-desktop.iss after portable build.",
        ],
    }


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    DIST_DIR.mkdir(parents=True, exist_ok=True)
    BUILD_DIR.mkdir(parents=True, exist_ok=True)
    if "--dry-run" in args or (platform.system() != "Windows" and "--build" not in args):
        inventory = dry_run_inventory()
        print(json.dumps(inventory, indent=2, ensure_ascii=False))
        if "--build" in args:
            build()
            bundle_info = verify_bundle()
            manifest = write_zip_and_manifest(bundle_info)
            print(json.dumps(manifest, indent=2, ensure_ascii=False))
        return 0
    build()
    bundle_info = verify_bundle()
    manifest = write_zip_and_manifest(bundle_info)
    print(json.dumps(manifest, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
