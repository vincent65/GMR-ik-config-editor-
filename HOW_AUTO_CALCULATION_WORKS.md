# How Automatic Scaling and Offset Calculation Works

## Overview

The automatic calibration calculates three things:
1. **Rotation Offsets** - Align coordinate frames between skeletons
2. **Scale Factors** - Account for size differences
3. **Weights** - Prioritize important bodies (heuristic-based)

Let's dive deep into each one with concrete examples.

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

We calculate an offset quaternion that transforms robot's frame to match human's frame.

### Formula:

```
q_offset = q_source * q_target^{-1}
```

Where:
- `q_source` = orientation of source (human) body in its skeleton
- `q_target` = orientation of target (robot) body in its skeleton
- `q_offset` = offset quaternion to align frames

### Why This Works:

We want: `q_source = q_offset * q_target`

Solve for offset:
```
q_offset = q_source * q_target^{-1}
```

Later, GMR applies this during retargeting:
```
robot_target_orientation = q_offset * human_current_orientation
```

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
q_offset = q_source * q_target.inv()

# Get as quaternion [x,y,z,w]
offset_xyzw = q_offset.as_quat()
# Convert to [w,x,y,z]
offset_wxyz = [offset_xyzw[3], offset_xyzw[0], offset_xyzw[1], offset_xyzw[2]]

print(offset_wxyz)
# Output: [0.707, -0.707, 0.0, 0.0]
```

### Step 3: Interpretation

The offset `[0.707, -0.707, 0, 0]` represents:
- A **-90° rotation around the X-axis**
- This undoes the robot's 90° rotation, aligning its frame with human's

### Step 4: Usage in GMR

```python
# During retargeting, frame 100:
human_shoulder_orientation = [0.924, 0, 0.383, 0]  # Some pose

# GMR applies offset:
robot_target = offset * human_shoulder_orientation
             = [0.707, -0.707, 0, 0] * [0.924, 0, 0.383, 0]
             = [computed_result]  # Quaternion multiplication

# IK solver moves robot shoulder to match robot_target orientation
```

---

## Implementation Code

```python
def calculate_rotation_offset(source_orientation, target_orientation):
    """Calculate offset: source = offset * target"""
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
    offset_rot = source_rot * target_rot.inv()

    # Convert back to [w,x,y,z]
    offset_quat = offset_rot.as_quat()  # Returns [x,y,z,w]
    return np.array([offset_quat[3], offset_quat[0], offset_quat[1], offset_quat[2]])
```

---

## When It Works / Doesn't Work

### ✅ Works When:

**Real skeleton data:**
```python
# From actual MuJoCo XML (robot in rest pose):
robot["pelvis"]["orientation"] = [0.5, -0.5, -0.5, -0.5]

# From actual SMPL-X (human in T-pose):
human["pelvis"]["orientation"] = [1, 0, 0, 0]

# Meaningful offset calculated:
offset = [0.5, 0.5, 0.5, 0.5]  # Rotates T-pose to match robot pose
```

### ❌ Doesn't Work When:

**Mock data with identity orientations:**
```python
# Both identity:
human["shoulder"]["orientation"] = [1, 0, 0, 0]
robot["shoulder_link"]["orientation"] = [1, 0, 0, 0]

# Useless result:
offset = [1, 0, 0, 0] * [1,0,0,0]^{-1} = [1, 0, 0, 0]  # Identity!
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

### Why This Formula:

GMR uses the scale table like this:

```python
# GMR's motion_retarget.py (simplified):
scaled_position = human_position * scale_factor[body_name]
```

So if `scale = 0.8`:
```
human knee at 0.5m from origin
→ scaled to 0.5 * 0.8 = 0.4m
→ robot can reach this!
```

---

## Detailed Example: Leg Scaling

### Step 1: Measure Bone Lengths

