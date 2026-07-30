"""Episode schema, validation, and export tests."""

from datetime import UTC, datetime
from pathlib import Path

from zeroarm_desktop.domain.dataset import (
    Action,
    Episode,
    EpisodeStep,
    Observation,
    StepResult,
    episode_to_json,
    export_episode_csv,
    export_episode_npz,
    validate_episode,
)


def _episode(transport: str = "mock") -> Episode:
    observation = Observation(
        (0, 1_570_770, 0, 0, 0, 0),
        1,
        0,
        1,
        datetime.now(UTC),
        None,
        None,
    )
    action = Action("set_joint_target", (1, 1_570_770, 0, 0, 0, 0), 0, transport)
    result = StepResult(True, 0, True)
    return Episode(1, "ep-1", "mock", (EpisodeStep(observation, action, result),), {})


def test_episode_validation_and_exports(tmp_path: Path) -> None:
    episode = _episode()
    assert not validate_episode(episode)
    payload = episode_to_json(episode)
    assert "ep-1" in payload
    assert "device_time_ms" in payload
    export_episode_csv(episode, tmp_path / "episode.csv")
    export_episode_npz(episode, tmp_path / "episode.npz.json")
    assert (tmp_path / "episode.csv").exists()
    assert (tmp_path / "episode.npz.json").exists()
    assert "step_0_serial_action_forbidden" in validate_episode(_episode("serial"))
