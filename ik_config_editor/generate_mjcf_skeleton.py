import json

import mujoco as mj


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(
        description="Generate SMPL skeleton configuration file."
    )
    parser.add_argument("xml_file", type=str, help="Path to the MuJoCo XML file.")
    parser.add_argument(
        "output_file",
        type=str,
        help="Path to save the generated skeleton configuration file.",
    )

    args = parser.parse_args()

    m = mj.MjModel.from_xml_path(args.xml_file)
    d = mj.MjData(m)
    mj.mj_forward(m, d)

    skeleton_data = {}
    for bid in range(m.nbody):
        body = m.body(bid)
        position = d.xpos[bid].tolist()
        orientation = d.xquat[bid].tolist()

        # Create a dictionary entry for the body
        skeleton_data[body.name] = (position, orientation)

    # Save the skeleton data to a JSON file
    with open(args.output_file, "w") as f:
        json.dump(skeleton_data, f, indent=4)