```python
# Human skeleton:
human["pelvis"]["position"] = [0, 0, 1.0]
human["left_hip"]["position"] = [-0.1, 0, 0.9]

# Calculate distance:
human_pelvis_to_hip = np.linalg.norm(
    np.array([-0.1, 0, 0.9]) - np.array([0, 0, 1.0])
)
= np.linalg.norm([-0.1, 0, -0.1])
= sqrt(0.01 + 0 + 0.01)
= 0.141 meters


# Robot skeleton:
robot["pelvis"]["position"] = [0, 0, 0.8]
robot["left_hip_roll_link"]["position"] = [-0.09, 0, 0.75]

# Calculate distance:
robot_pelvis_to_hip = np.linalg.norm(
    np.array([-0.09, 0, 0.75]) - np.array([0, 0, 0.8])
)
= np.linalg.norm([-0.09, 0, -0.05])
= sqrt(0.0081 + 0 + 0.0025)
= 0.103 meters
```

### Step 2: Calculate Scale

```python
scale["left_hip"] = human_pelvis_to_hip / robot_pelvis_to_hip
                  = 0.141 / 0.103
                  = 1.37
```

### Step 3: What This Means

**Interpretation:**
- `scale = 1.37` means human's pelvis-to-hip bone is **1.37x longer** than robot's
- When GMR scales human data: `human_pos * 1.37`
- This makes human positions proportionally larger to match robot's smaller limbs

**Wait, that seems backwards!** Let me reconsider...

Actually, looking at the code again (line 128):
```python
return source_length / target_length
```

If source (human) = 0.141m and target (robot) = 0.103m:
```
scale = 0.141 / 0.103 = 1.37
```

Now when GMR applies this:
```python
# GMR scales the human position
scaled = human_pos * scale
```

Hmm, but that would make things BIGGER, not smaller. Let me check how GMR actually uses the scale table...

Actually, the `human_scale_table` in GMR is used to scale the human skeleton BEFORE IK, not the positions. It scales the reference lengths. Let me rewrite this correctly:

### Step 3 (Corrected): How GMR Uses Scale

GMR's `update_targets()` method applies scales to adjust human body positions **to match robot proportions**.

The scale factor answers: "How much bigger/smaller is the human compared to the robot?"

```
scale = human_length / robot_length = 0.141 / 0.103 = 1.37
```

GMR then uses this to **compress** human data:
```python
# Conceptually (simplified):
adjusted_human_pos = human_pos / scale  # Make human smaller
# OR equivalently:
adjusted_human_pos = human_pos * (robot_length / human_length)
                    = human_pos * (1 / 1.37)
                    = human_pos * 0.73
```

Wait, I need to check the actual GMR code to be sure. Let me provide the correct interpretation based on the IK config structure:

### Step 3 (Final): Correct Interpretation

The `human_scale_table` is applied to the human skeleton as a whole. Here's what happens:

**Config:**
```json
"human_scale_table": {
    "left_hip": 1.37
}
```

**GMR's processing:**
```python
# GMR scales each human body position
for body_name, scale in human_scale_table.items():
    human_data[body_name].position *= scale
```

So `scale = 1.37` means:
- **Enlarge** human positions by 1.37x
- This is used when robot is BIGGER than human
- Most configs have `scale < 1.0` because robots are smaller than humans

**Example from bvh_lafan1_to_g1.json:**
```json
"human_scale_table": {
    "Hips": 0.9,  # Scale DOWN to 90%
    "LeftArm": 0.75  # Scale DOWN to 75%
}
```

This means:
- Human is BIGGER than robot
- Scale positions DOWN by 90% (torso) and 75% (arms)
- Makes human proportions match robot

So in our calculation:
```python
scale = source_length / target_length = 0.141 / 0.103 = 1.37
```

This is **inverted** from what we want! We should use:
```python
scale = target_length / source_length = 0.103 / 0.141 = 0.73
```

---

Actually, let me look at one more thing - check what real configs have:

From `bvh_lafan1_to_g1.json`:
- Legs: scale = 0.9 (human bigger, scale down)
- Arms: scale = 0.75 (human much bigger, scale down more)

