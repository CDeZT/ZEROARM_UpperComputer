"""SafetyGate denials, boundaries, Arm binding, and pure execution tests."""

from collections.abc import Callable
from dataclasses import replace
from datetime import UTC, datetime

import pytest
from hypothesis import given
from hypothesis import strategies as st

from zeroarm_desktop.application.device_session import SessionState
from zeroarm_desktop.domain.models import JointTarget, RobotSnapshot
from zeroarm_desktop.domain.safety import (
    AppMode,
    CommandFamily,
    CommandIntent,
    CommandService,
    SafetyContext,
    SafetyGate,
)


def _snapshot(generation: int = 1, received_ns: int = 100) -> RobotSnapshot:
    actual = (0, 1_570_770, 0, 0, 0, 0)
    return RobotSnapshot(
        generation,
        received_ns,
        datetime.now(UTC),
        None,
        None,
        1,
        actual,
        actual,
        0,
        0,
        0,
        None,
        None,
        0,
        None,
        None,
    )


def _context() -> SafetyContext:
    return SafetyContext(
        SessionState.READONLY_READY,
        AppMode.OPERATOR,
        _snapshot(),
        200,
        1_000,
        "calibration-v1",
        False,
        False,
        True,
        True,
    )


def _intent(target: tuple[int, int, int, int, int, int] | None = None) -> CommandIntent:
    return CommandIntent(
        CommandFamily.JOINT_TARGET,
        0x3F,
        JointTarget(target or (10_000, 1_570_770, 0, 0, 0, 0), 100, 0),
    )


def test_readonly_is_always_allowed_without_action_context() -> None:
    context = replace(_context(), snapshot=None, mode=AppMode.OBSERVER)
    assert SafetyGate().evaluate(CommandIntent(CommandFamily.READONLY), context).allowed


def test_gate_returns_all_relevant_denials() -> None:
    context = replace(
        _context(),
        session_state=SessionState.DISCONNECTED,
        mode=AppMode.OBSERVER,
        snapshot=None,
        calibration_hash=None,
        hardware_assembled=False,
        mock_transport=False,
        hold_active=False,
    )
    decision = SafetyGate().evaluate(replace(_intent(), continuous=True, joint_mask=0x80), context)
    assert set(decision.denials) == {
        "session_not_ready",
        "operator_mode_required",
        "snapshot_missing",
        "calibration_missing",
        "hardware_not_confirmed",
        "joint_mask_invalid",
        "hold_required",
    }


def test_stale_fault_gravity_and_target_validation_denials() -> None:
    stale = replace(_context(), now_monotonic_ns=10_000)
    assert "snapshot_stale" in SafetyGate().evaluate(_intent(), stale).denials
    fault = replace(_context(), snapshot=replace(_snapshot(), run_state_raw=5))
    assert "run_state_unsafe" in SafetyGate().evaluate(_intent(), fault).denials
    release = CommandIntent(CommandFamily.GRAVITY_RELEASE, joint_mask=0x06)
    decision = SafetyGate().evaluate(release, _context())
    assert "gravity_support_required" in decision.denials
    assert decision.required_confirmation_text is not None
    missing = SafetyGate().evaluate(CommandIntent(CommandFamily.JOINT_TARGET), _context())
    assert "target_missing" in missing.denials


@given(delta=st.integers(min_value=-175_000, max_value=175_000))
def test_joint_target_exact_step_boundary_is_allowed(delta: int) -> None:
    actual = _snapshot().actual_joint_urad
    target = (*actual[:3], actual[3] + delta, *actual[4:])
    assert SafetyGate().evaluate(_intent(target), _context()).allowed


def test_joint_limit_step_and_duration_are_rejected() -> None:
    gate = SafetyGate()
    decision = gate.evaluate(_intent((-1, 1_570_770, 0, 0, 0, 0)), _context())
    assert "joint_limit" in decision.denials
    decision = gate.evaluate(_intent((200_000, 1_570_770, 0, 0, 0, 0)), _context())
    assert "step_limit" in decision.denials
    target = _intent().target
    assert target is not None
    bad_duration = replace(_intent(), target=replace(target, duration_ms=0))
    assert "duration_invalid" in gate.evaluate(bad_duration, _context()).denials


class RecordingExecutor:
    def __init__(self) -> None:
        self.intents: list[CommandIntent] = []

    def execute(self, intent: CommandIntent) -> str:
        self.intents.append(intent)
        return "accepted"


def test_command_service_binds_preview_arm_generation_and_calibration() -> None:
    executor = RecordingExecutor()
    service = CommandService(SafetyGate(), executor)
    context = _context()
    preview = service.preview(_intent(), context)
    arm = service.arm(preview, context)
    assert service.execute(preview, arm, context) == "accepted"
    assert executor.intents == [_intent()]
    with pytest.raises(PermissionError):
        service.execute(preview, arm, context)


@pytest.mark.parametrize(
    "changed",
    [
        lambda context: replace(context, now_monotonic_ns=6_000_000_000),
        lambda context: replace(context, calibration_hash="changed"),
        lambda context: replace(context, snapshot=replace(_snapshot(), generation=2)),
        lambda context: replace(context, mode=AppMode.OBSERVER),
    ],
)
def test_command_service_rejects_stale_arm_context(
    changed: Callable[[SafetyContext], SafetyContext],
) -> None:
    service = CommandService(SafetyGate(), RecordingExecutor())
    context = _context()
    preview = service.preview(_intent(), context)
    arm = service.arm(preview, context)
    with pytest.raises(PermissionError):
        service.execute(preview, arm, changed(context))


def test_denied_preview_cannot_arm() -> None:
    service = CommandService(SafetyGate(), RecordingExecutor())
    context = replace(_context(), mode=AppMode.OBSERVER)
    with pytest.raises(PermissionError):
        service.arm(service.preview(_intent(), context), context)


def test_command_service_requires_executor_contract() -> None:
    service = CommandService(SafetyGate(), object())
    context = _context()
    preview = service.preview(_intent(), context)
    arm = service.arm(preview, context)
    with pytest.raises(TypeError, match="executor"):
        service.execute(preview, arm, context)
