#!/usr/bin/env python3
"""Generate skeleton JSON from robot pose JSON file.

This script converts a robot pose file (joint angles + root pose) into
a full skeleton file (all body positions/orientations) by computing
forward kinematics.

This is useful for pre-generating skeleton files to avoid needing the
XML file when loading in the IK config editor.
"""

import argparse
import json

from ik_config_editor.skeleton_loader import SkeletonLoader


def main():
    parser = argparse.ArgumentParser(
        description="Generate skeleton JSON from robot pose JSON",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Example:
  python ik_config_editor/generate_robot_pose_skeleton.py \\
      test_data/g1_t_pose.json \\
      g1.xml \\
      test_data/g1_t_pose_skeleton.json

Input format (robot pose JSON):
  {
    "root_position": [x, y, z],
    "root_quaternion": [w, x, y, z],
    "joint_angles": {
      "joint_name": angle,
      ...
    }
  }

Output format (skeleton JSON):
  {
    "body_name": [[x, y, z], [w, x, y, z]],
    ...
  }
        """
    )

    parser.add_argument(
        "pose_json",
        type=str,
        help="Path to robot pose JSON file"
    )

    parser.add_argument(
        "robot_xml",
        type=str,
        help="Path to robot MuJoCo XML file"
    )

    parser.add_argument(
        "output_json",
        type=str,
        help="Path to save the generated skeleton JSON"
    )

    args = parser.parse_args()

    # Load skeleton from robot pose
    print(f"Loading robot pose from: {args.pose_json}")
    print(f"Using robot XML: {args.robot_xml}")

    skeleton = SkeletonLoader.from_robot_pose(args.pose_json, args.robot_xml)

    print(f"Loaded skeleton with {len(skeleton)} bodies")

    # Convert to output format (tuple format for compatibility)
    output_data = {}
    for body_name, data in skeleton.items():
        output_data[body_name] = [
            data["position"],
            data["orientation"]
        ]

    # Save to file
    with open(args.output_json, 'w') as f:
        json.dump(output_data, f, indent=4)

    print(f"Saved skeleton to: {args.output_json}")
    print(f"\nYou can now load this file directly in the IK config editor without needing the XML file.")


if __name__ == "__main__":
    main()
