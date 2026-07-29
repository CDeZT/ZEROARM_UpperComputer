"""Cross-platform user data paths."""

from pathlib import Path

from platformdirs import user_data_path


def default_data_root() -> Path:
    return Path(user_data_path("ZeroArm Desktop", "ZeroArm", roaming=False, ensure_exists=True))
