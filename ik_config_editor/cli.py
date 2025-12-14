#!/usr/bin/env python3
"""Command-line interface for IK Config Editor."""

import argparse
import sys

from ik_config_editor.ik_config_editor_app import IKConfigEditorApp


def main():
    """Main entry point for IK Config Editor CLI."""
    parser = argparse.ArgumentParser(
        description="IK Config Editor - Create IK configuration files for GMR",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Launch empty editor
  python -m ik_config_editor.cli

  # Pre-load source skeleton
  python -m ik_config_editor.cli --source path/to/skeleton.json

  # Pre-load both skeletons
  python -m ik_config_editor.cli \\
      --source smpl_skeleton.json --source-type json \\
      --target assets/unitree_g1/unitree_g1.xml --target-type mjcf

  # Load MuJoCo XML files directly
  python -m ik_config_editor.cli \\
      --source assets/booster_t1/booster_t1.xml \\
      --target assets/unitree_g1/unitree_g1.xml
        """
    )

    parser.add_argument(
        "--source",
        type=str,
        help="Path to source skeleton file (JSON or MuJoCo XML)"
    )

    parser.add_argument(
        "--source-type",
        type=str,
        default="auto",
        choices=["json", "mjcf", "robot_pose", "auto"],
        help="Type of source skeleton file (default: auto-detect from extension)"
    )

    parser.add_argument(
        "--source-xml",
        type=str,
        help="Path to source robot XML file (required if source is a robot pose JSON)"
    )

    parser.add_argument(
        "--target",
        type=str,
        help="Path to target skeleton file (JSON or MuJoCo XML)"
    )

    parser.add_argument(
        "--target-type",
        type=str,
        default="auto",
        choices=["json", "mjcf", "robot_pose", "auto"],
        help="Type of target skeleton file (default: auto-detect from extension)"
    )

    parser.add_argument(
        "--target-xml",
        type=str,
        help="Path to target robot XML file (required if target is a robot pose JSON)"
    )

    args = parser.parse_args()

    # Create and run the application
    try:
        app = IKConfigEditorApp(
            source_path=args.source,
            target_path=args.target,
            source_type=args.source_type,
            target_type=args.target_type,
            source_xml_path=args.source_xml,
            target_xml_path=args.target_xml
        )
        app.run()
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
