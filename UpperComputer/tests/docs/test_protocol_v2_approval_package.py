"""Document consistency checks for the protocol V2 approval package."""

from pathlib import Path

ROOT = Path(__file__).parents[2]
PACKAGE = ROOT / "docs" / "18_PROTOCOL_V2_APPROVAL_PACKAGE.md"
FIXTURE_README = ROOT / "docs" / "protocol_v2_fixtures" / "README.md"
PROPOSAL = ROOT / "docs" / "04_PROTOCOL_V2_PROPOSAL.md"


def test_approval_package_exists_and_blocks_mcu_work() -> None:
    text = PACKAGE.read_text(encoding="utf-8")
    assert "pending_user_approval" in text
    assert "确认实施协议 V2" in text
    assert "不修改 MCU 源码" in text
    assert "0x10" in text and "GET_CAPABILITIES" in text
    assert "0x11" in text and "GET_STATE_V2" in text
    assert "device_time_ms" in text
    assert "sample_seq" in text
    assert "parser inter-byte timeout" in text.lower() or "帧内超时" in text
    assert "UNKNOWN_OUTCOME" in text
    assert "115200" in text


def test_fixture_registry_lists_required_ids() -> None:
    text = FIXTURE_README.read_text(encoding="utf-8")
    for fixture_id in (
        "V2-CAP-REQ",
        "V2-CAP-RSP",
        "V2-STATE-REQ",
        "V2-STATE-RSP",
        "V2-PING-REQ",
        "V2-PING-RSP",
        "V2-BAD-MAJOR",
        "V2-TIMEOUT-RESYNC",
        "V2-SEQ-ECHO",
    ):
        assert fixture_id in text


def test_approval_package_is_consistent_with_proposal() -> None:
    package = PACKAGE.read_text(encoding="utf-8")
    proposal = PROPOSAL.read_text(encoding="utf-8")
    for token in ("GET_CAPABILITIES", "GET_STATE_V2", "TELEMETRY_V2", "EVENT_V2", "大端"):
        assert token in package
        assert token in proposal
