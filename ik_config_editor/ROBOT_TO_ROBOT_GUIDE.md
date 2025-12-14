# Robot-to-Robot Retargeting with IK Config Editor

This guide explains how to use the IK Config Editor to create IK configurations for robot-to-robot motion retargeting.

## Overview

The IK config editor now supports loading robot pose files (T-pose configurations with joint angles) to enable robot-to-robot retargeting. This allows you to:

1. Create T-pose configurations for your robots
2. Map body correspondences between two robots
3. Generate IK configs with automatic rotation offsets and scaling
4. Leverage existing human-to-robot configs by using intermediate robot mappings

## Workflow

### Step 1: Create Robot T-Pose Files

For each robot you want to work with, create a T-pose configuration JSON file with this format:

```json
{
  "root_position": [x, y, z],
  "root_quaternion": [w, x, y, z],
  "joint_angles": {
    "joint_name": angle_in_radians,
    ...
  }
}
```

**Example**: `test_data/g1_t_pose.json`

The T-pose should have:
- Arms extended horizontally to the sides
- Legs straight, feet on the ground
- Body upright and balanced

You can create this file using the pose editor (program 1) or manually by setting joint angles.

### Step 2: Launch the IK Config Editor

**Option A: Using the GUI with file dialogs**

```bash
conda activate gmr
python -m ik_config_editor.cli
```

Then:
1. Click "Load Source Skeleton" → select your source robot T-pose JSON (e.g., `g1_t_pose.json`)
2. When prompted, select the robot's XML file (e.g., `g1.xml`)
3. Click "Load Target Skeleton" → select your target robot T-pose JSON
4. When prompted, select the target robot's XML file

**Option B: Using command-line arguments**

```bash
conda activate gmr
python -m ik_config_editor.cli \
    --source test_data/g1_t_pose.json \
    --source-xml g1.xml \
    --target test_data/other_robot_t_pose.json \
    --target-xml assets/other_robot/robot.xml
```

### Step 3: Create Body Correspondences

In the GUI:

1. You'll see both robot skeletons displayed side-by-side in 3D
2. In the "Body Correspondences" section, map source bodies to target bodies:
   - For each source robot body, select the corresponding target robot body from the dropdown
   - Example: `pelvis` → `pelvis`, `left_hip_roll_link` → `left_hip_link`, etc.
3. Common body mappings:
   - Pelvis/torso (root)
   - Hip joints (left/right)
   - Knee joints (left/right)
   - Foot/ankle links (left/right)
   - Shoulder joints (left/right)
   - Elbow joints (left/right)
   - Wrist/hand links (left/right)

**Tip**: You don't need to map every body - focus on the main kinematic chain bodies.

### Step 4: Configure Automatic Calibration

Enable the Phase 2 automatic features:

1. **☑ Auto-calculate rotation offsets** (HIGHLY RECOMMENDED)
   - Calculates the rotation offset quaternion for each body pair
   - Formula: `q_offset = q_source^(-1) * q_target`
   - Ensures proper alignment between robot coordinate frames

2. **☑ Auto-calculate scale factors** (RECOMMENDED)
   - Enables height-based and/or limb-based scaling

3. **☑ Use height-based scaling** (RECOMMENDED)
   - Computes uniform scale from pelvis-to-ground height
   - Ensures overall size matching between robots

4. **☑ Use per-limb scaling adjustments** (OPTIONAL)
   - Adds per-limb proportional adjustments
   - Useful if robots have different body proportions
   - Multiplies with height scale

5. **☑ Auto-suggest IK weights** (OPTIONAL)
   - Automatically sets position/rotation weights based on body type
   - End effectors (feet, hands) get higher position weights
   - Spine/shoulders get higher rotation weights

### Step 5: Configure Root Names

Set the root body names:

- **Robot Root**: The target robot's root body (usually `"pelvis"`)
- **Human Root**: The source robot's root body (usually `"pelvis"`)
- **Human Height**: Reference height in meters (default: `1.8`)

For robot-to-robot, both root names should typically be `"pelvis"` or the equivalent root link.

### Step 6: Export IK Configuration

1. Click "Export IK Config"
2. Choose a save location (e.g., `ik_configs/g1_to_other_robot.json`)
3. The generated config will include:
   - Rotation offsets (if auto-calculated)
   - Scale factors (if auto-calculated)
   - Position offsets (all zero as specified)
   - IK weights (auto-suggested or default)
   - Two IK match tables (table1 and table2)

