"""Pure deterministic command safety decisions for all future action sources."""

import hashlib
import json
from dataclasses import dataclass
from enum import Enum
from uuid import UUID, uuid4

from zeroarm_desktop.application.device_session import SessionState
from zeroarm_desktop.domain.hardware_profile import (
    HardwareProfile,
    InterlockPolicy,
    PathValidator,
)
from zeroarm_desktop.domain.models import JointTarget, RobotSnapshot


class AppMode(Enum):
    OBSERVER = "observer"
    DEBUG = "debug"
    OPERATOR = "operator"


class CommandFamily(Enum):
    READONLY = "readonly"
    STOP = "stop"
    JOINT_TARGET = "joint_target"
    ENABLE = "enable"
    HOME = "home"
    FAULT_CLEAR = "fault_clear"
    GRIPPER = "gripper"
    GRAVITY_RELEASE = "gravity_release"
    TRAJECTORY = "trajectory"


@dataclass(frozen=True, slots=True)
class CommandIntent:
    family: CommandFamily
    joint_mask: int = 0
    target: JointTarget | None = None
    continuous: bool = False


@dataclass(frozen=True, slots=True)
class SafetyContext:
    session_state: SessionState
    mode: AppMode
    snapshot: RobotSnapshot | None
    now_monotonic_ns: int
    snapshot_max_age_ns: int
    calibration_hash: str | None
    hardware_assembled: bool
    support_confirmed: bool
    hold_active: bool
    mock_transport: bool
    max_step_urad: int = 175_000


@dataclass(frozen=True, slots=True)
class SafetyDecision:
    allowed: bool
    denials: tuple[str, ...]
    warnings: tuple[str, ...]
    normalized_intent: CommandIntent | None
    required_confirmation_text: str | None


@dataclass(frozen=True, slots=True)
class CommandPreview:
    intent: CommandIntent
    preview_hash: str
    decision: SafetyDecision
    snapshot_generation: int
    calibration_hash: str


@dataclass(frozen=True, slots=True)
class ArmContext:
    token: UUID
    command_family: CommandFamily
    allowed_joint_mask: int
    preview_hash: str
    created_monotonic_ns: int
    expires_monotonic_ns: int
    calibration_hash: str
    snapshot_generation: int


class SafetyGate:
    """Evaluate an action intent without I/O, UI, or mutable global state."""

    def __init__(
        self,
        profile: HardwareProfile | None = None,
        policy: InterlockPolicy | None = None,
        path_validator: PathValidator | None = None,
    ) -> None:
        self.profile = profile or HardwareProfile.default()
        self.policy = policy or InterlockPolicy()
        self.path_validator = path_validator or PathValidator(self.profile, self.policy)

    def evaluate(self, intent: CommandIntent, context: SafetyContext) -> SafetyDecision:
        if intent.family is CommandFamily.READONLY:
            return SafetyDecision(True, (), (), intent, None)

        denials: list[str] = []
        warnings: list[str] = ["软件检查不能替代机械急停和装机确认"]
        snapshot = context.snapshot
        if context.session_state is not SessionState.READONLY_READY:
            denials.append("session_not_ready")
        if context.mode is not AppMode.OPERATOR:
            denials.append("operator_mode_required")
        if snapshot is None:
            denials.append("snapshot_missing")
        elif (
            context.now_monotonic_ns - snapshot.received_monotonic_ns > context.snapshot_max_age_ns
        ):
            denials.append("snapshot_stale")
        elif intent.family is not CommandFamily.FAULT_CLEAR and snapshot.run_state_raw in {0, 3, 5}:
            denials.append("run_state_unsafe")
        if intent.family is CommandFamily.FAULT_CLEAR:
            return SafetyDecision(not denials, tuple(denials), tuple(warnings), intent, None)
        if context.calibration_hash is None:
            denials.append("calibration_missing")
        if not context.mock_transport and not context.hardware_assembled:
            denials.append("hardware_not_confirmed")
        if not 0 <= intent.joint_mask <= 0x3F:
            denials.append("joint_mask_invalid")
        if intent.continuous and not context.hold_active:
            denials.append("hold_required")
        if intent.family is CommandFamily.GRAVITY_RELEASE and not context.support_confirmed:
            denials.append("gravity_support_required")
        if intent.family is CommandFamily.HOME:
            if snapshot is not None and snapshot.run_state_raw != 1:
                denials.append("home_requires_ready")
            if intent.joint_mask & ~self.profile.home_mask:
                denials.append("home_mask_outside_profile")

        target = intent.target
        if intent.family is CommandFamily.JOINT_TARGET:
            if target is None:
                denials.append("target_missing")
            elif snapshot is not None:
                denials.extend(self.profile.target_violations(target.joint_urad))
                denials.extend(
                    self.policy.transition_violations(snapshot.actual_joint_urad, target.joint_urad)
                )
                if (
                    max(
                        abs(target_value - actual_value)
                        for target_value, actual_value in zip(
                            target.joint_urad, snapshot.actual_joint_urad, strict=True
                        )
                    )
                    > context.max_step_urad
                ):
                    denials.append("step_limit")
                if not 1 <= target.duration_ms <= 0xFFFF:
                    denials.append("duration_invalid")

        confirmation = None
        if intent.family in {CommandFamily.GRAVITY_RELEASE, CommandFamily.TRAJECTORY}:
            confirmation = "确认支撑、急停、工作空间和允许轴"
        return SafetyDecision(not denials, tuple(denials), tuple(warnings), intent, confirmation)


