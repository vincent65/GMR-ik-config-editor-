import json

from general_motion_retargeting.utils.smpl import load_smplx_file, get_smplx_data


def generate_smpl_skeleton(smplx_file, smplx_body_model_path, output_file):
    # Load SMPL-X data and model
    smplx_data, body_model, smplx_output, human_height = load_smplx_file(
        smplx_file, smplx_body_model_path
    )

    # Get joint positions and orientations for the rest pose
    smplx_output = body_model(return_full_pose=True)
    smplx_output.global_orient = smplx_output.global_orient.detach()
    smplx_output.full_pose = smplx_output.full_pose.detach()
    skeleton_data = get_smplx_data(smplx_data, body_model, smplx_output, curr_frame=0)

    # For each element in the skeleton data, convert the numpy arrays to lists
    for joint, (position, orientation) in skeleton_data.items():
        skeleton_data[joint] = (position.tolist(), orientation.tolist())

    # Save the skeleton data to a JSON file
    with open(output_file, "w") as f:
        json.dump(skeleton_data, f, indent=4)

    print(f"Skeleton configuration saved to {output_file}")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(
        description="Generate SMPL skeleton configuration file."
    )
    parser.add_argument(
        "--smplx_file", type=str, required=True, help="Path to the SMPL-X file."
    )
    parser.add_argument(
        "--smplx_body_model_path",
        type=str,
        required=True,
        help="Path to the SMPL-X body model directory.",
    )
    parser.add_argument(
        "--output_file",
        type=str,
        required=True,
        help="Path to save the generated skeleton configuration file.",
    )

    args = parser.parse_args()

    generate_smpl_skeleton(
        args.smplx_file, args.smplx_body_model_path, args.output_file
    )
