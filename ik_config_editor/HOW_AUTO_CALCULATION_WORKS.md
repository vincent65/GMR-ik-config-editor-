# How Automatic Scaling and Offset Calculation Works

## Overview

The automatic calibration calculates three things:
1. **Rotation Offsets** - Align coordinate frames between skeletons
2. **Scale Factors** - Account for size differences
3. **Weights** - Prioritize important bodies (heuristic-based)

---

# Part 1: Rotation Offset Calculation

## The Problem

Human and robot skeletons have bodies oriented differently in 3D space.

### Example: Shoulder Joint

**Human SMPL-X skeleton (T-pose):**
```
Shoulder local frame:
  X-axis: Points laterally (towards hand)
  Y-axis: Points up
  Z-axis: Points forward

Orientation: [1, 0, 0, 0] (identity quaternion)
```

**Robot G1 skeleton (rest pose):**
```
Shoulder local frame:
  X-axis: Points DOWN (gravity direction)
  Y-axis: Points laterally
  Z-axis: Points forward

Orientation: [0.707, 0.707, 0, 0] (90° rotation around Z)
```

**Problem:** If we track the human shoulder directly, when human raises arm sideways (+X), robot will move arm downward!

---

## The Solution: Rotation Offset

We calculate an offset quaternion that transforms the source frame to the target frame.

### Formula:

```
q_offset = q_source^{-1} * q_target
```

Where:
- `q_source` = orientation of source (human) body in its skeleton's rest pose
- `q_target` = orientation of target (robot) body in its skeleton's rest pose
- `q_offset` = offset quaternion to align frames

### Why This Works:

During retargeting, when we have a human pose `q_human`, we compute:
```
q_robot_goal = q_human * q_offset
```

When human is at rest pose (`q_source`):
```
q_robot_goal = q_source * q_offset
             = q_source * (q_source^{-1} * q_target)
             = q_target  ✓
```

This correctly maps the source rest pose to the target rest pose!

---

## Step-by-Step Example

### Given:
```python
# From skeleton JSON files:
source["left_shoulder"]["orientation"] = [1.0, 0.0, 0.0, 0.0]  # Identity
target["left_shoulder_yaw_link"]["orientation"] = [0.707, 0.707, 0.0, 0.0]  # 90° rotation
```

### Step 1: Convert to Scipy Rotation Objects

```python
from scipy.spatial.transform import Rotation as R
import numpy as np

# Note: scipy uses [x,y,z,w], we use [w,x,y,z]
def to_scipy(quat_wxyz):
    return [quat_wxyz[1], quat_wxyz[2], quat_wxyz[3], quat_wxyz[0]]

q_source = R.from_quat(to_scipy([1.0, 0.0, 0.0, 0.0]))  # → [0,0,0,1]
q_target = R.from_quat(to_scipy([0.707, 0.707, 0.0, 0.0]))  # → [0.707,0,0,0.707]
```

### Step 2: Calculate Offset

```python
# q_offset = q_source^{-1} * q_target
q_offset = q_source.inv() * q_target

# Get as quaternion [x,y,z,w]
offset_xyzw = q_offset.as_quat()
# Convert to [w,x,y,z]
offset_wxyz = [offset_xyzw[3], offset_xyzw[0], offset_xyzw[1], offset_xyzw[2]]

print(offset_wxyz)
# Output: [0.707, 0.707, 0.0, 0.0]
```

### Step 3: Interpretation

The offset `[0.707, 0.707, 0, 0]` represents:
- A **90° rotation around the X-axis**
- This transforms the source frame to match the target frame

### Step 4: Usage in GMR

```python
# During retargeting, frame 100:
human_shoulder_orientation = [0.924, 0, 0.383, 0]  # Some pose

# GMR applies offset:
robot_target = human_shoulder_orientation * offset
             = [0.924, 0, 0.383, 0] * [0.707, 0.707, 0, 0]
             = [computed_result]  # Quaternion multiplication

# IK solver moves robot shoulder to match robot_target orientation
```

---

## Implementation Code

```python
def calculate_rotation_offset(source_orientation, target_orientation):
    """Calculate offset: q_offset = q_source^{-1} * q_target
    
    Usage: q_robot = q_human * q_offset
    """
    # Convert [w,x,y,z] → [x,y,z,w] for scipy
    source_rot = R.from_quat([
        source_orientation[1], source_orientation[2],
        source_orientation[3], source_orientation[0]
    ])
    target_rot = R.from_quat([
        target_orientation[1], target_orientation[2],
        target_orientation[3], target_orientation[0]
    ])

    # Calculate offset
    offset_rot = source_rot.inv() * target_rot

    # Convert back to [w,x,y,z]
    offset_quat = offset_rot.as_quat()  # Returns [x,y,z,w]
    return np.array([offset_quat[3], offset_quat[0], offset_quat[1], offset_quat[2]])
```

---

## When It Works / Doesn't Work

### ✅ Works When:

**Real skeleton data with meaningful orientations:**
```python
# From actual MuJoCo XML (robot in rest pose):
robot["pelvis"]["orientation"] = [0.5, -0.5, -0.5, -0.5]

# From actual SMPL-X (human in T-pose):
human["pelvis"]["orientation"] = [1, 0, 0, 0]

# Meaningful offset calculated
```

### ❌ Doesn't Work When:

**Mock data with identity orientations:**
```python
# Both identity:
human["shoulder"]["orientation"] = [1, 0, 0, 0]
robot["shoulder_link"]["orientation"] = [1, 0, 0, 0]

# Result:
offset = identity^{-1} * identity = identity  # No correction!
```