class CommandService:
    """Bind preview, Arm, snapshot, and calibration before invoking one executor."""

    def __init__(
        self, gate: SafetyGate, executor: object, *, arm_ttl_ns: int = 5_000_000_000
    ) -> None:
        self.gate = gate
        self.executor = executor
        self.arm_ttl_ns = arm_ttl_ns
        self._armed: ArmContext | None = None

    def preview(self, intent: CommandIntent, context: SafetyContext) -> CommandPreview:
        decision = self.gate.evaluate(intent, context)
        generation = context.snapshot.generation if context.snapshot is not None else -1
        calibration = context.calibration_hash or ""
        return CommandPreview(intent, preview_hash(intent), decision, generation, calibration)

    def arm(self, preview: CommandPreview, context: SafetyContext) -> ArmContext:
        if not preview.decision.allowed:
            raise PermissionError("cannot arm a denied preview")
        arm = ArmContext(
            uuid4(),
            preview.intent.family,
            preview.intent.joint_mask,
            preview.preview_hash,
            context.now_monotonic_ns,
            context.now_monotonic_ns + self.arm_ttl_ns,
            preview.calibration_hash,
            preview.snapshot_generation,
        )
        self._armed = arm
        return arm

    def disarm(self, reason: str) -> None:
        del reason
        self._armed = None

    def execute(self, preview: CommandPreview, arm: ArmContext, context: SafetyContext) -> object:
        current = self.gate.evaluate(preview.intent, context)
        generation = context.snapshot.generation if context.snapshot is not None else -1
        checks = (
            self._armed == arm,
            current.allowed,
            context.now_monotonic_ns <= arm.expires_monotonic_ns,
            preview.preview_hash == arm.preview_hash == preview_hash(preview.intent),
            generation == arm.snapshot_generation == preview.snapshot_generation,
            (context.calibration_hash or "") == arm.calibration_hash == preview.calibration_hash,
            preview.intent.family is arm.command_family,
            preview.intent.joint_mask == arm.allowed_joint_mask,
        )
        if not all(checks):
            self.disarm("execute_revalidation_failed")
            raise PermissionError("Arm context no longer matches the current command context")
        self.disarm("executed")
        execute = getattr(self.executor, "execute", None)
        if not callable(execute):
            raise TypeError("command executor must provide execute(intent)")
        return execute(preview.intent)


def preview_hash(intent: CommandIntent) -> str:
    target = intent.target
    document = {
        "family": intent.family.value,
        "joint_mask": intent.joint_mask,
        "continuous": intent.continuous,
        "target": None
        if target is None
        else {
            "joint_urad": target.joint_urad,
            "duration_ms": target.duration_ms,
            "gripper_u16": target.gripper_u16,
        },
    }
    encoded = json.dumps(document, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(encoded).hexdigest()
