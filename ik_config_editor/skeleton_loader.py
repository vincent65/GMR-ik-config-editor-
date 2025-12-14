"""Skeleton loader module for loading skeleton data from various sources."""

import json
from typing import Dict, Tuple, List
import numpy as np


class SkeletonLoader:
    """Load skeleton data from various sources into a unified format.

    Unified format: {body_name: {"position": [x,y,z], "orientation": [w,x,y,z]}}
    """

    @staticmethod
    def from_json(path: str) -> Dict[str, Dict[str, List[float]]]:
        """Load skeleton from JSON file.

        Expected JSON format (from generate_mjcf_skeleton.py or generate_smpl_skeleton.py):
        {
            "body_name": [[x, y, z], [w, x, y, z]],
            ...
        }

        Args:
            path: Path to JSON file

        Returns:
            Dictionary mapping body names to position and orientation
        """
        with open(path, 'r') as f:
            data = json.load(f)

        # Convert to unified format
        skeleton = {}
        for body_name, (position, orientation) in data.items():
            skeleton[body_name] = {
                "position": list(position) if isinstance(position, (list, tuple, np.ndarray)) else position,
                "orientation": list(orientation) if isinstance(orientation, (list, tuple, np.ndarray)) else orientation
            }

        return skeleton

    @staticmethod
    def from_mjcf(xml_path: str) -> Dict[str, Dict[str, List[float]]]:
        """Load skeleton directly from MuJoCo XML file.

        Args:
            xml_path: Path to MuJoCo XML file

        Returns:
            Dictionary mapping body names to position and orientation
        """
        import mujoco as mj

        # Load model and initialize data
        model = mj.MjModel.from_xml_path(xml_path)
        data = mj.MjData(model)
        mj.mj_forward(model, data)

        skeleton = {}
        for body_id in range(model.nbody):
            body = model.body(body_id)
            position = data.xpos[body_id].tolist()
            orientation = data.xquat[body_id].tolist()

            skeleton[body.name] = {
                "position": position,
                "orientation": orientation
            }

        return skeleton

    @staticmethod
    def from_smplx(npz_path: str, body_model_path: str) -> Dict[str, Dict[str, List[float]]]:
        """Load skeleton from SMPL-X file in rest pose.

        Args:
            npz_path: Path to SMPL-X .npz file
            body_model_path: Path to SMPL-X body model directory

        Returns:
            Dictionary mapping body names to position and orientation
        """
        from general_motion_retargeting.utils.smpl import load_smplx_file, get_smplx_data

        # Load SMPL-X data and model
        smplx_data, body_model, smplx_output, human_height = load_smplx_file(
            npz_path, body_model_path
        )

        # Get joint positions and orientations for the first frame
        skeleton_data = get_smplx_data(smplx_data, body_model, smplx_output, curr_frame=0)

        # Convert to unified format
        skeleton = {}
        for joint_name, (position, orientation) in skeleton_data.items():
            skeleton[joint_name] = {
                "position": position.tolist() if hasattr(position, 'tolist') else list(position),
                "orientation": orientation.tolist() if hasattr(orientation, 'tolist') else list(orientation)
            }

        return skeleton

    @staticmethod
    def from_robot_pose(pose_json_path: str, robot_xml_path: str) -> Dict[str, Dict[str, List[float]]]:
        """Load skeleton from robot pose JSON file by computing forward kinematics.

        This method takes a robot pose file containing joint angles and root pose,
        loads the robot's MuJoCo model, sets the configuration, and computes
        forward kinematics to get all body positions and orientations.

        Args:
            pose_json_path: Path to robot pose JSON file with format:
                {
                    "root_position": [x, y, z],
                    "root_quaternion": [w, x, y, z],
                    "joint_angles": {"joint_name": angle, ...}
                }
            robot_xml_path: Path to the robot's MuJoCo XML file

        Returns:
            Dictionary mapping body names to position and orientation
        """
        import mujoco as mj

        # Load the robot pose JSON
        with open(pose_json_path, 'r') as f:
            pose_data = json.load(f)

        # Extract root position, root quaternion, and joint angles
        root_position = np.array(pose_data["root_position"])
        root_quaternion = np.array(pose_data["root_quaternion"])  # [w, x, y, z]
        joint_angles = pose_data["joint_angles"]

        # Load MuJoCo model
        model = mj.MjModel.from_xml_path(robot_xml_path)
        data = mj.MjData(model)

        # Set root position (first 3 elements of qpos for freejoint)
        # MuJoCo freejoint qpos: [x, y, z, qw, qx, qy, qz]
        if model.nq >= 7:  # Has free joint
            data.qpos[0:3] = root_position
            data.qpos[3:7] = root_quaternion  # [w, x, y, z]
            qpos_offset = 7
        else:
            qpos_offset = 0

        # Set joint angles
        for joint_name, angle in joint_angles.items():
            # Find joint ID by name
            try:
                joint_id = mj.mj_name2id(model, mj.mjtObj.mjOBJ_JOINT, joint_name)
                joint_qposadr = model.jnt_qposadr[joint_id]
                data.qpos[joint_qposadr] = angle
            except KeyError:
                print(f"Warning: Joint '{joint_name}' not found in model, skipping")

        # Compute forward kinematics
        mj.mj_forward(model, data)

        # Extract all body positions and orientations
        skeleton = {}
        for body_id in range(model.nbody):
            body = model.body(body_id)
            position = data.xpos[body_id].tolist()
            orientation = data.xquat[body_id].tolist()

            skeleton[body.name] = {
                "position": position,
                "orientation": orientation
            }

        return skeleton

    @staticmethod
    def load(path: str, skeleton_type: str = "auto", robot_xml_path: str = None) -> Dict[str, Dict[str, List[float]]]:
        """Load skeleton with automatic type detection.

        Args:
            path: Path to skeleton file
            skeleton_type: Type of skeleton ("json", "mjcf", "smplx", "robot_pose", or "auto")
            robot_xml_path: Path to robot XML file (required for robot_pose type)

        Returns:
            Dictionary mapping body names to position and orientation
        """
        if skeleton_type == "auto":
            # Auto-detect based on file extension and content
            if path.endswith('.json'):
                # Check if it's a robot pose JSON by reading the file
                with open(path, 'r') as f:
                    data = json.load(f)

                # Robot pose JSON has "joint_angles" key
                if "joint_angles" in data:
                    skeleton_type = "robot_pose"
                else:
                    skeleton_type = "json"
            elif path.endswith('.xml'):
                skeleton_type = "mjcf"
            elif path.endswith('.npz'):
                skeleton_type = "smplx"
            else:
                raise ValueError(f"Cannot auto-detect skeleton type for file: {path}")

        if skeleton_type == "json":
            return SkeletonLoader.from_json(path)
        elif skeleton_type == "mjcf":
            return SkeletonLoader.from_mjcf(path)
        elif skeleton_type == "robot_pose":
            if robot_xml_path is None:
                raise ValueError("robot_xml_path is required for robot_pose skeleton type")
            return SkeletonLoader.from_robot_pose(path, robot_xml_path)
        elif skeleton_type == "smplx":
            raise ValueError("SMPL-X loading requires body_model_path. Use from_smplx() directly.")
        else:
            raise ValueError(f"Unknown skeleton type: {skeleton_type}")
