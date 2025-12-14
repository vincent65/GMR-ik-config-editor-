# Quick Start: Robot-to-Robot IK Config Editor

## Prerequisites

You need:
1. **Robot T-pose JSON file** for source robot (e.g., `g1_t_pose.json`)
2. **Robot XML file** for source robot (e.g., `g1.xml`)
3. **Robot T-pose JSON file** for target robot
4. **Robot XML file** for target robot

## T-Pose JSON Format

```json
{
  "root_position": [0.0, 0.064452, -0.1027],
  "root_quaternion": [1.0, 0.0, 0.0, 0.0],
  "joint_angles": {
    "left_hip_pitch_joint": 0.0,
    "left_shoulder_roll_joint": 1.53,
    "right_shoulder_roll_joint": -1.53,
    "left_elbow_joint": 1.53,
    ...
  }
}
```

## Quick Start (CLI)

```bash
# Activate environment
conda activate gmr

# Launch editor with both robots
python -m ik_config_editor.cli \
    --source test_data/g1_t_pose.json \
    --source-xml g1.xml \
    --target test_data/target_robot_t_pose.json \
    --target-xml assets/target_robot/robot.xml
```

## Quick Start (GUI)

```bash
conda activate gmr
python -m ik_config_editor.cli
```

Then:
1. Click "Load Source Skeleton" → select `g1_t_pose.json`
2. When prompted, select `g1.xml`
3. Click "Load Target Skeleton" → select target robot's T-pose JSON
4. When prompted, select target robot's XML
5. Map bodies in "Body Correspondences" section
6. Enable automatic calibration:
   - ☑ Auto-calculate rotation offsets
   - ☑ Auto-calculate scale factors
   - ☑ Use height-based scaling
   - ☑ Use per-limb scaling adjustments
7. Click "Export IK Config" → save the file

## Essential Body Mappings

Map at minimum:
- **pelvis** → **pelvis** (or equivalent root)
- **left_hip** → **left_hip_link**
- **right_hip** → **right_hip_link**
- **left_knee** → **left_knee_link**
- **right_knee** → **right_knee_link**
- **left_foot** → **left_ankle_link** or **left_toe_link**
- **right_foot** → **right_ankle_link** or **right_toe_link**
- **left_shoulder** → **left_shoulder_link**
- **right_shoulder** → **right_shoulder_link**
- **left_elbow** → **left_elbow_link**
- **right_elbow** → **right_elbow_link**

## Recommended Settings

For robot-to-robot retargeting:
- **Target Root**: `"pelvis"` (target robot's root body)
- **Source Root**: `"pelvis"` (source robot's root body)
- **Source Height (m)**: `1.8` (reference baseline height)
- **Auto-calculate rotation offsets**: ✓ **ENABLED** (highly recommended)
- **Auto-calculate scale factors**: ✓ **ENABLED** (recommended)
- **Use height-based scaling**: ✓ **ENABLED** (recommended)
- **Use per-limb scaling**: ✓ **ENABLED** (optional, for different proportions)

## Helper: Pre-Generate Skeleton Files

To avoid needing XML every time:

```bash
# Generate full skeleton JSON from robot pose
python -m ik_config_editor.generate_robot_pose_skeleton \
    test_data/g1_t_pose.json \
    g1.xml \
    test_data/g1_skeleton.json

# Then load the skeleton JSON directly (no XML needed)
python -m ik_config_editor.cli \
    --source test_data/g1_skeleton.json \
    --target test_data/target_skeleton.json
```

## Output

Generated IK config will be saved as JSON:
```json
{
  "robot_root_name": "pelvis",
  "human_root_name": "pelvis",
  "human_scale_table": {
    "pelvis": 1.15,
    "left_hip": 1.15,
    ...
  },
  "ik_match_table1": {
    "pelvis": ["pelvis", 100, 10, [0,0,0], [qw,qx,qy,qz]],
    ...
  },
  ...
}
```

## Troubleshooting

**Q**: "robot_xml_path is required" error?
**A**: Add `--source-xml` or `--target-xml` argument, or use GUI which prompts automatically

**Q**: Bodies don't align visually?
**A**: Normal! The IK config handles rotation offsets. Focus on mapping corresponding bodies.

**Q**: Scale seems wrong?
**A**: Check both robots are in T-pose with feet on ground. Manually adjust in generated JSON if needed.

## Next Steps

After generating your IK config:
1. Save it to `ik_configs/` directory
2. Test with motion retargeting
3. Fine-tune weights/scales if needed

## Full Documentation

- `ROBOT_TO_ROBOT_GUIDE.md` - Complete user guide
- `IMPLEMENTATION_SUMMARY.md` - Technical details
- `README.md` - General overview
