"""Dataset episode inspector and export page."""

from datetime import UTC, datetime

from PySide6.QtWidgets import QLabel, QPushButton, QVBoxLayout, QWidget

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
from zeroarm_desktop.infrastructure.paths import default_data_root


class DatasetPage(QWidget):
    def __init__(self) -> None:
        super().__init__()
        self.setObjectName("page_dataset")
        title = QLabel("数据集接口")
        title.setObjectName("page_title")
        self.status = QLabel("模型动作默认 target_transport=mock")
        self.status.setObjectName("dataset_status")
        export_json = QPushButton("导出示例Episode JSON")
        export_json.setObjectName("export_episode_json")
        export_json.clicked.connect(self.export_json)
        export_csv = QPushButton("导出示例Episode CSV")
        export_csv.setObjectName("export_episode_csv")
        export_csv.clicked.connect(self.export_csv)
        export_npz = QPushButton("导出示例Episode NPZ/JSON")
        export_npz.setObjectName("export_episode_npz")
        export_npz.clicked.connect(self.export_npz)
        layout = QVBoxLayout(self)
        for widget in (title, self.status, export_json, export_csv, export_npz):
            layout.addWidget(widget)
        layout.addStretch()
        self._episode = self._demo_episode()

    def export_json(self) -> None:
        path = default_data_root() / "datasets" / "demo_episode.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(episode_to_json(self._episode), encoding="utf-8")
        self.status.setText(f"JSON已导出 | issues={validate_episode(self._episode)}")

    def export_csv(self) -> None:
        path = default_data_root() / "datasets" / "demo_episode.csv"
        export_episode_csv(self._episode, path)
        self.status.setText(f"CSV已导出 | {path.name}")

    def export_npz(self) -> None:
        path = default_data_root() / "datasets" / "demo_episode.npz.json"
        export_episode_npz(self._episode, path)
        self.status.setText(f"NPZ/JSON已导出 | {path.name}")

    @staticmethod
    def _demo_episode() -> Episode:
        observation = Observation(
            (0, 1_570_770, 0, 0, 0, 0),
            1,
            0,
            100,
            datetime.now(UTC),
            None,
            None,
        )
        action = Action("set_joint_target", (10_000, 1_570_770, 0, 0, 0, 0), 0, "mock")
        result = StepResult(True, 0, True)
        return Episode(
            1,
            "demo-episode",
            "mock",
            (EpisodeStep(observation, action, result),),
            {"model_action_default_transport": "mock"},
        )
