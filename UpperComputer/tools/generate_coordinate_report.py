"""Generate the reproducible model-coordinate mapping report."""

import json
import math
from pathlib import Path

from zeroarm_desktop.model3d.fk import UrdfForwardKinematics
from zeroarm_desktop.model3d.joint_mapping import JointModelMapping


def main() -> int:
    root = Path(__file__).parents[1]
    urdf = (
        root
        / "resources/robot_model/URDF_XG_Robot_Arm_Urdf_V1_1/urdf"
        / "URDF_XG_Robot_Arm_Urdf_V1_1.urdf"
    )
    mapping = JointModelMapping()
    fk = UrdfForwardKinematics(urdf, mapping)
    model_zero_robot = (
        0,
        round(math.pi * 1_000_000),
        round(-math.pi / 2 * 1_000_000),
        0,
        round(math.pi / 2 * 1_000_000),
        0,
    )
    report = {
        "schema_version": 1,
        "hardware_mapping_verified": False,
        "warning": (
            "Model-coordinate evidence is complete; installed encoder zero/sign remains unverified."
        ),
        "mapping": [
            {
                "robot_index": entry.robot_index,
                "model_joint": entry.model_joint,
                "sign": entry.sign,
                "offset_rad": entry.offset_rad,
                "wrap": entry.wrap,
                "robot_range_urad": [entry.robot_min_urad, entry.robot_max_urad],
                "model_range_rad": [entry.model_min_rad, entry.model_max_rad],
                "hardware_verified": entry.hardware_verified,
            }
            for entry in mapping.entries
        ],
        "golden_model_zero": {
            "robot_urad": model_zero_robot,
            "end_effector_position_m": fk.forward(model_zero_robot).position_m,
            "reference": "URDF + MuJoCo + modified-DH audit 2026-07-29",
        },
    }
    output = root / "resources/robot_model/coordinate_report.json"
    output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
