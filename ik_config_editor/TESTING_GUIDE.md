# IK Config Testing Guide

## How to Verify Your IK Config is Correct

This guide explains multiple ways to test if your generated IK configuration will work correctly with GMR.

---

## Quick Validation (2 minutes)

### Option 1: Automated Test Script

Run the validation script:

```bash
python ik_config_editor/test_ik_config_quality.py --config path/to/your_config.json
```

**What it checks:**
- ✓ JSON structure is valid
- ✓ All required fields present
- ✓ Entry formats are correct (5 elements per entry)
- ✓ Quaternions are valid (unit norm)
- ✓ Weights make sense (feet have high position weights)
- ✓ Scale factors are reasonable

**Example output:**
```
======================================================================
TEST 1: Structure Validation
======================================================================
✓ All required keys present
  - Robot root: pelvis
  - Human root: pelvis
  - Ground height: 0.0
  - Human height: 1.8
  - Scale entries: 14
  - Table1 entries: 14
  - Table2 entries: 14

======================================================================
TEST 2: Entry Format Validation
======================================================================
✓ All entries have correct format

======================================================================
TEST 3: Weight Analysis
======================================================================
⚠ WARNING: Feet have low position weights:
  - left_toe_link: pos_weight = 0.0 (recommend >= 100)
  - right_toe_link: pos_weight = 0.0 (recommend >= 100)

...

======================================================================
TEST SUMMARY
======================================================================
✅ CONFIG IS VALID AND READY TO USE!
   (Some warnings - may want to review)
```

### Option 2: Compare with Reference Config

```bash
python ik_config_editor/test_ik_config_quality.py \
    --config test_data/test_ik_config.json \
    --reference general_motion_retargeting/ik_configs/smplx_to_g1.json
```

This shows:
- How many mappings you have vs. reference
- Which bodies are missing or extra
- Side-by-side comparison of sample entries

---

## Full Integration Test (10-20 minutes)

### Prerequisites

You need:
1. Your generated IK config
2. A test motion file (SMPL-X `.npz` or BVH `.bvh`)
3. The robot XML file

### Step 1: Add Config to GMR

Edit `general_motion_retargeting/params.py`:

```python
# Add to IK_CONFIG_DICT
IK_CONFIG_DICT = {
    # ... existing configs ...
    ("smplx", "my_robot_test"): "path/to/your_config.json",
}

# Make sure robot XML is in ROBOT_XML_DICT
ROBOT_XML_DICT = {
    # ... existing robots ...
    "my_robot_test": "assets/your_robot/your_robot.xml",
}

# Add robot base if needed
ROBOT_BASE_DICT = {
    # ... existing bases ...
    "my_robot_test": "pelvis",  # or whatever your root is
}
```

### Step 2: Run Retargeting

```bash
python scripts/smplx_to_robot.py \
    --smplx_file path/to/test_motion.npz \
    --robot my_robot_test \
    --visualize \
    --save_path test_output/retargeted.pkl
```

**Or for BVH:**
```bash
python scripts/bvh_to_robot.py \
    --bvh_file path/to/test_motion.bvh \
    --robot my_robot_test \
    --format lafan1 \
    --visualize \
    --save_path test_output/retargeted.pkl
```

### Step 3: What to Look For

#### ✅ **GOOD SIGNS**:

1. **Script runs without errors**
   ```
   Loading config...
   Retargeting frame 0/100
   Retargeting frame 1/100
   ...
   ✓ Saved to test_output/retargeted.pkl
   ```

2. **Visualization shows reasonable motion**
   - Robot moves smoothly (not jerky)
   - Limbs point in correct directions (arms are arms, legs are legs)
   - No extreme distortions

3. **Feet touch the ground**
   - During standing/walking, feet make contact
   - No floating or sinking

4. **Joint angles look natural**
   - Elbows bend the right way
   - Knees bend forward, not backward
   - No limbs folded backwards

