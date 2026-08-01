"""Command-line argument parsing for desktop startup modes."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from typing import Literal

LogLevel = Literal["debug", "info", "warning", "error"]


@dataclass(frozen=True, slots=True)
class LaunchOptions:
    """Normalized startup options used by bootstrap and packaging smoke."""

    mock: bool = False
    safe_mode: bool = False
    reset_layout: bool = False
    diagnostics: bool = False
    log_level: LogLevel = "info"
    show_version: bool = False


def build_argument_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="zeroarm-desktop",
        description="ZeroArm Desktop debugger and operator console",
    )
    parser.add_argument(
        "--version",
        action="store_true",
        help="print application version and exit",
    )
    parser.add_argument(
        "--mock",
        action="store_true",
        help="prefer Mock transport defaults on the connection page",
    )
    parser.add_argument(
        "--safe-mode",
        action="store_true",
        help="disable heavy optional surfaces for recovery diagnostics",
    )
    parser.add_argument(
        "--reset-layout",
        action="store_true",
        help="request default window geometry on next launch",
    )
    parser.add_argument(
        "--diagnostics",
        action="store_true",
        help="open diagnostics page after startup",
    )
    parser.add_argument(
        "--log-level",
        choices=("debug", "info", "warning", "error"),
        default="info",
        help="console log verbosity",
    )
    return parser


def parse_launch_options(argv: list[str] | None = None) -> LaunchOptions:
    parser = build_argument_parser()
    args = parser.parse_args(argv)
    return LaunchOptions(
        mock=bool(args.mock),
        safe_mode=bool(args.safe_mode),
        reset_layout=bool(args.reset_layout),
        diagnostics=bool(args.diagnostics),
        log_level=args.log_level,
        show_version=bool(args.version),
    )
