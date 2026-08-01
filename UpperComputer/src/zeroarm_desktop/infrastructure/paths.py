"""Cross-platform user data and packaged resource paths."""

import os
import sys
from pathlib import Path

from platformdirs import user_data_path


def default_data_root() -> Path:
    override = os.environ.get("ZEROARM_DATA_ROOT")
    if override:
        root = Path(override).expanduser()
        root.mkdir(parents=True, exist_ok=True)
        return root
    return Path(user_data_path("ZeroArm Desktop", "ZeroArm", roaming=False, ensure_exists=True))


def application_root() -> Path:
    """Return the install/project root for both source and frozen builds."""
    if getattr(sys, "frozen", False):
        meipass = getattr(sys, "_MEIPASS", None)
        if meipass is not None:
            return Path(meipass)
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parents[3]


def resource_root() -> Path:
    return application_root() / "resources"


def robot_model_root() -> Path:
    return resource_root() / "robot_model"
