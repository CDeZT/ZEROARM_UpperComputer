"""HardwareProfile, interlock policy, path validation, and readiness.

Single source of truth for the current partial hardware contract
(`zeroarm_g474_v1_partial`, MCU Config/joint_config.c and build_config.h
at zero_arm_mcu main @ 48c11d8). Pages and action sources must not spread
these thresholds.
"""

from collections.abc import Sequence
from dataclasses import dataclass

from zeroarm_desktop.domain.models import JointVector, RobotSnapshot
from zeroarm_desktop.protocol.v1_codec import V1FaultFlag, V1RunState

URAD_PER_DEGREE = 17_453
"""Rounded urad per degree (MCU JOINT_URAD_PER_DEGREE); precision ~0.01 deg."""


def _deg(value: int) -> int:
    return value * URAD_PER_DEGREE


@dataclass(frozen=True, slots=True)
class JointCapability:
    """Public contract for one robot axis."""

    index: int
    name: str
    available: bool
    continuous: bool
    min_urad: int
    max_urad: int
    limit_switch_installed: bool
    motor_id: int
    max_velocity_urad_s: int = _deg(30)

    def is_within_range(self, value_urad: int) -> bool:
        if self.continuous:
            return True
        return self.min_urad <= value_urad <= self.max_urad


@dataclass(frozen=True, slots=True)
class HardwareProfile:
    """Frozen partial-hardware contract for the current board."""

    profile_id: str
    capabilities: tuple[JointCapability, ...]
    startup_limit_mask: int
    home_mask: int
    feedback_mask: int

    def capability(self, index: int) -> JointCapability:
        return self.capabilities[index]

    def target_violations(self, target_urad: JointVector) -> tuple[str, ...]:
        """Reject out-of-range values and any non-zero motion on unavailable axes."""
        violations: list[str] = []
        for capability, value in zip(self.capabilities, target_urad, strict=True):
            if not capability.available:
                if value != 0:
                    violations.append("unavailable_axis")
                continue
            if not capability.is_within_range(value):
                violations.append("joint_limit")
        return tuple(violations)

    @classmethod
    def default(cls) -> "HardwareProfile":
        return cls(
            profile_id="zeroarm_g474_v1_partial",
            capabilities=(
                JointCapability(0, "J1", True, True, 0, _deg(360), True, 1),
                JointCapability(1, "J2", False, False, _deg(90), _deg(180), False, 2),
                JointCapability(2, "J3", True, False, 0, _deg(135), True, 3),
                JointCapability(3, "J4", True, False, _deg(-90), _deg(90), True, 4),
                JointCapability(4, "J5", True, False, _deg(-35), _deg(135), True, 5),
                JointCapability(5, "J6", False, False, 0, _deg(360), False, 6),
            ),
            startup_limit_mask=0x1D,
            home_mask=0x1D,
            feedback_mask=0x1F,
        )


