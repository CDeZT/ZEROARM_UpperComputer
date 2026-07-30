"""Calibration validation, checksum, import, and single-axis diff tests."""

from dataclasses import replace

import pytest

from zeroarm_desktop.domain.calibration import (
    DEFAULT_CALIBRATION,
    calibration_diff,
    calibration_from_json,
    calibration_to_json,
    validate_calibration,
)


def test_calibration_roundtrip_checksum_and_axis_diff() -> None:
    decoded = calibration_from_json(calibration_to_json(DEFAULT_CALIBRATION))
    assert decoded == DEFAULT_CALIBRATION
    assert decoded.checksum == DEFAULT_CALIBRATION.checksum
    changed_axes = list(decoded.axes)
    changed_axes[2] = replace(changed_axes[2], mechanical_zero_urad=123)
    changed = replace(decoded, revision=2, axes=tuple(changed_axes))
    assert len(calibration_diff(decoded, changed)) == 1
    assert calibration_diff(decoded, changed)[0].startswith("J3")


def test_calibration_rejects_duplicate_ids_and_bad_limits() -> None:
    axes = list(DEFAULT_CALIBRATION.axes)
    axes[1] = replace(axes[1], motor_id=1, soft_min_urad=10, soft_max_urad=10)
    issues = validate_calibration(replace(DEFAULT_CALIBRATION, axes=tuple(axes)))
    assert "duplicate_motor_id" in issues
    assert "axis_1_limits" in issues
    with pytest.raises(ValueError):
        calibration_from_json('{"schema_version":99,"revision":1,"axes":[]}')
