"""Operation evidence schema for auditable Mock/operator actions."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from enum import Enum
from uuid import uuid4

from zeroarm_desktop.domain.models import FirmwareIdentity


class OutcomeStatus(Enum):
    DENIED = "denied"
    REJECTED = "rejected"
    ACCEPTED = "accepted"
    COMPLETED = "completed"
    FAILED = "failed"
    TIMEOUT = "timeout"
    UNKNOWN_OUTCOME = "unknown_outcome"
    CANCELLED = "cancelled"


@dataclass(frozen=True, slots=True)
class OperationEvidence:
    operation_id: str
    firmware_identity: FirmwareIdentity | None
    profile_id: str
    calibration_hash: str
    authorization_text: str | None
    command_name: str
    result_raw: int | None
    outcome: OutcomeStatus
    before_generation: int | None
    after_generation: int | None
    notes: tuple[str, ...]
    created_wall_utc: datetime
    schema_version: int = 1


def make_evidence(
    *,
    command_name: str,
    outcome: OutcomeStatus,
    profile_id: str = "zeroarm_g474_v1_partial",
    calibration_hash: str = "mock-model-v1",
    firmware_identity: FirmwareIdentity | None = None,
    authorization_text: str | None = None,
    result_raw: int | None = None,
    before_generation: int | None = None,
    after_generation: int | None = None,
    notes: tuple[str, ...] = (),
) -> OperationEvidence:
    return OperationEvidence(
        operation_id=str(uuid4()),
        firmware_identity=firmware_identity,
        profile_id=profile_id,
        calibration_hash=calibration_hash,
        authorization_text=authorization_text,
        command_name=command_name,
        result_raw=result_raw,
        outcome=outcome,
        before_generation=before_generation,
        after_generation=after_generation,
        notes=notes,
        created_wall_utc=datetime.now(UTC),
    )


class EvidenceLog:
    """Bounded in-memory evidence ring for GUI/session export."""

    def __init__(self, capacity: int = 500) -> None:
        self._capacity = capacity
        self._items: list[OperationEvidence] = []

    def append(self, evidence: OperationEvidence) -> None:
        self._items.append(evidence)
        if len(self._items) > self._capacity:
            del self._items[: len(self._items) - self._capacity]

    def clear(self) -> None:
        self._items.clear()

    @property
    def items(self) -> tuple[OperationEvidence, ...]:
        return tuple(self._items)

    def to_json(self) -> str:
        def encode(value: object) -> object:
            if isinstance(value, datetime):
                return value.isoformat()
            if isinstance(value, Enum):
                return value.value
            if isinstance(value, FirmwareIdentity):
                return asdict(value)
            if isinstance(value, OperationEvidence):
                return encode(asdict(value))
            if isinstance(value, tuple | list):
                return [encode(item) for item in value]
            if isinstance(value, dict):
                return {key: encode(item) for key, item in value.items()}
            return value

        return json.dumps(
            {"schema_version": 1, "items": [encode(item) for item in self._items]},
            ensure_ascii=False,
            sort_keys=True,
            indent=2,
        )
