"""OperationEvidence schema and log tests."""

from zeroarm_desktop.domain.evidence import EvidenceLog, OutcomeStatus, make_evidence


def test_evidence_log_is_bounded_and_serializable() -> None:
    log = EvidenceLog(capacity=2)
    log.append(make_evidence(command_name="HOME", outcome=OutcomeStatus.ACCEPTED, result_raw=0))
    log.append(make_evidence(command_name="TEACH_START", outcome=OutcomeStatus.COMPLETED))
    log.append(make_evidence(command_name="SET_JOINT_TARGET", outcome=OutcomeStatus.TIMEOUT))
    assert len(log.items) == 2
    assert log.items[0].command_name == "TEACH_START"
    text = log.to_json()
    assert '"schema_version": 1' in text
    assert "SET_JOINT_TARGET" in text