@dataclass(frozen=True, slots=True)
class InterlockPolicy:
    """J3/J4/J5 combination interlocks mirrored from MCU joint_config.c.

    The MCU guarantees only endpoint (and transition) checks; path sampling is
    the host's responsibility (see PathValidator).
    """

    j3_min_for_j4_motion_urad: int = _deg(15)
    j3_min_for_j5_midrange_urad: int = _deg(15)
    j5_max_without_j3_midrange_urad: int = _deg(45)
    j3_min_for_j5_extended_urad: int = _deg(45)
    j5_max_without_j3_extended_urad: int = _deg(60)
    j4_zero_urad: int = 0

    @property
    def defaults_valid(self) -> bool:
        return (
            self.j3_min_for_j4_motion_urad
            <= self.j3_min_for_j5_midrange_urad
            <= self.j3_min_for_j5_extended_urad
        )

    def target_violations(self, target_urad: JointVector) -> tuple[str, ...]:
        """Mirror joint_config_targets_satisfy_interlocks."""
        violations: list[str] = []
        if target_urad[3] != self.j4_zero_urad and target_urad[2] <= self.j3_min_for_j4_motion_urad:
            violations.append("j4_requires_j3_clear")
        if (
            target_urad[4] > self.j5_max_without_j3_midrange_urad
            and target_urad[2] <= self.j3_min_for_j5_midrange_urad
        ):
            violations.append("j5_midrange_requires_j3")
        if (
            target_urad[4] > self.j5_max_without_j3_extended_urad
            and target_urad[2] <= self.j3_min_for_j5_extended_urad
        ):
            violations.append("j5_extended_requires_j3")
        return tuple(violations)

    def transition_violations(
        self, actual_urad: JointVector, target_urad: JointVector
    ) -> tuple[str, ...]:
        """Mirror joint_config_transition_satisfies_interlocks (endpoint level)."""
        violations = list(self.target_violations(target_urad))
        if target_urad[3] != actual_urad[3] and actual_urad[2] <= self.j3_min_for_j4_motion_urad:
            violations.append("j4_move_requires_j3_already_clear")
        if (
            target_urad[4] > self.j5_max_without_j3_midrange_urad
            and actual_urad[2] <= self.j3_min_for_j5_midrange_urad
        ):
            violations.append("j5_midrange_requires_j3_already_clear")
        if (
            target_urad[4] > self.j5_max_without_j3_extended_urad
            and actual_urad[2] <= self.j3_min_for_j5_extended_urad
        ):
            violations.append("j5_extended_requires_j3_already_clear")
        if target_urad[2] <= self.j3_min_for_j4_motion_urad and actual_urad[3] != self.j4_zero_urad:
            violations.append("lower_j3_requires_j4_centered")
        if (
            target_urad[2] <= self.j3_min_for_j5_midrange_urad
            and actual_urad[4] > self.j5_max_without_j3_midrange_urad
        ):
            violations.append("lower_j3_requires_j5_midrange")
        if (
            target_urad[2] <= self.j3_min_for_j5_extended_urad
            and actual_urad[4] > self.j5_max_without_j3_extended_urad
        ):
            violations.append("lower_j3_requires_j5_extended")
        return tuple(violations)


def _fmt_urad(value: int) -> str:
    return f"{value / URAD_PER_DEGREE:.1f}°"


def _interlock_joint_index(code: str) -> int | None:
    if code.startswith("j4") or code == "lower_j3_requires_j4_centered":
        return 3
    if code.startswith("j5") or code.startswith("lower_j3_requires_j5"):
        return 4
    if code.startswith("lower_j3"):
        return 2
    return None


def _interlock_detail(
    code: str,
    actual_urad: JointVector,
    target_urad: JointVector,
) -> str:
    j3 = target_urad[2]
    j4 = target_urad[3]
    j5 = target_urad[4]
    if code in {"j4_requires_j3_clear", "j4_move_requires_j3_already_clear"}:
        return (
            f"J4={_fmt_urad(j4)} 需要 J3>15° (J3={_fmt_urad(actual_urad[2])})"
            if code.endswith("already_clear")
            else f"J4={_fmt_urad(j4)} 需要 J3>15° (J3={_fmt_urad(j3)})"
        )
    if code in {"j5_midrange_requires_j3", "j5_midrange_requires_j3_already_clear"}:
        j3_value = actual_urad[2] if code.endswith("already_clear") else j3
        return f"J5={_fmt_urad(j5)} 需要 J3>15° (J3={_fmt_urad(j3_value)})"
    if code in {"j5_extended_requires_j3", "j5_extended_requires_j3_already_clear"}:
        j3_value = actual_urad[2] if code.endswith("already_clear") else j3
        return f"J5={_fmt_urad(j5)} 需要 J3>45° (J3={_fmt_urad(j3_value)})"
    if code == "lower_j3_requires_j4_centered":
        return f"降 J3 到 {_fmt_urad(j3)} 前 J4 必须回 0° (J4={_fmt_urad(actual_urad[3])})"
    if code == "lower_j3_requires_j5_midrange":
        return f"降 J3 到 {_fmt_urad(j3)} 前 J5 必须 ≤45° (J5={_fmt_urad(actual_urad[4])})"
    if code == "lower_j3_requires_j5_extended":
        return f"降 J3 到 {_fmt_urad(j3)} 前 J5 必须 ≤60° (J5={_fmt_urad(actual_urad[4])})"
    return ""


@dataclass(frozen=True, slots=True)
class PathIssue:
    point_index: int
    code: str
    joint_index: int | None = None
    detail: str | None = None


@dataclass(frozen=True, slots=True)
class PathValidation:
    valid: bool
    issues: tuple[PathIssue, ...]

    @property
    def errors(self) -> tuple[tuple[int, str], ...]:
        return tuple((issue.point_index, issue.code) for issue in self.issues)

    def reasons(self) -> tuple[str, ...]:
        return tuple(issue.code for issue in self.issues)