## Generated IK Config Format

The exported JSON will have this structure:

```json
{
    "robot_root_name": "pelvis",
    "human_root_name": "pelvis",
    "ground_height": 0.0,
    "human_height_assumption": 1.8,
    "use_ik_match_table1": true,
    "use_ik_match_table2": true,
    "human_scale_table": {
        "pelvis": 1.15,
        "left_hip": 1.15,
        "left_knee": 1.15,
        ...
    },
    "ik_match_table1": {
        "target_body_name": [
            "source_body_name",
            position_weight,
            rotation_weight,
            [0.0, 0.0, 0.0],           // position offset (always zero)
            [qw, qx, qy, qz]           // rotation offset (auto-calculated)
        ],
        ...
    },
    "ik_match_table2": { ... }
}
```

## Key Features

### Rotation Offset Calculation

The rotation offset quaternion is calculated using:

```
q_offset = q_source^(-1) * q_target
```

This ensures that when the source motion is applied (`q_source * q_offset`), the result correctly maps to the target frame (`q_target`).

### Height-Based Scaling

Measures the distance from the pelvis to the lowest foot position (ground level):

```
height_source = pelvis_z_source - min(foot_z_source)
height_target = pelvis_z_target - min(foot_z_target)
scale = height_source / height_target
```

This scale is applied uniformly to all bodies in the `human_scale_table`.

### Per-Limb Scaling

Calculates bone length ratios for kinematic chains:

- Legs: pelvis → hip → knee → foot
- Arms: spine → shoulder → elbow → wrist
- Torso: pelvis → spine

Each body gets a scale factor based on its parent-child bone length ratio. This is multiplied with the height scale for combined scaling.

## Use Case: Leveraging Existing Configs

**Scenario**: You have a `lafan → g1` IK config and want to create `lafan → new_robot`.

**Solution**:

1. Create `g1 → new_robot` IK config using this editor
2. Use the G1 as an intermediate representation:
   - The `lafan → g1` config maps LAFAN human skeleton to G1 robot
   - The `g1 → new_robot` config provides the geometric transform between robots
3. You can then either:
   - **Option A**: Create a new `lafan → new_robot` config by adapting the body correspondences from the G1 config
   - **Option B**: Chain the retargeting (less ideal): LAFAN → G1 motion → new_robot motion

## Loading Robot Poses

The skeleton loader supports robot T-pose JSON files directly. When you load a T-pose file via the GUI, it will prompt for the robot XML file to compute forward kinematics and extract body positions/orientations.

## Troubleshooting

### "robot_xml_path is required" error

If you load a robot pose JSON via CLI without `--source-xml` or `--target-xml`, you'll get this error. Solutions:

1. Add the XML path arguments to your command
2. Use the GUI which will prompt for the XML path automatically

### Bodies don't align visually

This is expected! The T-poses may look different between robots. The IK config will handle the rotation offsets and scaling to make the retargeting work correctly.

### Scale factors seem wrong

Check:
1. Are both robots in proper T-pose with feet on ground?
2. Is the pelvis body named correctly in both skeletons?
3. Are there foot/toe/ankle bodies for height calculation?

You can manually adjust scale factors in the generated JSON if needed.

### Missing correspondences warning

You don't need to map every body - only the ones important for your retargeting task. Common minimal sets:

- **Lower body**: pelvis, hips, knees, feet
- **Upper body**: spine/torso, shoulders, elbows, wrists
- **Full body**: all of the above

## Example Commands

**Create G1 to Booster T1 config**:

```bash
python -m ik_config_editor.cli \
    --source test_data/g1_t_pose.json \
    --source-xml g1.xml \
    --target test_data/booster_t1_t_pose.json \
    --target-xml assets/booster_t1/booster_t1.xml
```

**Load T-pose files directly**:

```bash
# The editor will prompt for XML files when loading T-pose JSONs
python -m ik_config_editor.cli \
    --source test_data/g1_t_pose.json \
    --source-xml g1.xml \
    --target test_data/t1_t_pose.json \
    --target-xml assets/booster_t1/booster_t1.xml
```

## Next Steps

After generating your IK config:

1. Test it with actual motion retargeting
2. Fine-tune weights if needed (position/rotation weights in the JSON)
3. Adjust scale factors if the motion looks too large/small
4. Verify end effector alignment (feet, hands)

For robot-to-robot retargeting code, you'll need to adapt the `GeneralMotionRetargeting` class to accept robot motion input instead of human motion input.