5. **Console shows low IK errors**
   ```
   Frame 50: IK error = 0.002  # Good!
   ```

#### ❌ **BAD SIGNS**:

1. **Errors during execution**
   ```
   KeyError: 'some_body_name'  # Missing mapping
   ValueError: invalid quaternion  # Bad rotation offset
   ```

2. **Robot explodes or distorts**
   - Limbs at extreme angles
   - Body parts separated
   - NaN values in output

3. **Feet float off ground**
   ```
   # Your config probably has:
   "left_toe_link": [..., 0, ...]  # position weight = 0 ❌

   # Should be:
   "left_toe_link": [..., 100, ...]  # position weight = 100 ✓
   ```

4. **Limbs point wrong direction**
   ```
   # Rotation offsets might be wrong
   # Try enabling auto-calibration or manually tune offsets
   ```

5. **Motion looks scaled incorrectly**
   - Robot reaches too far or not far enough
   - Proportions look wrong
   ```
   # Scale factors might be wrong
   # Enable auto-scale calculation
   ```

---

## Common Issues & Fixes

### Issue 1: "Feet are floating"

**Diagnosis:**
```bash
python ik_config_editor/test_ik_config_quality.py --config your_config.json
```
Output:
```
⚠ WARNING: Feet have low position weights:
  - left_toe_link: pos_weight = 0.0 (recommend >= 100)
```

**Fix:**
Edit your config JSON:
```json
"left_toe_link": [
    "left_foot",
    100,  // Change from 0 to 100 ← FIX HERE
    10,
    [0, 0, 0],
    [1, 0, 0, 0]
]
```

Or regenerate with Phase 2 auto-weights enabled.

---

### Issue 2: "Limbs point wrong direction (arms twisted)"

**Diagnosis:** Rotation offsets are identity or incorrect

**Fix Option A:** Use Phase 2 auto-calibration
- Launch editor, check ☑ Auto-calculate rotation offsets
- Re-export config

**Fix Option B:** Manually adjust rotation offset

Example: If left arm is rotated 90° wrong:
```json
"left_shoulder_yaw_link": [
    "left_shoulder",
    0,
    10,
    [0, 0, 0],
    [0.707, 0, 0, 0.707]  // 90° rotation around X-axis ← FIX HERE
]
```

Use this helper to calculate quaternions:
```python
from scipy.spatial.transform import Rotation as R
import numpy as np

# 90 degrees around X-axis
rot = R.from_euler('x', 90, degrees=True)
quat = rot.as_quat()  # Returns [x, y, z, w]
quat_wxyz = [quat[3], quat[0], quat[1], quat[2]]  # Convert to [w,x,y,z]
print(quat_wxyz)  # [0.707, 0.707, 0, 0]
```

---

### Issue 3: "Robot reaches too far / not far enough"

**Diagnosis:** Scale factors are wrong (all 1.0)

**Fix:** Enable Phase 2 auto-scale
- Regenerate config with ☑ Auto-calculate scale factors checked

Or manually adjust `human_scale_table`:
```json
"human_scale_table": {
    "left_hip": 0.8,   // If robot's hip is 80% of human's
    "left_knee": 0.85,
    ...
}
```

---

### Issue 4: "Config loads but robot doesn't move at all"

**Diagnosis:** Check console for errors

Common causes:
1. **Body name mismatch**
   ```
   KeyError: 'left_hip'  # Human body not in motion file
   ```
   Fix: Check your source skeleton has the bodies you mapped

2. **Robot body doesn't exist**
   ```
   KeyError: 'left_hip_roll_link'  # Robot body not in XML
   ```
   Fix: Verify robot body names match the XML file exactly

3. **All weights are zero**
   ```
   # Config has all position and rotation weights = 0
   ```
   Fix: Set reasonable weights (use Phase 2 auto-weights)

---

### Issue 5: "Motion looks jittery/unstable"