class PathValidator:
    """Pointwise validation of sampled joint paths.

    R9 will add interpolation and velocity constraints; this base already
    enforces profile range, unavailable axes, and the interlock transition
    rule on every adjacent pair so a dangerous midpoint is rejected even when
    the final point is legal.
    """

    def __init__(
        self,
        profile: HardwareProfile | None = None,
        policy: InterlockPolicy | None = None,
    ) -> None:
        self.profile = profile or HardwareProfile.default()
        self.policy = policy or InterlockPolicy()
        if not self.policy.defaults_valid:
            raise ValueError("interlock thresholds must be ascending")

    def validate_path(self, points: Sequence[JointVector]) -> PathValidation:
        if not points:
            return PathValidation(True, ())
        issues: list[PathIssue] = []
        for index, point in enumerate(points):
            if len(point) != 6:
                issues.append(PathIssue(index, "point_must_have_six_axes"))
                continue
            issues.extend(self._point_issues(index, point))
            if index > 0:
                previous = points[index - 1]
                for code in self.policy.transition_violations(previous, point):
                    issues.append(
                        PathIssue(
                            index,
                            code,
                            _interlock_joint_index(code),
                            _interlock_detail(code, previous, point),
                        )
                    )
        return PathValidation(not issues, tuple(issues))

    def _point_issues(self, index: int, point: JointVector) -> list[PathIssue]:
        issues: list[PathIssue] = []
        for axis, (capability, value) in enumerate(
            zip(self.profile.capabilities, point, strict=True)
        ):
            if not capability.available:
                if value != 0:
                    issues.append(
                        PathIssue(
                            index,
                            "unavailable_axis",
                            axis,
                            f"J{axis + 1} 不可用但目标非零 ({_fmt_urad(value)})",
                        )
                    )
            elif not capability.is_within_range(value):
                issues.append(
                    PathIssue(
                        index,
                        "joint_limit",
                        axis,
                        f"J{axis + 1}={_fmt_urad(value)}, "
                        f"范围 [{_fmt_urad(capability.min_urad)}, "
                        f"{_fmt_urad(capability.max_urad)}]",
                    )
                )
        for code in self.policy.target_violations(point):
            issues.append(
                PathIssue(
                    index,
                    code,
                    _interlock_joint_index(code),
                    _interlock_detail(code, point, point),
                )
            )
        return issues


@dataclass(frozen=True, slots=True)
class ReadinessReport:
    run_state_known: bool
    run_state_name: str | None
    reset_required: bool
    motion_authorized: bool
    homed_complete: bool
    homed_mask: int | None
    fault_known: tuple[V1FaultFlag, ...]
    fault_unknown_bits: int
    fault_flags_raw: int


def evaluate_readiness(
    snapshot: RobotSnapshot,
    profile: HardwareProfile | None = None,
) -> ReadinessReport:
    """Derive motion authorization and homing readiness from a V1 snapshot."""
    profile = profile or HardwareProfile.default()
    run_state: V1RunState | None = None
    run_state_name: str | None = None
    run_state_known = False
    try:
        run_state = V1RunState(snapshot.run_state_raw)
        run_state_name = run_state.name
        run_state_known = True
    except ValueError:
        pass
    fault_known = tuple(flag for flag in V1FaultFlag if snapshot.fault_flags_raw & flag.value)
    fault_unknown_bits = snapshot.fault_flags_raw & ~0x0FFF
    reset_required = (
        snapshot.fault_flags_raw & (V1FaultFlag.STARTUP | V1FaultFlag.HOMING | V1FaultFlag.ESTOP)
    ) != 0
    motion_authorized = run_state is V1RunState.READY and snapshot.fault_flags_raw == 0
    homed_mask = snapshot.homed_mask
    homed_complete = (
        homed_mask is not None and (homed_mask & profile.home_mask) == profile.home_mask
    )
    return ReadinessReport(
        run_state_known=run_state_known,
        run_state_name=run_state_name,
        reset_required=reset_required,
        motion_authorized=motion_authorized,
        homed_complete=homed_complete,
        homed_mask=homed_mask,
        fault_known=fault_known,
        fault_unknown_bits=fault_unknown_bits,
        fault_flags_raw=snapshot.fault_flags_raw,
    )
