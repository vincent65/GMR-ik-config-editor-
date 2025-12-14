#!/usr/bin/env python3
"""
Test and validate IK configuration quality.

This script helps you verify if your generated IK config is correct by:
1. Checking JSON structure validity
2. Comparing with reference configs
3. Testing with actual motion retargeting (if motion data available)
4. Providing diagnostic feedback

Usage:
    python ik_config_editor/test_ik_config_quality.py --config path/to/config.json
    python ik_config_editor/test_ik_config_quality.py --config path/to/config.json --reference general_motion_retargeting/ik_configs/smplx_to_g1.json
    python ik_config_editor/test_ik_config_quality.py --config path/to/config.json --test-motion path/to/motion.npz --robot unitree_g1
"""

import sys
import os
import json
import argparse
from typing import Dict, List, Tuple

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class IKConfigTester:
    """Test and validate IK configuration files."""

    def __init__(self, config_path: str):
        self.config_path = config_path
        self.config = None
        self.errors = []
        self.warnings = []
        self.info = []

    def load_config(self) -> bool:
        """Load and parse the config file."""
        print(f"Loading config: {self.config_path}")
        try:
            with open(self.config_path, 'r') as f:
                self.config = json.load(f)
            print("✓ Config loaded successfully\n")
            return True
        except FileNotFoundError:
            self.errors.append(f"Config file not found: {self.config_path}")
            return False
        except json.JSONDecodeError as e:
            self.errors.append(f"Invalid JSON: {e}")
            return False

    def test_structure(self) -> bool:
        """Test 1: Verify config has all required fields."""
        print("=" * 70)
        print("TEST 1: Structure Validation")
        print("=" * 70)

        required_keys = [
            "robot_root_name",
            "human_root_name",
            "ground_height",
            "human_height_assumption",
            "use_ik_match_table1",
            "use_ik_match_table2",
            "human_scale_table",
            "ik_match_table1",
            "ik_match_table2"
        ]

        missing = []
        for key in required_keys:
            if key not in self.config:
                missing.append(key)

        if missing:
            self.errors.append(f"Missing required keys: {missing}")
            print(f"✗ FAILED: Missing keys: {missing}\n")
            return False
        else:
            print("✓ All required keys present")
            print(f"  - Robot root: {self.config['robot_root_name']}")
            print(f"  - Human root: {self.config['human_root_name']}")
            print(f"  - Ground height: {self.config['ground_height']}")
            print(f"  - Human height: {self.config['human_height_assumption']}")
            print(f"  - Scale entries: {len(self.config['human_scale_table'])}")
            print(f"  - Table1 entries: {len(self.config['ik_match_table1'])}")
            print(f"  - Table2 entries: {len(self.config['ik_match_table2'])}")
            print()
            return True

    def test_entry_format(self) -> bool:
        """Test 2: Verify each table entry has correct format."""
        print("=" * 70)
        print("TEST 2: Entry Format Validation")
        print("=" * 70)

        def validate_entry(table_name: str, target_body: str, entry: list) -> bool:
            """Validate a single entry."""
            if not isinstance(entry, list):
                self.errors.append(f"{table_name}[{target_body}]: Not a list")
                return False

            if len(entry) != 5:
                self.errors.append(f"{table_name}[{target_body}]: Expected 5 elements, got {len(entry)}")
                return False

            # [0] Source body name (string)
            if not isinstance(entry[0], str):
                self.errors.append(f"{table_name}[{target_body}][0]: Source name must be string")
                return False

            # [1] Position weight (number)
            if not isinstance(entry[1], (int, float)):
                self.errors.append(f"{table_name}[{target_body}][1]: Position weight must be number")
                return False

            # [2] Rotation weight (number)
            if not isinstance(entry[2], (int, float)):
                self.errors.append(f"{table_name}[{target_body}][2]: Rotation weight must be number")
                return False

            # [3] Position offset (3D vector)
            if not isinstance(entry[3], list) or len(entry[3]) != 3:
                self.errors.append(f"{table_name}[{target_body}][3]: Position offset must be [x,y,z]")
                return False

            # [4] Rotation offset (quaternion [w,x,y,z])
            if not isinstance(entry[4], list) or len(entry[4]) != 4:
                self.errors.append(f"{table_name}[{target_body}][4]: Rotation offset must be [w,x,y,z]")
                return False

            return True

        all_valid = True
        for target_body, entry in self.config["ik_match_table1"].items():
            if not validate_entry("ik_match_table1", target_body, entry):
                all_valid = False

        for target_body, entry in self.config["ik_match_table2"].items():
            if not validate_entry("ik_match_table2", target_body, entry):
                all_valid = False

        if all_valid:
            print("✓ All entries have correct format")
            print()
            return True
        else:
            print("✗ FAILED: Some entries have invalid format")
            print()
            return False

    def test_weights(self) -> bool:
        """Test 3: Analyze IK weights for common issues."""
        print("=" * 70)
        print("TEST 3: Weight Analysis")
        print("=" * 70)

        # Check for feet with low position weights (common mistake!)
        foot_keywords = ['foot', 'toe', 'ankle']
        feet_with_low_pos_weight = []

        for target_body, entry in self.config["ik_match_table1"].items():
            pos_weight = entry[1]
            if any(kw in target_body.lower() for kw in foot_keywords):
                if pos_weight < 50:
                    feet_with_low_pos_weight.append((target_body, pos_weight))

        if feet_with_low_pos_weight:
            self.warnings.append("Feet have low position weights - may float off ground!")
            print("⚠ WARNING: Feet have low position weights:")
            for body, weight in feet_with_low_pos_weight:
                print(f"  - {body}: pos_weight = {weight} (recommend >= 100)")
        else:
            print("✓ Foot position weights look good")

        # Check for pelvis with low position weight
        pelvis_bodies = [b for b in self.config["ik_match_table1"].keys() if 'pelvis' in b.lower()]
        if pelvis_bodies:
            pelvis_weight = self.config["ik_match_table1"][pelvis_bodies[0]][1]
            if pelvis_weight < 50:
                self.warnings.append(f"Pelvis position weight is low ({pelvis_weight})")
                print(f"⚠ WARNING: Pelvis position weight = {pelvis_weight} (recommend >= 100)")
            else:
                print(f"✓ Pelvis position weight = {pelvis_weight}")

        # Check for all zeros (not necessarily bad, but worth noting)
        all_zero_pos = all(entry[1] == 0 for entry in self.config["ik_match_table1"].values())
        if all_zero_pos:
            self.warnings.append("All position weights are 0")
            print("⚠ WARNING: All position weights are 0 (rotation-only IK)")

        print()
        return True

    def test_quaternions(self) -> bool:
        """Test 4: Verify rotation offsets are valid quaternions."""
        print("=" * 70)
        print("TEST 4: Quaternion Validation")
        print("=" * 70)

        import numpy as np

        invalid_quats = []
        identity_count = 0

        for target_body, entry in self.config["ik_match_table1"].items():
            quat = np.array(entry[4])
            norm = np.linalg.norm(quat)

            # Check if valid quaternion (norm should be 1.0)
            if not (0.99 < norm < 1.01):
                invalid_quats.append((target_body, norm))

            # Count identity quaternions
            if np.allclose(quat, [1, 0, 0, 0], atol=1e-6):
                identity_count += 1

        if invalid_quats:
            print("✗ FAILED: Invalid quaternions found:")
            for body, norm in invalid_quats:
                print(f"  - {body}: norm = {norm} (should be ~1.0)")
            print()
            return False
        else:
            print("✓ All quaternions are valid (unit norm)")

        total = len(self.config["ik_match_table1"])
        print(f"  - Identity quaternions: {identity_count}/{total}")
        if identity_count == total:
            self.info.append("All rotation offsets are identity (no automatic calibration)")
            print("  ℹ All offsets are identity - consider enabling auto-calibration")

        print()
        return True

    def test_scales(self) -> bool:
        """Test 5: Analyze scale factors."""
        print("=" * 70)
        print("TEST 5: Scale Factor Analysis")
        print("=" * 70)

        import numpy as np

        scales = list(self.config["human_scale_table"].values())
        if not scales:
            self.errors.append("human_scale_table is empty")
            print("✗ FAILED: No scale factors\n")
            return False

        scales_array = np.array(scales)
        min_scale = np.min(scales_array)
        max_scale = np.max(scales_array)
        mean_scale = np.mean(scales_array)
        std_scale = np.std(scales_array)

        print(f"✓ Scale factor statistics:")
        print(f"  - Min:  {min_scale:.3f}")
        print(f"  - Max:  {max_scale:.3f}")
        print(f"  - Mean: {mean_scale:.3f}")
        print(f"  - Std:  {std_scale:.3f}")

        # Warn if all scales are 1.0
        if np.allclose(scales_array, 1.0, atol=1e-6):
            self.info.append("All scales are 1.0 (no automatic calibration)")
            print("  ℹ All scales are 1.0 - consider enabling auto-calibration")

        # Warn if huge scale variation
        if max_scale / min_scale > 2.0:
            self.warnings.append(f"Large scale variation: {max_scale/min_scale:.2f}x")
            print(f"  ⚠ Large variation ({max_scale/min_scale:.2f}x) - verify this is correct")

        print()
        return True

    def compare_with_reference(self, reference_path: str):
        """Test 6: Compare with a reference config."""
        print("=" * 70)
        print("TEST 6: Comparison with Reference Config")
        print("=" * 70)

        try:
            with open(reference_path, 'r') as f:
                ref_config = json.load(f)
        except Exception as e:
            print(f"✗ Could not load reference: {e}\n")
            return

        print(f"Reference: {reference_path}\n")

        # Compare number of mappings
        ref_count = len(ref_config["ik_match_table1"])
        our_count = len(self.config["ik_match_table1"])

        print(f"Mapping count:")
        print(f"  Reference: {ref_count}")
        print(f"  Your config: {our_count}")

        if our_count < ref_count:
            self.warnings.append(f"Fewer mappings than reference ({our_count} vs {ref_count})")
            print(f"  ⚠ You have fewer mappings")
        elif our_count > ref_count:
            print(f"  ℹ You have more mappings")
        else:
            print(f"  ✓ Same number of mappings")

        # Check which bodies are different
        ref_bodies = set(ref_config["ik_match_table1"].keys())
        our_bodies = set(self.config["ik_match_table1"].keys())

        missing = ref_bodies - our_bodies
        extra = our_bodies - ref_bodies

        if missing:
            print(f"\n  Bodies in reference but not in yours: {missing}")
        if extra:
            print(f"\n  Bodies in yours but not in reference: {extra}")

        # Compare a sample entry
        common_bodies = ref_bodies & our_bodies
        if common_bodies:
            sample_body = list(common_bodies)[0]
            print(f"\nSample comparison ('{sample_body}'):")
            print(f"  Reference: {ref_config['ik_match_table1'][sample_body]}")
            print(f"  Your config: {self.config['ik_match_table1'][sample_body]}")

        print()

    def print_summary(self):
        """Print test summary."""
        print("=" * 70)
        print("TEST SUMMARY")
        print("=" * 70)

        if self.errors:
            print(f"\n❌ ERRORS ({len(self.errors)}):")
            for error in self.errors:
                print(f"  • {error}")

        if self.warnings:
            print(f"\n⚠️  WARNINGS ({len(self.warnings)}):")
            for warning in self.warnings:
                print(f"  • {warning}")

        if self.info:
            print(f"\nℹ️  INFO ({len(self.info)}):")
            for info in self.info:
                print(f"  • {info}")

        print()

        if not self.errors:
            print("✅ CONFIG IS VALID AND READY TO USE!")
            if self.warnings:
                print("   (Some warnings - may want to review)")
        else:
            print("❌ CONFIG HAS ERRORS - FIX BEFORE USING")

        print()


