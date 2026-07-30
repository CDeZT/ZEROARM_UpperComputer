# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller specification for the ZeroArm Desktop portable bundle."""

from pathlib import Path

from PyInstaller.utils.hooks import collect_all

project_root = Path(SPECPATH).resolve().parent
resources = project_root / "resources"

datas = [(str(resources), "resources")]
binaries = []
hiddenimports = [
    "scipy.optimize",
    "scipy.optimize._lsq",
    "pyqtgraph.opengl",
    "OpenGL",
    "serial.tools.list_ports",
]

for package in ("PySide6", "pyqtgraph", "OpenGL"):
    package_datas, package_binaries, package_hidden = collect_all(package)
    datas += package_datas
    binaries += package_binaries
    hiddenimports += package_hidden

a = Analysis(
    [str(project_root / "src" / "zeroarm_desktop" / "__main__.py")],
    pathex=[str(project_root / "src")],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="ZeroArmDesktop",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name="ZeroArmDesktop",
)
