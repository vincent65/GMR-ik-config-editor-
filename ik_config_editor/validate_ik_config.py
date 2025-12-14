#!/usr/bin/env python3
"""Validate IK configuration files for correctness."""

import json
import sys
from pathlib import Path


def validate_ik_config(config_path: str):
    """Validate an IK configuration file.

    Checks:
    1. Format correctness
    2. Correspondence consistency
    3. Missing mappings for right_shoulder_pitch_link
    4. Scale factors
    5. Rotation offset format
    """
    print(f"Validating IK config: {config_path}\n")

    with open(config_path, 'r') as f:
        config = json.load(f)

    errors = []
    warnings = []

    # Check required fields
    required_fields = [
        "robot_root_name", "human_root_name", "human_scale_table",
        "ik_match_table1", "ik_match_table2"
    ]
    for field in required_fields:
        if field not in config:
            errors.append(f"Missing required field: {field}")

    if errors:
        print("❌ ERRORS:")
        for err in errors:
            print(f"  - {err}")
        return False

    # Check table1 and table2 consistency
    table1_bodies = set(config["ik_match_table1"].keys())
    table2_bodies = set(config["ik_match_table2"].keys())

    if table1_bodies != table2_bodies:
        warnings.append(f"Table1 and Table2 have different target bodies")
        print(f"  Table1 only: {table1_bodies - table2_bodies}")
        print(f"  Table2 only: {table2_bodies - table1_bodies}")

    # Check for missing right_shoulder_pitch_link
    source_bodies_in_table1 = [entry[0] for entry in config["ik_match_table1"].values()]

    if "right_shoulder_pitch_link" not in source_bodies_in_table1:
        warnings.append("Missing correspondence for 'right_shoulder_pitch_link' in source bodies")

    # Check for wrong mappings (hip → shoulder)
    print("📋 Checking correspondences...")
    suspicious_mappings = []

    for target_body, entry in config["ik_match_table1"].items():
        source_body = entry[0]

        # Check for hip-shoulder confusion
        if "hip" in target_body and "shoulder" in source_body:
            suspicious_mappings.append(f"  ❌ {target_body} → {source_body} (hip mapped to shoulder!)")
        elif "shoulder" in target_body and "hip" in source_body:
            suspicious_mappings.append(f"  ❌ {target_body} → {source_body} (shoulder mapped to hip!)")
        elif target_body == source_body:
            print(f"  ✓ {target_body} → {source_body} (perfect match)")
        else:
            print(f"  ~ {target_body} → {source_body} (different names, verify manually)")

    if suspicious_mappings:
        errors.extend(suspicious_mappings)

    # Check scale factors
    print(f"\n📏 Scale factors:")
    scales = config["human_scale_table"]
    unique_scales = set(scales.values())

    if len(unique_scales) == 1:
        print(f"  All scales are uniform: {list(unique_scales)[0]}")
        if list(unique_scales)[0] == 1.0:
            warnings.append("All scale factors are 1.0 - did you forget to enable auto-calculate scales?")
    else:
        print(f"  Non-uniform scaling: {len(unique_scales)} different values")
        print(f"  Range: {min(scales.values())} to {max(scales.values())}")

    # Check rotation offsets
    print(f"\n🔄 Rotation offsets:")
    identity_count = 0
    non_identity_count = 0

    for target_body, entry in config["ik_match_table1"].items():
        rot_offset = entry[4]
        if rot_offset == [1.0, 0.0, 0.0, 0.0]:
            identity_count += 1
        else:
            non_identity_count += 1

    print(f"  Identity offsets: {identity_count}")
    print(f"  Non-identity offsets: {non_identity_count}")

    if non_identity_count == 0:
        warnings.append("All rotation offsets are identity - did you forget to enable auto-calculate offsets?")

    # Summary
    print("\n" + "="*60)

    if errors:
        print("❌ VALIDATION FAILED")
        print(f"\n{len(errors)} error(s):")
        for err in errors:
            print(f"  {err}")
    else:
        print("✅ VALIDATION PASSED")

    if warnings:
        print(f"\n⚠️  {len(warnings)} warning(s):")
        for warn in warnings:
            print(f"  - {warn}")

    print("="*60)

    return len(errors) == 0


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python validate_ik_config.py <config.json>")
        sys.exit(1)

    config_path = sys.argv[1]
    success = validate_ik_config(config_path)
    sys.exit(0 if success else 1)
