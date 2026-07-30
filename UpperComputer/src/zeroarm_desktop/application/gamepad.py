"""Mock-safe gamepad mapping with deadzone and hold semantics."""

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class GamepadAxisMap:
    source_axis: int
    joint_index: int
    scale: float
    invert: bool = False


@dataclass(frozen=True, slots=True)
class GamepadProfile:
    name: str
    deadzone: float
    maps: tuple[GamepadAxisMap, ...]


@dataclass(frozen=True, slots=True)
class GamepadSample:
    axes: tuple[float, ...]
    buttons: tuple[bool, ...]
    hold_active: bool


def apply_deadzone(value: float, deadzone: float) -> float:
    if not -1.0 <= value <= 1.0:
        raise ValueError("axis value must be within [-1, 1]")
    if deadzone < 0 or deadzone >= 1:
        raise ValueError("deadzone must be within [0, 1)")
    if abs(value) < deadzone:
        return 0.0
    sign = 1.0 if value > 0 else -1.0
    return sign * (abs(value) - deadzone) / (1.0 - deadzone)


def map_sample_to_joint_steps(
    sample: GamepadSample,
    profile: GamepadProfile,
    *,
    max_step_urad: int = 17_453,
) -> tuple[int, ...]:
    if not sample.hold_active:
        return (0, 0, 0, 0, 0, 0)
    steps = [0, 0, 0, 0, 0, 0]
    for mapping in profile.maps:
        raw = sample.axes[mapping.source_axis]
        value = apply_deadzone(raw, profile.deadzone)
        if mapping.invert:
            value = -value
        steps[mapping.joint_index] = round(value * mapping.scale * max_step_urad)
    return tuple(steps)


DEFAULT_GAMEPAD_PROFILE = GamepadProfile(
    "mock-xbox-like",
    0.12,
    (
        GamepadAxisMap(0, 0, 1.0),
        GamepadAxisMap(1, 1, 1.0, invert=True),
        GamepadAxisMap(2, 2, 0.8),
        GamepadAxisMap(3, 3, 0.8),
    ),
)
