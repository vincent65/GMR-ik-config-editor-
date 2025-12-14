# IK Config Editor - Quick Start Guide

## Installation

The editor is already part of GMR. Ensure dependencies are installed:

```bash
conda activate gmr
pip install open3d  # Already done
```

## Quick Test (5 minutes)

### 1. Generate Test Skeletons

```bash
# Create mock skeletons for testing
python ik_config_editor/create_test_skeletons.py
```

### 2. Launch the Editor

```bash
# Option A: Launch with pre-loaded skeletons (recommended for first try)
python -m ik_config_editor.cli \
    --source test_data/smplx_skeleton.json \
    --target test_data/g1_skeleton.json

# Option B: Launch empty and load via GUI
python -m ik_config_editor.cli
```

### 3. In the GUI

1. **Verify skeletons loaded**: You should see two 3D views with coordinate frames
2. **Scroll down** to "Body Correspondences" section
3. **Map a few bodies** using the dropdowns:
   - `pelvis` → `pelvis`
   - `left_hip` → `left_hip_roll_link`
   - `left_knee` → `left_knee_link`
   - `left_foot` → `left_toe_link`
   (and same for right side)
4. **Optional**: Enable Phase 2 features:
   - ☑ Auto-calculate rotation offsets
   - ☑ Auto-calculate scale factors
   - ☑ Auto-suggest IK weights
5. **Click "Export IK Config"**
6. **Save** as `test_data/my_first_config.json`

### 4. Verify the Config

```bash
# Run validation test
python -c "
import json
with open('test_data/my_first_config.json', 'r') as f:
    config = json.load(f)
print(f'✓ Config loaded successfully')
print(f'✓ Mappings: {len(config[\"ik_match_table1\"])}')
"
```

**Expected output:**
```
✓ Config loaded successfully
✓ Mappings: 8
```

---

## Real Usage (Creating Configs for Actual Robots)

### Scenario: Create config for retargeting SMPL-X to Unitree G1

#### Step 1: Generate SMPL-X Skeleton

You'll need an SMPL-X motion file (`.npz`). If you don't have one, you can create a skeleton from rest pose:

```bash
# This requires fixing the MuJoCo x86/ARM issue first
# Or use an existing SMPL-X skeleton if available
```

#### Step 2: Generate G1 Skeleton from MuJoCo Model

```bash
python ik_config_editor/generate_mjcf_skeleton.py \
    assets/unitree_g1/unitree_g1.xml \
    ik_config_editor/skeletons/g1_skeleton.json
```

#### Step 3: Launch Editor

```bash
python -m ik_config_editor.cli \
    --source ik_config_editor/skeletons/smplx_skeleton.json \
    --target ik_config_editor/skeletons/g1_skeleton.json
```

#### Step 4: Create Mappings

Reference the existing config at `general_motion_retargeting/ik_configs/smplx_to_g1.json` to see which bodies should map to which.

Example mappings (14 total):

| SMPL-X Source | Unitree G1 Target |
|---------------|-------------------|
| pelvis | pelvis |
| spine3 | torso_link |
| left_hip | left_hip_roll_link |
| left_knee | left_knee_link |
| left_foot | left_toe_link |
| right_hip | right_hip_roll_link |
| right_knee | right_knee_link |
| right_foot | right_toe_link |
| left_shoulder | left_shoulder_yaw_link |
| left_elbow | left_elbow_link |
| left_wrist | left_wrist_yaw_link |
| right_shoulder | right_shoulder_yaw_link |
| right_elbow | right_elbow_link |
| right_wrist | right_wrist_yaw_link |

#### Step 5: Configure Settings

- **Robot Root**: `pelvis`
- **Human Root**: `pelvis`
- **Human Height**: `1.8`

#### Step 6: Enable Phase 2 (Recommended)

- ☑ Auto-calculate rotation offsets
- ☑ Auto-calculate scale factors
- ☑ Auto-suggest IK weights

#### Step 7: Export and Test

1. Export to `general_motion_retargeting/ik_configs/smplx_to_g1_custom.json`
2. Test with GMR:

```bash
# First, add to params.py:
# IK_CONFIG_DICT[("smplx", "unitree_g1_custom")] = "general_motion_retargeting/ik_configs/smplx_to_g1_custom.json"

# Then run retargeting (requires SMPL-X motion file):
python scripts/smplx_to_robot.py \
    --smplx_file path/to/motion.npz \
    --robot unitree_g1_custom \
    --visualize
```

---

## Tips for Best Results

### Phase 1 (Manual)
- Start with the pelvis (root body) first
- Map symmetric bodies together (left + right)
- End effectors (feet, hands) are most important for grounding
- You can leave some bodies unmapped if not needed

### Phase 2 (Automatic)
- **Always enable** if you want better initial results
- Rotation offsets help with limb orientation mismatches
- Scale factors are critical when source/target have different proportions
- Weight suggestions help prioritize important joints (feet, pelvis)

### Troubleshooting
- **Skeleton not visible?** Rotate the view with left-click drag
- **Can't load XML?** Ensure it's a valid MuJoCo MJCF file
- **Configs don't work in GMR?** Check that robot XML path matches `ROBOT_XML_DICT` in `params.py`
- **Motion looks wrong?** You may need to manually tune rotation offsets in the JSON

---

## GUI Controls

| Action | Control |
|--------|---------|
| Rotate view | Left-click + drag |
| Pan view | Right-click + drag |
| Zoom | Scroll wheel |
| Reset mapping | Set dropdown to empty option |

---

## Next Steps

After creating your first config:

1. **Test with real motion data**: Run retargeting and visualize results
2. **Refine manually**: Edit the JSON to fine-tune weights and offsets
3. **Compare with existing configs**: Look at `ik_configs/` for reference values
4. **Iterate**: Adjust, test, repeat until motion quality is satisfactory

---

## Common Workflows

### Workflow 1: New Robot, Human Source
```bash
generate_mjcf_skeleton.py <robot.xml> <robot_skeleton.json>
# Use existing SMPL-X skeleton
cli.py --source smplx_skeleton.json --target robot_skeleton.json
# Map bodies, enable Phase 2, export
```

### Workflow 2: Robot-to-Robot Retargeting
```bash
generate_mjcf_skeleton.py <source_robot.xml> <source.json>
generate_mjcf_skeleton.py <target_robot.xml> <target.json>
cli.py --source source.json --target target.json
# Map bodies, enable Phase 2, export
```

### Workflow 3: Quick Iteration
```bash
# Edit existing config manually
# Test in GMR
# If issues, reload in editor and adjust
```

---

## Keyboard Shortcuts

Currently none implemented, but you can:
- Tab through fields
- Use dropdowns with mouse
- Type in text fields

---

## Getting Help

- Check `README.md` for detailed documentation
- See `IMPLEMENTATION_SUMMARY.md` for technical details
- Look at existing configs in `general_motion_retargeting/ik_configs/` for examples
- Run tests to verify installation: `python ik_config_editor/test_basic.py`

---

**Happy Retargeting! 🤖**