def test_with_motion(config_path: str, motion_path: str, robot: str):
    """Test 7: Actually run retargeting with the config."""
    print("=" * 70)
    print("TEST 7: Motion Retargeting Test")
    print("=" * 70)

    print(f"Config: {config_path}")
    print(f"Motion: {motion_path}")
    print(f"Robot: {robot}")
    print()

    # This would require modifying params.py and running the actual retargeting
    # For now, provide instructions
    print("To test with actual motion retargeting:")
    print()
    print("1. Add your config to params.py:")
    print(f'   IK_CONFIG_DICT[("smplx", "{robot}_test")] = "{config_path}"')
    print()
    print("2. Run retargeting:")
    print(f'   python scripts/smplx_to_robot.py \\')
    print(f'       --smplx_file {motion_path} \\')
    print(f'       --robot {robot}_test \\')
    print(f'       --visualize \\')
    print(f'       --save_path test_output.pkl')
    print()
    print("3. Look for:")
    print("   ✓ No errors during IK solving")
    print("   ✓ Robot moves smoothly")
    print("   ✓ Feet touch ground")
    print("   ✓ Limbs point in correct directions")
    print("   ✓ No extreme joint angles or NaN values")
    print()


def main():
    parser = argparse.ArgumentParser(
        description="Test and validate IK configuration files",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Basic validation
  python ik_config_editor/test_ik_config_quality.py --config test_data/test_ik_config.json

  # Compare with reference
  python ik_config_editor/test_ik_config_quality.py \\
      --config test_data/test_ik_config.json \\
      --reference general_motion_retargeting/ik_configs/smplx_to_g1.json

  # Test with motion (shows instructions)
  python ik_config_editor/test_ik_config_quality.py \\
      --config test_data/test_ik_config.json \\
      --test-motion path/to/motion.npz \\
      --robot unitree_g1
        """
    )

    parser.add_argument("--config", required=True, help="Path to IK config to test")
    parser.add_argument("--reference", help="Path to reference config for comparison")
    parser.add_argument("--test-motion", help="Path to motion file for retargeting test")
    parser.add_argument("--robot", help="Robot name for retargeting test")

    args = parser.parse_args()

    # Run tests
    tester = IKConfigTester(args.config)

    if not tester.load_config():
        tester.print_summary()
        return 1

    tester.test_structure()
    tester.test_entry_format()
    tester.test_weights()
    tester.test_quaternions()
    tester.test_scales()

    if args.reference:
        tester.compare_with_reference(args.reference)

    tester.print_summary()

    if args.test_motion and args.robot:
        test_with_motion(args.config, args.test_motion, args.robot)

    return 0 if not tester.errors else 1


if __name__ == "__main__":
    sys.exit(main())