**Different reference poses not accounted for:**
- Human in T-pose (arms extended)
- Robot photographed with arms at sides
- Even with real data, poses must be comparable

---

# Part 2: Scale Factor Calculation

## The Problem

Humans and robots have different sizes!

### Example: Thigh Length

```
Human:
  Hip at [0, 0, 1.0]
  Knee at [0, 0, 0.5]
  Thigh length = 0.5m

Robot:
  Hip at [0, 0, 0.8]
  Knee at [0, 0, 0.4]
  Thigh length = 0.4m

Problem: If human's knee moves 0.5m from hip, robot can't reach that far!
```

---

## The Solution: Scale Factors

Calculate the ratio of bone lengths and use it to scale human positions into robot-proportional space.

### Formula:

```
scale = source_bone_length / target_bone_length
```

A "bone" is the distance between two connected bodies (parent → child).

---

## Height-Based Scaling

For overall size matching, we measure pelvis-to-ground height:

```python
def calculate_height_scale(source_skeleton, target_skeleton):
    # Measure pelvis height above ground (lowest foot)
    source_height = source_pelvis_z - min(source_foot_z)
    target_height = target_pelvis_z - min(target_foot_z)
    
    # Scale to match target size
    return target_height / source_height
```

**Interpretation:**
- If target is taller than source: scale > 1.0 (enlarge motion)
- If target is shorter than source: scale < 1.0 (shrink motion)

---

## Per-Limb Scaling

For robots with different proportions, we measure individual kinematic chains:

```python
chains = [
    # Legs
    ("pelvis", "left_hip"),    # Hip joint offset
    ("left_hip", "left_knee"), # Thigh
    ("left_knee", "left_foot"), # Shin

    # Arms
    ("spine3", "left_shoulder"),    # Shoulder offset
    ("left_shoulder", "left_elbow"), # Upper arm
    ("left_elbow", "left_wrist"),   # Forearm

    # Torso
    ("pelvis", "spine3"),  # Spine height
]
```

Each child body gets a scale factor from its parent-child bone length ratio.

---

## When It Works / Doesn't Work

### ✅ Works When:

**Real skeleton geometry:**
```python
# Actual measured positions from robot XML:
robot["pelvis"] = [0, 0, 0.774]
robot["left_hip_roll_link"] = [-0.0965, 0, 0.724]

# Meaningful scale calculated
```

### ❌ Doesn't Work When:

**Mock data with arbitrary positions:**
```python
# Made-up positions:
human["pelvis"] = [0, 0, 1.0]  # Random
human["left_hip"] = [-0.1, 0, 0.9]  # Random

# Scale calculation will be meaningless
```

---

# Part 3: Weight Suggestions

## The Problem

IK solver needs to know which bodies are most important to track accurately.

### Example:

```
Foot on ground: CRITICAL (pos_weight = 100)
  → Must touch ground exactly, no floating!

Pelvis height: IMPORTANT (pos_weight = 100)
  → Determines overall robot height

Elbow position: LESS IMPORTANT (pos_weight = 10)
  → Rotation matters more, position follows kinematics

Spine rotation: VERY IMPORTANT (rot_weight = 100)
  → Determines upper body posture
```

---

## The Solution: Keyword Matching

We use heuristics based on body names to suggest weights.

### Position Weights:

```python
if 'foot' in body_name or 'toe' in body_name or 'pelvis' in body_name:
    pos_weight = 100  # HIGH - must be precisely positioned

elif 'knee' in body_name or 'elbow' in body_name:
    pos_weight = 10  # MEDIUM - helps with pose

else:
    pos_weight = 0  # LOW - rotation sufficient
```

### Rotation Weights:

```python
if 'foot' in body_name or 'hand' in body_name or 'wrist' in body_name:
    rot_weight = 50  # End effector orientation matters

elif 'shoulder' in body_name or 'spine' in body_name or 'torso' in body_name:
    rot_weight = 100  # Upper body posture critical

else:
    rot_weight = 10  # Default
```

---

## Limitations

This is **heuristic-based**, not physics-based:

- ✅ Works well for standard humanoid skeletons
- ✅ Provides reasonable starting points
- ⚠️ May need manual tuning for:
  - Custom robot morphologies
  - Specific behaviors (e.g., hand manipulation vs. locomotion)
  - Performance optimization

**Example where it fails:**
```python
# Custom robot with unusual naming:
"tip_003_link"  # Actually the foot, but no keyword match!
→ Gets default weights instead of high weights
```

---

# Summary

## What Auto-Calculation Does:

1. **Rotation Offsets**: Aligns coordinate frames using quaternion math
   - Formula: `offset = source^{-1} * target`
   - Requires: Real skeleton orientations (not all identity)

2. **Scale Factors**: Measures bone length ratios
   - Formula: `scale = source_length / target_length` (per-limb) or `target_height / source_height` (height-based)
   - Requires: Real skeleton geometry (not arbitrary positions)

3. **Weights**: Keywords → suggested priorities
   - Method: Pattern matching on body names
   - Requires: Standard naming conventions

## Limitations:

| Feature | Requires | Works with Mocks? |
|---------|----------|-------------------|
| Rotation offsets | Real orientations | ❌ No |
| Scale factors | Real positions | ❌ No |
| Weights | Standard names | ✅ Yes |

## Recommendations:

1. **Always use real skeleton files** from actual sources:
   - Load MuJoCo XML directly for robots
   - Use actual SMPL-X or BVH data for humans

2. **Enable automatic calibration** when creating configs

3. **Test and refine** - auto-calculation gives you 80-90%, manual tuning gets the last 10-20%

---

**The auto-calibration is a powerful starting point, but understanding the math helps you debug and refine when needed!**
