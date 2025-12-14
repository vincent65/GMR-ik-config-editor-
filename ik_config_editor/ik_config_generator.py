"""IK Configuration Generator for creating GMR-compatible IK config JSON files."""

import json
import numpy as np
from typing import Dict, List, Any, Optional

from ik_config_editor.auto_calibration import AutoCalibration


class IKConfigGenerator:
    """Generate IK configuration files from user-defined correspondences."""

    def __init__(
        self,
        source_skeleton: Dict[str, Dict[str, List[float]]],
        target_skeleton: Dict[str, Dict[str, List[float]]],
        correspondences: Dict[str, str],
        robot_root_name: str = "pelvis",
        human_root_name: str = "pelvis",
        human_height_assumption: float = 1.8,
        ground_height: float = 0.0,
        default_pos_weight: float = 0.0,
        default_rot_weight: float = 10.0,
        auto_calculate_offsets: bool = False,
        auto_calculate_scales: bool = False,
        auto_suggest_weights: bool = False,
        use_height_scaling: bool = True,
        use_limb_scaling: bool = True,
    ):
        """Initialize the IK config generator.

        Args:
            source_skeleton: Source skeleton data (human/source robot)
            target_skeleton: Target skeleton data (target robot)
            correspondences: Mapping from source body name to target body name
            robot_root_name: Name of the robot root body
            human_root_name: Name of the human/source root body
            human_height_assumption: Assumed human height in meters
            ground_height: Ground height offset
            default_pos_weight: Default position weight for IK
            default_rot_weight: Default rotation weight for IK
            auto_calculate_offsets: Automatically calculate rotation offsets
            auto_calculate_scales: Automatically calculate scale factors (enables both height and limb)
            auto_suggest_weights: Automatically suggest IK weights
            use_height_scaling: Use height-based uniform scaling (only if auto_calculate_scales=True)
            use_limb_scaling: Use per-limb scaling adjustments (only if auto_calculate_scales=True)
        """
        self.source_skeleton = source_skeleton
        self.target_skeleton = target_skeleton
        self.correspondences = correspondences
        self.robot_root_name = robot_root_name
        self.human_root_name = human_root_name
        self.human_height_assumption = human_height_assumption
        self.ground_height = ground_height
        self.default_pos_weight = default_pos_weight
        self.default_rot_weight = default_rot_weight
        self.auto_calculate_offsets = auto_calculate_offsets
        self.auto_calculate_scales = auto_calculate_scales
        self.auto_suggest_weights = auto_suggest_weights
        self.use_height_scaling = use_height_scaling
        self.use_limb_scaling = use_limb_scaling

        # Calculate automatic values if requested
        self.rotation_offsets = None
        self.scale_factors = None
        self.height_scale = None
        self.position_weights = None
        self.rotation_weights = None

        if self.auto_calculate_offsets:
            self.rotation_offsets = AutoCalibration.calculate_all_rotation_offsets(
                source_skeleton, target_skeleton, correspondences
            )

        if self.auto_calculate_scales:
            # Calculate height-based scaling
            if self.use_height_scaling:
                self.height_scale = AutoCalibration.calculate_height_scale(
                    source_skeleton, target_skeleton,
                    human_root_name, robot_root_name
                )

            # Calculate per-limb scaling
            if self.use_limb_scaling:
                self.scale_factors = AutoCalibration.calculate_limb_scales(
                    source_skeleton, target_skeleton, correspondences
                )

        if self.auto_suggest_weights:
            self.position_weights = AutoCalibration.suggest_position_weights(correspondences)
            self.rotation_weights = AutoCalibration.suggest_rotation_weights(correspondences)

    def generate(self) -> Dict[str, Any]:
        """Generate the IK configuration dictionary.

        Returns:
            IK configuration dictionary ready to be saved as JSON
        """
        config = {
            "robot_root_name": self.robot_root_name,
            "human_root_name": self.human_root_name,
            "ground_height": self.ground_height,
            "human_height_assumption": self.human_height_assumption,
            "use_ik_match_table1": True,
            "use_ik_match_table2": True,
            "human_scale_table": {},
            "ik_match_table1": {},
            "ik_match_table2": {},
        }

        # Build human_scale_table
        for source_name in self.correspondences.keys():
            # Start with base scale
            scale = 1.0

            # Apply height-based uniform scaling
            if self.height_scale is not None:
                scale *= self.height_scale

            # Apply per-limb scaling adjustments
            if self.scale_factors and source_name in self.scale_factors:
                scale *= self.scale_factors[source_name]

            config["human_scale_table"][source_name] = float(scale)

        # Build ik_match_table1 and ik_match_table2
        for source_name, target_name in self.correspondences.items():
            # Determine weights
            if self.position_weights and target_name in self.position_weights:
                pos_weight = float(self.position_weights[target_name])
            else:
                pos_weight = self.default_pos_weight

            if self.rotation_weights and target_name in self.rotation_weights:
                rot_weight = float(self.rotation_weights[target_name])
            else:
                rot_weight = self.default_rot_weight

            # Determine rotation offset
            if self.rotation_offsets and target_name in self.rotation_offsets:
                rot_offset = self.rotation_offsets[target_name].tolist()
            else:
                rot_offset = [1.0, 0.0, 0.0, 0.0]  # Identity quaternion

            # Create table entry for table1
            table_entry1 = [
                source_name,                    # Source body name
                pos_weight,                     # Position weight
                rot_weight,                     # Rotation weight
                [0.0, 0.0, 0.0],               # Position offset (zero for now)
                rot_offset,                     # Rotation offset
            ]

            # Create table entry for table2 (can differ from table1 in weights)
            # For table2, typically use lower rotation weights
            table_entry2 = [
                source_name,
                pos_weight,
                rot_weight * 0.5,  # Half rotation weight for table2
                [0.0, 0.0, 0.0],
                rot_offset,
            ]

            config["ik_match_table1"][target_name] = table_entry1
            config["ik_match_table2"][target_name] = table_entry2

        return config

    def save(self, output_path: str, indent: int = 4):
        """Generate and save the IK configuration to a JSON file.

        Args:
            output_path: Path where to save the JSON file
            indent: JSON indentation level
        """
        config = self.generate()

        with open(output_path, 'w') as f:
            json.dump(config, f, indent=indent)

        print(f"IK configuration saved to: {output_path}")
        print(f"  - {len(self.correspondences)} body correspondences")
        print(f"  - Robot root: {self.robot_root_name}")
        print(f"  - Human root: {self.human_root_name}")
