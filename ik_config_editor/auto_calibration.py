"""Automatic calibration for rotation offsets and scale factors."""

import numpy as np
from scipy.spatial.transform import Rotation as R
from typing import Dict, List, Tuple


class AutoCalibration:
    """Calculate automatic rotation offsets and scale factors for IK configs."""

    @staticmethod
    def calculate_rotation_offset(
        source_orientation: np.ndarray,
        target_orientation: np.ndarray
    ) -> np.ndarray:
        """Calculate rotation offset quaternion between source and target orientations.

        The offset quaternion q_offset transforms target to source:
            q_source = q_offset * q_target

        Therefore: q_offset = q_source * q_target^{-1}

        Args:
            source_orientation: Source orientation as quaternion [w, x, y, z]
            target_orientation: Target orientation as quaternion [w, x, y, z]

        Returns:
            Rotation offset as quaternion [w, x, y, z]
        """
        # Convert to scipy Rotation objects (expects x, y, z, w format)
        source_rot = R.from_quat([
            source_orientation[1], source_orientation[2],
            source_orientation[3], source_orientation[0]
        ])
        target_rot = R.from_quat([
            target_orientation[1], target_orientation[2],
            target_orientation[3], target_orientation[0]
        ])

        # Calculate offset: q_offset = q_source * q_target^{-1}
        offset_rot = source_rot.inv() * target_rot

        # Convert back to [w, x, y, z] format
        offset_quat = offset_rot.as_quat()  # Returns [x, y, z, w]
        return np.array([offset_quat[3], offset_quat[0], offset_quat[1], offset_quat[2]])

    @staticmethod
    def calculate_all_rotation_offsets(
        source_skeleton: Dict[str, Dict[str, List[float]]],
        target_skeleton: Dict[str, Dict[str, List[float]]],
        correspondences: Dict[str, str]
    ) -> Dict[str, np.ndarray]:
        """Calculate rotation offsets for all correspondences.

        Args:
            source_skeleton: Source skeleton data
            target_skeleton: Target skeleton data
            correspondences: Mapping from source body to target body

        Returns:
            Dictionary mapping target body name to rotation offset quaternion
        """
        rotation_offsets = {}

        for source_body, target_body in correspondences.items():
            source_ori = np.array(source_skeleton[source_body]["orientation"])
            target_ori = np.array(target_skeleton[target_body]["orientation"])

            offset = AutoCalibration.calculate_rotation_offset(source_ori, target_ori)
            rotation_offsets[target_body] = offset

        return rotation_offsets

    @staticmethod
    def calculate_bone_length(
        skeleton: Dict[str, Dict[str, List[float]]],
        body1: str,
        body2: str
    ) -> float:
        """Calculate distance between two bodies (bone length).

        Args:
            skeleton: Skeleton data
            body1: First body name
            body2: Second body name

        Returns:
            Euclidean distance between the two bodies
        """
        pos1 = np.array(skeleton[body1]["position"])
        pos2 = np.array(skeleton[body2]["position"])
        return np.linalg.norm(pos2 - pos1)

    @staticmethod
    def calculate_scale_factor(
        source_skeleton: Dict[str, Dict[str, List[float]]],
        target_skeleton: Dict[str, Dict[str, List[float]]],
        source_body1: str,
        source_body2: str,
        target_body1: str,
        target_body2: str
    ) -> float:
        """Calculate scale factor between two bone pairs.

        Scale = source_length / target_length

        Args:
            source_skeleton: Source skeleton data
            target_skeleton: Target skeleton data
            source_body1: First source body
            source_body2: Second source body
            target_body1: First target body
            target_body2: Second target body

        Returns:
            Scale factor
        """
        source_length = AutoCalibration.calculate_bone_length(
            source_skeleton, source_body1, source_body2
        )
        target_length = AutoCalibration.calculate_bone_length(
            target_skeleton, target_body1, target_body2
        )

        if target_length == 0:
            return 1.0

        return source_length / target_length

    @staticmethod
    def calculate_height_scale(
        source_skeleton: Dict[str, Dict[str, List[float]]],
        target_skeleton: Dict[str, Dict[str, List[float]]],
        pelvis_name_source: str = "pelvis",
        pelvis_name_target: str = "pelvis"
    ) -> float:
        """Calculate uniform scale factor based on pelvis-to-ground height.

        Measures the height from the pelvis to the lowest foot position
        (ground level) and returns the ratio.

        Args:
            source_skeleton: Source skeleton data
            target_skeleton: Target skeleton data
            pelvis_name_source: Name of pelvis body in source skeleton
            pelvis_name_target: Name of pelvis body in target skeleton

        Returns:
            Scale factor (target_height / source_height)
            - If target is taller, returns > 1.0 (enlarge source motion)
            - If target is shorter, returns < 1.0 (shrink source motion)
        """
        def get_height(skeleton, pelvis_name):
            """Get height from pelvis to lowest foot position."""
            # Get pelvis Z position
            if pelvis_name not in skeleton:
                raise ValueError(f"Pelvis body '{pelvis_name}' not found in skeleton")

            pelvis_z = skeleton[pelvis_name]["position"][2]

            # Find all foot/toe/ankle bodies (lowest points)
            foot_keywords = ["foot", "toe", "ankle"]
            foot_positions = []

            for body_name, data in skeleton.items():
                body_lower = body_name.lower()
                if any(keyword in body_lower for keyword in foot_keywords):
                    foot_positions.append(data["position"][2])

            if not foot_positions:
                # If no foot bodies found, use ground as Z=0
                min_foot_z = 0.0
            else:
                min_foot_z = min(foot_positions)

            height = pelvis_z - min_foot_z
            return height if height > 0 else 1.0  # Avoid zero/negative heights

        source_height = get_height(source_skeleton, pelvis_name_source)
        target_height = get_height(target_skeleton, pelvis_name_target)

        if source_height == 0:
            return 1.0

        # Scale = target/source to scale source motion to match target size
        # If target is bigger, scale > 1.0 (enlarge motion)
        # If target is smaller, scale < 1.0 (shrink motion)
        return target_height / source_height

    @staticmethod
    def calculate_limb_scales(
        source_skeleton: Dict[str, Dict[str, List[float]]],
        target_skeleton: Dict[str, Dict[str, List[float]]],
        correspondences: Dict[str, str]
    ) -> Dict[str, float]:
        """Calculate scale factors for limbs based on correspondences.

        This attempts to find common kinematic chains and calculate scales.

        Args:
            source_skeleton: Source skeleton data
            target_skeleton: Target skeleton data
            correspondences: Body correspondences

        Returns:
            Dictionary mapping source body names to scale factors
        """
        scales = {}

        # Define common kinematic chains to measure
        # Format: (parent, child) pairs
        common_chains = [
            # Legs
            ("pelvis", "left_hip"),
            ("left_hip", "left_knee"),
            ("left_knee", "left_foot"),
            ("pelvis", "right_hip"),
            ("right_hip", "right_knee"),
            ("right_knee", "right_foot"),
            # Arms
            ("spine3", "left_shoulder"),
            ("left_shoulder", "left_elbow"),
            ("left_elbow", "left_wrist"),
            ("spine3", "right_shoulder"),
            ("right_shoulder", "right_elbow"),
            ("right_elbow", "right_wrist"),
            # Torso
            ("pelvis", "spine3"),
        ]

        for source_parent, source_child in common_chains:
            # Check if both bodies are in correspondences
            if source_parent in correspondences and source_child in correspondences:
                target_parent = correspondences[source_parent]
                target_child = correspondences[source_child]

                try:
                    scale = AutoCalibration.calculate_scale_factor(
                        source_skeleton, target_skeleton,
                        source_parent, source_child,
                        target_parent, target_child
                    )

                    # Assign scale to the child body (the one being scaled from parent)
                    scales[source_child] = scale

                except (KeyError, ZeroDivisionError):
                    # Skip if bodies don't exist or have zero distance
                    continue

        # Fill in missing scales with 1.0
        for source_body in correspondences.keys():
            if source_body not in scales:
                scales[source_body] = 1.0

        return scales

    @staticmethod
    def suggest_position_weights(
        correspondences: Dict[str, str]
    ) -> Dict[str, float]:
        """Suggest position weights based on body names.

        Args:
            correspondences: Body correspondences

        Returns:
            Dictionary mapping target body names to suggested position weights
        """
        weights = {}

        # High weight (100) for end effectors and pelvis (grounding)
        high_weight_keywords = ['foot', 'toe', 'ankle', 'pelvis', 'hand']
        # Medium weight (10-50) for intermediate joints
        medium_weight_keywords = ['knee', 'elbow', 'wrist', 'hip', 'shoulder']
        # Low weight (0) for most rotation-only joints
        # Default is 0

        for source_body, target_body in correspondences.items():
            target_lower = target_body.lower()
            source_lower = source_body.lower()

            # Check for high weight keywords
            if any(kw in target_lower or kw in source_lower for kw in high_weight_keywords):
                weights[target_body] = 100.0
            # Check for medium weight keywords
            elif any(kw in target_lower or kw in source_lower for kw in medium_weight_keywords):
                weights[target_body] = 10.0
            # Default to low weight
            else:
                weights[target_body] = 0.0

        return weights

    @staticmethod
    def suggest_rotation_weights(
        correspondences: Dict[str, str]
    ) -> Dict[str, float]:
        """Suggest rotation weights based on body names.

        Args:
            correspondences: Body correspondences

        Returns:
            Dictionary mapping target body names to suggested rotation weights
        """
        weights = {}

        # Higher rotation weight for spine, shoulders (important orientation)
        high_rot_keywords = ['spine', 'torso', 'shoulder']
        # Very high for end effectors
        very_high_rot_keywords = ['foot', 'toe', 'hand', 'wrist']
        # Default is 10

        for source_body, target_body in correspondences.items():
            target_lower = target_body.lower()
            source_lower = source_body.lower()

            if any(kw in target_lower or kw in source_lower for kw in very_high_rot_keywords):
                weights[target_body] = 50.0
            elif any(kw in target_lower or kw in source_lower for kw in high_rot_keywords):
                weights[target_body] = 100.0
            else:
                weights[target_body] = 10.0

        return weights