**Possible causes:**
1. **Conflicting IK targets** - Too many high-weight bodies fighting each other
2. **Under-constrained** - Not enough important bodies tracked
3. **Bad rotation offsets** - Causing IK solver to oscillate

**Fixes:**
1. Reduce rotation weights in `ik_match_table2` (make them 50% of table1)
2. Ensure critical bodies (pelvis, feet) have high weights
3. Re-calculate rotation offsets with auto-calibration

---

## Visual Checklist

When you run visualization (`--visualize`), check:

```
☐ Script runs without Python errors
☐ Visualization window opens
☐ Robot appears (not empty scene)
☐ Robot moves when you play the motion
☐ Limb orientations look correct:
    ☐ Arms extend sideways (not forward/back)
    ☐ Legs point down
    ☐ Head points up
☐ During standing:
    ☐ Feet on ground
    ☐ Pelvis at reasonable height
    ☐ Upper body upright
☐ During walking:
    ☐ Feet alternate contact with ground
    ☐ Knees bend forward
    ☐ Arms swing naturally
☐ No extreme angles:
    ☐ Joints within reasonable limits
    ☐ No limbs bent backwards
    ☐ No body parts separated
```

---

## Quantitative Metrics

### Good IK Config Metrics:

1. **IK Error**: Should be < 0.01 for most frames
   ```
   # You'll see in console:
   Frame 100: error=0.003  # GOOD
   Frame 101: error=0.156  # BAD - something's wrong
   ```

2. **Joint Limits**: No warnings about joint limits
   ```
   # BAD:
   Warning: left_knee at limit (-0.1 rad)
   ```

3. **Position Weights**:
   - Feet: >= 100
   - Pelvis: >= 50
   - Most others: 0-10

4. **Rotation Weights**:
   - All bodies: 5-100
   - End effectors (feet, hands): 50-100
   - Torso/shoulders: 50-100

5. **Scale Factors**:
   - Should be in range [0.5, 2.0] typically
   - Large variations (>2x) are suspicious

---

## Advanced: Compare Frame-by-Frame

If motion looks wrong but you're not sure why:

```python
# Load your retargeted motion
import pickle
with open('test_output/retargeted.pkl', 'rb') as f:
    data = pickle.load(f)

root_pos = data['root_pos']  # Shape: (num_frames, 3)
root_rot = data['root_rot']  # Shape: (num_frames, 4)
dof_pos = data['dof_pos']    # Shape: (num_frames, num_joints)

# Check for NaN or extreme values
import numpy as np
print("NaN values:", np.isnan(dof_pos).sum())
print("Joint angle range:", dof_pos.min(), dof_pos.max())
print("Root height range:", root_pos[:, 2].min(), root_pos[:, 2].max())

# Bad signs:
# - NaN values (IK failed)
# - Joint angles > 3.14 or < -3.14 (unrealistic)
# - Root height < 0 (sinking) or > 3 (flying)
```

---

## Summary: Testing Workflow

```
1. Generate config in editor
   ↓
2. Run test_ik_config_quality.py
   ↓ (if errors) → Fix config
   ↓ (if valid)
3. Add to params.py
   ↓
4. Run retargeting with --visualize
   ↓
5. Check visual quality
   ├─ Good? → Done! ✓
   └─ Issues? → Diagnose and iterate
         ↓
         Regenerate with different Phase 2 settings
         or manually tune problematic entries
```

---

## Getting Help

If you're stuck:

1. **Run diagnostics:**
   ```bash
   python ik_config_editor/test_ik_config_quality.py --config your.json --reference general_motion_retargeting/ik_configs/smplx_to_g1.json
   ```

2. **Compare with working config**: Open a known-good config (e.g., `smplx_to_g1.json`) and compare values

3. **Check specific body**: Look at how reference configs handle similar bodies

4. **Enable all Phase 2 features**: Sometimes auto-calibration finds issues you missed

---

**Remember**: Even "correct" configs may need manual tuning for best results. Start with Phase 2 auto-calibration, then refine!
