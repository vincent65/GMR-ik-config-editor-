# IK Config Editor

Interactive GUI tool for creating IK configuration files for GMR (General Motion Retargeting).

## Overview

The IK Config Editor allows you to visually map body correspondences between a source skeleton (human/robot) and a target robot, then export a GMR-compatible IK configuration JSON file.

## Features

- **Dual-pane 3D visualization**: View source and target skeletons side-by-side
- **Interactive correspondence mapping**: Use dropdowns to map source bodies to target bodies
- **Multiple input formats**: Load skeletons from JSON or MuJoCo XML files
- **GMR-compatible output**: Export IK configs ready to use with GMR retargeting

## Installation

The editor is part of the GMR package. Ensure you have the required dependencies:

```bash
pip install open3d mujoco
```

## Usage

### Quick Start

```bash
# Launch empty editor (load files via GUI)
python -m ik_config_editor.cli

# Pre-load skeletons from command line
python -m ik_config_editor.cli \
    --source test_data/smplx_skeleton.json \
    --target test_data/g1_skeleton.json
```

### Preparing Skeleton Files

You can load skeletons from:

1. **MuJoCo XML files** (recommended for robots) - loaded directly via the GUI or CLI
2. **JSON skeleton files** - pre-extracted skeleton data
3. **Robot T-pose JSON files** - with joint angles, requires the robot XML for forward kinematics

For robot-to-robot retargeting, see `ROBOT_TO_ROBOT_GUIDE.md`.

### Workflow

1. **Load Skeletons**
   - Click "Load Source Skeleton" and select your source skeleton file
   - Click "Load Target Skeleton" and select your target robot file
   - Both skeletons will appear in the 3D viewers

2. **Create Body Correspondences**
   - For each source body in the table, select the corresponding target body from the dropdown
   - Leave dropdown empty to skip unmapped bodies
   - Correspondences are saved automatically

3. **Configure Metadata**
   - Set "Robot Root" to the target robot's root body name (usually "pelvis")
   - Set "Human Root" to the source skeleton's root body name
   - Set "Human Height" to the assumed height in meters (default: 1.8)

4. **Export Configuration**
   - Click "Export IK Config"
   - Choose save location (e.g., `my_ik_config.json`)
   - The generated config is ready to use with GMR

### Mouse Controls

- **Left drag**: Rotate view
- **Right drag**: Pan view
- **Scroll**: Zoom in/out

## Generated Config Format

The tool generates IK configuration files with this structure:

```json
{
    "robot_root_name": "pelvis",
    "human_root_name": "pelvis",
    "ground_height": 0.0,
    "human_height_assumption": 1.8,
    "use_ik_match_table1": true,
    "use_ik_match_table2": true,
    "human_scale_table": {
        "pelvis": 1.0,
        ...
    },
    "ik_match_table1": {
        "target_body": ["source_body", 0, 10, [0,0,0], [1,0,0,0]],
        ...
    },
    "ik_match_table2": { ... }
}
```

**Note**: The initial config uses default values:
- Position weight: 0 (disabled for most joints)
- Rotation weight: 10
- Position offset: [0, 0, 0]
- Rotation offset: [1, 0, 0, 0] (identity quaternion)
- Scale: 1.0 for all bodies

You may need to manually tune these values or use Phase 2 features (automatic offset calculation) for better retargeting quality.

## Testing the Generated Config

To test your generated IK config with GMR:

1. **Add config to params.py** (temporary):
```python
# In general_motion_retargeting/params.py
IK_CONFIG_DICT = {
    # ... existing configs ...
    ("smplx", "my_robot"): "path/to/my_ik_config.json",
}
```

2. **Run retargeting**:
```bash
python scripts/smplx_to_robot.py \
    --smplx_file path/to/motion.npz \
    --robot my_robot \
    --visualize \
    --save_path output/test_motion.pkl
```

3. **Verify**: Robot should move (even if imperfectly due to untuned offsets)

## Automatic Calibration (Phase 2)

Enable these options in the GUI for better initial results:

- **☑ Auto-calculate rotation offsets**: Computes quaternion offsets using `q_offset = q_source^(-1) * q_target`
- **☑ Auto-calculate scale factors**: Measures bone lengths and computes scaling ratios
- **☑ Auto-suggest IK weights**: Sets appropriate position/rotation weights based on body type

Without auto-calibration:
- Rotation offsets default to identity (may need manual tuning)
- Scale factors default to 1.0
- Weights use simple defaults

## Architecture

```
ik_config_editor/
├── cli.py                    # Command-line entry point
├── skeleton_loader.py        # Load skeletons from various sources
├── ik_config_generator.py    # Generate IK config JSON
├── ik_config_editor_app.py   # Main GUI application
├── auto_calibration.py       # Automatic rotation/scale calculation
├── test_ik_config_quality.py # Validate generated IK configs
└── validate_ik_config.py     # Config validation utilities
```

## Troubleshooting

**"Failed to load source/target skeleton"**
- Ensure file path is correct
- For MuJoCo XML, verify the file is a valid MJCF format
- For JSON, ensure it was generated by the skeleton export scripts

**"Please create at least one body correspondence"**
- Map at least one source body to a target body before exporting

**Empty 3D view**
- Try adjusting the view with mouse controls
- Check that the skeleton file loaded successfully (look for console messages)
