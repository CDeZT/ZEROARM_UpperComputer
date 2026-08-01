"""Dataset episode inspector built from teach recordings or demo data."""

from datetime import UTC, datetime

from PySide6.QtWidgets import QLabel, QPushButton, QVBoxLayout, QWidget

from zeroarm_desktop.application.teach import RawTeachRecording
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
from zeroarm_desktop.gui.viewmodels.teach import TeachViewModel
from zeroarm_desktop.infrastructure.paths import default_data_root


class DatasetPage(QWidget):
    def __init__(self, teach_view_model: TeachViewModel) -> None:
        super().__init__()
        self.setObjectName("page_dataset")
        self.teach_view_model = teach_view_model
        title = QLabel("数据集接口")
        title.setObjectName("page_title")
        self.status = QLabel("可从最近示教 raw 生成 Episode | 模型动作默认 target_transport=mock")
        self.status.setObjectName("dataset_status")
        self.status.setWordWrap(True)
        from_teach = QPushButton("从示教记录生成 Episode")
        from_teach.setObjectName("dataset_from_teach_button")
        from_teach.clicked.connect(self.load_from_teach)
        export_json = QPushButton("导出 Episode JSON")
        export_json.setObjectName("export_episode_json")
        export_json.clicked.connect(self.export_json)
        export_csv = QPushButton("导出 Episode CSV")
        export_csv.setObjectName("export_episode_csv")
        export_csv.clicked.connect(self.export_csv)
        export_npz = QPushButton("导出 Episode NPZ/JSON")
        export_npz.setObjectName("export_episode_npz")
        export_npz.clicked.connect(self.export_npz)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(36, 32, 36, 32)
        for widget in (title, self.status, from_teach, export_json, export_csv, export_npz):
            layout.addWidget(widget)
        layout.addStretch()
        self._episode = self._demo_episode()

    def load_from_teach(self) -> None:
        recording = self.teach_view_model.recorder.last_recording
        if recording is None:
            self.status.setText("无示教记录 | 请先在拖动示教页完成 RECORDING→REVIEW")
            return
        self._episode = episode_from_teach(recording)
        issues = validate_episode(self._episode)
        self.status.setText(
            f"已从示教生成 Episode | steps={len(self._episode.steps)} | "
            f"mask=0x{recording.joint_mask:02X} | issues={issues or 'none'}"
        )

    def export_json(self) -> None:
        path = default_data_root() / "datasets" / f"{self._episode.episode_id}.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(episode_to_json(self._episode), encoding="utf-8")
        self.status.setText(
            f"JSON已导出 {path.name} | issues={validate_episode(self._episode) or 'none'}"
        )

    def export_csv(self) -> None:
        path = default_data_root() / "datasets" / f"{self._episode.episode_id}.csv"
        export_episode_csv(self._episode, path)
        self.status.setText(f"CSV已导出 | {path.name}")

    def export_npz(self) -> None:
        path = default_data_root() / "datasets" / f"{self._episode.episode_id}.npz.json"
        export_episode_npz(self._episode, path)
        self.status.setText(f"NPZ/JSON已导出 | {path.name}")

    @staticmethod
    def _demo_episode() -> Episode:
        observation = Observation(
            (0, 0, 0, 0, 0, 0),
            1,
            0,
            100,
            datetime.now(UTC),
            None,
            None,
        )
        action = Action("set_joint_target", (10_000, 0, 0, 0, 0, 0), 0, "mock")
        result = StepResult(True, 0, True)
        return Episode(
            1,
            "demo-episode",
            "mock",
            (EpisodeStep(observation, action, result),),
            {"model_action_default_transport": "mock"},
        )


def episode_from_teach(recording: RawTeachRecording) -> Episode:
    steps: list[EpisodeStep] = []
    for sample in recording.samples:
        observation = Observation(
            sample.joint_urad,
            sample.run_state_raw,
            0,
            sample.pc_monotonic_ns,
            sample.wall_utc,
            sample.device_time_ms,
            sample.sample_sequence,
        )
        action = Action("teach_sample", sample.joint_urad, None, "none")
        steps.append(EpisodeStep(observation, action, StepResult(True, None, True)))
    return Episode(
        1,
        f"teach-{recording.sha256[:12]}",
        "teach",
        tuple(steps),
        {
            "parent_raw_sha256": recording.sha256,
            "joint_mask": recording.joint_mask,
            "dropped_samples": recording.dropped_samples,
            "model_action_default_transport": "mock",
        },
    )
