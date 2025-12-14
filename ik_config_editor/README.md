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

You can either:

1. **Load MuJoCo XML directly** (recommended for robots)
2. **Pre-generate JSON skeleton files** for faster loading

To pre-generate skeleton JSON files:

```bash
# Generate robot skeleton from MuJoCo XML
python ik_config_editor/generate_mjcf_skeleton.py \
    assets/unitree_g1/unitree_g1.xml \
    test_data/g1_skeleton.json

# Generate SMPL-X skeleton from motion file
python ik_config_editor/generate_smpl_skeleton.py \
    --smplx_file path/to/motion.npz \
    --smplx_body_model_path assets/body_models/smplx \
    --output_file test_data/smplx_skeleton.json
```

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

## Limitations (Phase 1)

- Rotation offsets are identity (may need manual tuning for correct limb orientations)
- Position offsets are zero (may need adjustments for end effectors)
- Weights use defaults (may need tuning for desired IK behavior)
- Scale factors are 1.0 (may need adjustment if source/target sizes differ significantly)

Phase 2 features will include automatic offset and scale calculation.

## Architecture

```
ik_config_editor/
├── cli.py                    # Command-line entry point
├── skeleton_loader.py        # Load skeletons from various sources
├── ik_config_generator.py    # Generate IK config JSON
├── ik_config_editor_app.py   # Main GUI application
├── generate_mjcf_skeleton.py # Helper: Export MuJoCo skeleton to JSON
└── generate_smpl_skeleton.py # Helper: Export SMPL-X skeleton to JSON
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
