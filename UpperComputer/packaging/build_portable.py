"""Build and verify the portable Windows bundle."""

from __future__ import annotations

import hashlib
import json
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
    command = [
        sys.executable,
        "-m",
        "PyInstaller",
        "--noconfirm",
        "--clean",
        str(SPEC),
    ]
    subprocess.run(command, cwd=PROJECT_ROOT, check=True)


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

    # onedir layout places datas under _internal; frozen runtime resolves via sys._MEIPASS.
    return {
        "exe": str(exe.relative_to(PROJECT_ROOT)).replace("\\", "/"),
        "exe_sha256": sha256_file(exe),
        "exe_size_bytes": exe.stat().st_size,
        "resources_manifest": str(resources.relative_to(PROJECT_ROOT)).replace("\\", "/"),
        "resources_manifest_present": True,
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
    }
    manifest = {
        "schema_version": 1,
        "product": "ZeroArm Desktop",
        "version": __version__,
        "generated_utc": datetime.now(UTC).isoformat(),
        "bundle_dir": "dist/ZeroArmDesktop",
        "zip": ZIP_PATH.name,
        "zip_sha256": sha256_file(ZIP_PATH),
        "zip_size_bytes": ZIP_PATH.stat().st_size,
        "bundle": bundle_info,
        "licenses": licenses,
        "notes": [
            "Portable bundle does not require system Python.",
            "Mock demo is the default safe mode.",
            "Protocol V2 MCU implementation remains approval-gated.",
        ],
    }
    MANIFEST_PATH.write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    return manifest


def main() -> int:
    DIST_DIR.mkdir(parents=True, exist_ok=True)
    BUILD_DIR.mkdir(parents=True, exist_ok=True)
    build()
    bundle_info = verify_bundle()
    manifest = write_zip_and_manifest(bundle_info)
    print(json.dumps(manifest, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
