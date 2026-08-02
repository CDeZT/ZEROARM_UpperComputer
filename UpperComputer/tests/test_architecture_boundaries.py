"""Executable dependency rules for the layered desktop architecture."""

import ast
from pathlib import Path

DOMAIN_ROOT = Path(__file__).parents[1] / "src" / "zeroarm_desktop" / "domain"
SHELL_PATH = Path(__file__).parents[1] / "src" / "zeroarm_desktop" / "gui" / "shell.py"
OUTER_LAYER_PREFIXES = (
    "zeroarm_desktop.application",
    "zeroarm_desktop.gui",
    "zeroarm_desktop.infrastructure",
    "zeroarm_desktop.protocol",
    "zeroarm_desktop.transport",
)


def test_domain_layer_does_not_import_outer_layers() -> None:
    violations: list[str] = []
    for source_path in sorted(DOMAIN_ROOT.glob("*.py")):
        tree = ast.parse(source_path.read_text(encoding="utf-8"), filename=str(source_path))
        for node in ast.walk(tree):
            imported_modules: tuple[str, ...] = ()
            if isinstance(node, ast.ImportFrom) and node.module:
                imported_modules = (node.module,)
            elif isinstance(node, ast.Import):
                imported_modules = tuple(alias.name for alias in node.names)
            for module in imported_modules:
                if module.startswith(OUTER_LAYER_PREFIXES):
                    violations.append(f"{source_path.name}:{node.lineno} imports {module}")

    assert violations == []


def test_shell_does_not_bypass_command_service_for_home() -> None:
    tree = ast.parse(SHELL_PATH.read_text(encoding="utf-8"), filename=str(SHELL_PATH))
    direct_home_calls = [
        node.lineno
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr == "send_home"
    ]

    assert direct_home_calls == []