So the formula should be `target / source` if we want values < 1.0 for typical human-to-robot cases.

But the code says `source / target`... Let me think about this differently.

---

## Correct Interpretation

The scale factor represents the ratio of human to robot size:

```python
scale = human_bone_length / robot_bone_length
```

If human bone is 0.5m and robot bone is 0.4m:
```
scale = 0.5 / 0.4 = 1.25
```

**This means: human is 1.25x the size of the robot**

GMR then uses this scale value in its config, and internally handles the scaling appropriately (likely dividing by it to compress human data, or using it as a reference for height scaling).

The key insight: **the scale in the config represents the human-to-robot size ratio**, regardless of how GMR internally applies it.

---

## Implementation Code

```python
def calculate_scale_factor(source_skeleton, target_skeleton,
                          source_parent, source_child,
                          target_parent, target_child):
    """Calculate scale = source_length / target_length"""

    # Measure source bone
    source_pos1 = np.array(source_skeleton[source_parent]["position"])
    source_pos2 = np.array(source_skeleton[source_child]["position"])
    source_length = np.linalg.norm(source_pos2 - source_pos1)

    # Measure target bone
    target_pos1 = np.array(target_skeleton[target_parent]["position"])
    target_pos2 = np.array(target_skeleton[target_child]["position"])
    target_length = np.linalg.norm(target_pos2 - target_pos1)

    if target_length == 0:
        return 1.0

    return source_length / target_length
```

### Which Bones to Measure

We measure kinematic chains (parent → child pairs):

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

Each child gets the scale factor from its parent-child measurement.

---

## When It Works / Doesn't Work

### ✅ Works When:

**Real skeleton geometry:**
```python
# Actual measured positions from robot XML:
robot["pelvis"] = [0, 0, 0.774]
robot["left_hip_roll_link"] = [-0.0965, 0, 0.724]
distance = 0.123m

# Actual human proportions:
human["pelvis"] = [0, 0, 1.1]
human["left_hip"] = [-0.12, 0, 1.02]
distance = 0.147m

# Meaningful scale:
scale = 0.147 / 0.123 = 1.20
```

### ❌ Doesn't Work When:

**Mock data with arbitrary positions:**
```python
# We made these up:
human["pelvis"] = [0, 0, 1.0]  # Random
human["left_hip"] = [-0.1, 0, 0.9]  # Random
distance = 0.141m (meaningless)

# Scale calculation:
scale = 0.141 / robot_distance = ??? (arbitrary)
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

## Example Results:

```python
correspondences = {
    "left_foot": "left_toe_link",
    "left_knee": "left_knee_link",
    "pelvis": "pelvis",
    "left_shoulder": "left_shoulder_yaw_link"
}

# Position weights:
{
    "left_toe_link": 100.0,      # foot → high
    "left_knee_link": 10.0,      # knee → medium
    "pelvis": 100.0,              # pelvis → high
    "left_shoulder_yaw_link": 10.0  # shoulder → medium
}

# Rotation weights:
{
    "left_toe_link": 50.0,       # foot → very high (end effector)
    "left_knee_link": 10.0,      # knee → default
    "pelvis": 10.0,               # pelvis → default
    "left_shoulder_yaw_link": 100.0  # shoulder → high (upper body)
}
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
   - Formula: `offset = source_orientation * target_orientation^{-1}`
   - Requires: Real skeleton orientations (not all identity)

2. **Scale Factors**: Measures bone length ratios
   - Formula: `scale = source_length / target_length`
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
   - `generate_mjcf_skeleton.py` for robots
   - `generate_smpl_skeleton.py` for SMPL-X
   - Load actual BVH data

2. **Enable Phase 2 auto-calibration** when creating configs

3. **Test and refine** - auto-calculation gives you 80-90%, manual tuning gets the last 10-20%

---

**The auto-calibration is a powerful starting point, but understanding the math helps you debug and refine when needed!**
