"""Main GUI application for IK Config Editor."""

import json
import os
import numpy as np

import open3d as o3d
import open3d.visualization.gui as gui
import open3d.visualization.rendering as rendering

from ik_config_editor.skeleton_loader import SkeletonLoader
from ik_config_editor.ik_config_generator import IKConfigGenerator


class IKConfigEditorApp:
    """Interactive GUI application for creating IK configuration files."""

    def __init__(self, source_path=None, target_path=None, source_type="auto", target_type="auto",
                 source_xml_path=None, target_xml_path=None):
        """Initialize the IK Config Editor application.

        Args:
            source_path: Optional path to source skeleton
            target_path: Optional path to target skeleton
            source_type: Type of source skeleton ("json", "mjcf", "robot_pose", "auto")
            target_type: Type of target skeleton ("json", "mjcf", "robot_pose", "auto")
            source_xml_path: Optional path to source robot XML (for robot_pose type)
            target_xml_path: Optional path to target robot XML (for robot_pose type)
        """
        # Initialize Open3D application
        self.app = gui.Application.instance
        self.app.initialize()

        # Create main window
        self.window = self.app.create_window("IK Config Editor", 1400, 900)

        # Create 3D scene widgets
        self.src_scene = gui.SceneWidget()
        self.src_scene.scene = rendering.Open3DScene(self.window.renderer)
        self.window.add_child(self.src_scene)

        self.tgt_scene = gui.SceneWidget()
        self.tgt_scene.scene = rendering.Open3DScene(self.window.renderer)
        self.window.add_child(self.tgt_scene)

        # Create control panel with scrolling
        em = self.window.theme.font_size
        self.panel = gui.ScrollableVert(0, gui.Margins(em, em, em, em))

        # Data storage
        self.source_skeleton = None
        self.target_skeleton = None
        self.correspondences = {}
        self.robot_root_name = "pelvis"
        self.human_root_name = "pelvis"
        self.human_height_assumption = 1.8

        # XML paths for robot pose files
        self.source_xml_path = source_xml_path
        self.target_xml_path = target_xml_path

        # Phase 2 features
        self.auto_calculate_offsets = False
        self.auto_calculate_scales = False
        self.auto_suggest_weights = False
        self.use_height_scaling = True
        self.use_limb_scaling = True

        # Create UI
        self._create_ui()
        self.window.add_child(self.panel)

        # Set layout callback
        self.window.set_on_layout(self._on_layout)

        # Load skeletons if provided
        if source_path:
            self._load_source_skeleton_from_path(source_path, source_type)
        if target_path:
            self._load_target_skeleton_from_path(target_path, target_type)

    def _on_layout(self, layout_context):
        """Handle window layout."""
        r = self.window.content_rect
        panel_width = 450

        # Left scene (source)
        self.src_scene.frame = gui.Rect(0, 0, (r.width - panel_width) // 2, r.height)
        # Right scene (target)
        self.tgt_scene.frame = gui.Rect(
            (r.width - panel_width) // 2, 0, (r.width - panel_width) // 2, r.height
        )
        # Control panel on the right
        self.panel.frame = gui.Rect(r.width - panel_width, 0, panel_width, r.height)

    def _create_ui(self):
        """Create the user interface."""
        em = self.window.theme.font_size

        # Title
        title = gui.Label("IK Config Editor")
        title.text_color = gui.Color(1, 1, 1)
        self.panel.add_child(title)
        self.panel.add_fixed(em * 0.5)

        # Load buttons
        load_section = gui.CollapsableVert("Load Skeletons", em * 0.5, gui.Margins(em, 0, 0, 0))

        self.load_source_button = gui.Button("Load Source Skeleton")
        self.load_source_button.set_on_clicked(self._on_load_source_clicked)
        load_section.add_child(self.load_source_button)

        self.load_target_button = gui.Button("Load Target Skeleton")
        self.load_target_button.set_on_clicked(self._on_load_target_clicked)
        load_section.add_child(self.load_target_button)

        self.panel.add_child(load_section)
        self.panel.add_fixed(em * 0.5)

        # Root configuration section
        root_section = gui.CollapsableVert("Root Configuration", em * 0.5, gui.Margins(em, 0, 0, 0))

        # Target robot root name
        robot_root_layout = gui.Horiz()
        robot_root_layout.add_child(gui.Label("Target Root:"))
        self.robot_root_edit = gui.TextEdit()
        self.robot_root_edit.text_value = self.robot_root_name
        self.robot_root_edit.set_on_text_changed(self._on_robot_root_changed)
        robot_root_layout.add_child(self.robot_root_edit)
        root_section.add_child(robot_root_layout)

        # Source root name
        source_root_layout = gui.Horiz()
        source_root_layout.add_child(gui.Label("Source Root:"))
        self.human_root_edit = gui.TextEdit()
        self.human_root_edit.text_value = self.human_root_name
        self.human_root_edit.set_on_text_changed(self._on_human_root_changed)
        source_root_layout.add_child(self.human_root_edit)
        root_section.add_child(source_root_layout)

        # Source height (reference)
        height_layout = gui.Horiz()
        height_layout.add_child(gui.Label("Source Height (m):"))
        self.height_edit = gui.TextEdit()
        self.height_edit.text_value = str(self.human_height_assumption)
        self.height_edit.set_on_text_changed(self._on_height_changed)
        height_layout.add_child(self.height_edit)
        root_section.add_child(height_layout)

        self.panel.add_child(root_section)
        self.panel.add_fixed(em * 0.5)

        # Automatic calibration section (Phase 2)
        auto_section = gui.CollapsableVert("Automatic Calibration", em * 0.5, gui.Margins(em, 0, 0, 0))

        # Checkbox for auto rotation offsets
        self.auto_offsets_checkbox = gui.Checkbox("Auto-calculate rotation offsets")
        self.auto_offsets_checkbox.set_on_checked(self._on_auto_offsets_changed)
        auto_section.add_child(self.auto_offsets_checkbox)

        # Checkbox for auto scales
        self.auto_scales_checkbox = gui.Checkbox("Auto-calculate scale factors")
        self.auto_scales_checkbox.set_on_checked(self._on_auto_scales_changed)
        auto_section.add_child(self.auto_scales_checkbox)

        # Checkbox for auto weights
        self.auto_weights_checkbox = gui.Checkbox("Auto-suggest IK weights")
        self.auto_weights_checkbox.set_on_checked(self._on_auto_weights_changed)
        auto_section.add_child(self.auto_weights_checkbox)

        # Checkbox for height-based scaling
        self.height_scaling_checkbox = gui.Checkbox("Use height-based scaling")
        self.height_scaling_checkbox.checked = self.use_height_scaling
        self.height_scaling_checkbox.set_on_checked(self._on_height_scaling_changed)
        auto_section.add_child(self.height_scaling_checkbox)

        # Checkbox for limb scaling
        self.limb_scaling_checkbox = gui.Checkbox("Use per-limb scaling adjustments")
        self.limb_scaling_checkbox.checked = self.use_limb_scaling
        self.limb_scaling_checkbox.set_on_checked(self._on_limb_scaling_changed)
        auto_section.add_child(self.limb_scaling_checkbox)

        self.panel.add_child(auto_section)
        self.panel.add_fixed(em * 0.5)

        # Correspondences section
        corr_section = gui.CollapsableVert("Body Correspondences", em * 0.5, gui.Margins(em, 0, 0, 0))
        corr_section.set_is_open(True)

        # Placeholder for correspondence table (will be updated dynamically)
        # Note: No inner scroll needed since panel itself is scrollable
        self.correspondence_table_proxy = gui.WidgetProxy()
        corr_section.add_child(self.correspondence_table_proxy)

        self.panel.add_child(corr_section)
        self.panel.add_fixed(em * 0.5)

        # Export button
        self.export_button = gui.Button("Export IK Config")
        self.export_button.set_on_clicked(self._on_export_clicked)
        self.panel.add_child(self.export_button)

        # Instructions
        self.panel.add_fixed(em)
        instructions_label = gui.Label("Instructions:")
        self.panel.add_child(instructions_label)

        instructions = [
            "1. Load source and target skeletons",
            "2. Map source bodies to target bodies",
            "3. Configure root names and height",
            "4. Export IK configuration",
            "",
            "Mouse controls:",
            "  • Left drag: rotate view",
            "  • Right drag: pan view",
            "  • Scroll: zoom",
        ]

        for instruction in instructions:
            inst_label = gui.Label(instruction)
            inst_label.text_color = gui.Color(0.7, 0.7, 0.7)
            self.panel.add_child(inst_label)

    def _on_robot_root_changed(self, text):
        """Handle robot root name change."""
        self.robot_root_name = text

    def _on_human_root_changed(self, text):
        """Handle human root name change."""
        self.human_root_name = text

    def _on_height_changed(self, text):
        """Handle human height change."""
        try:
            self.human_height_assumption = float(text)
        except ValueError:
            pass  # Ignore invalid input

    def _on_auto_offsets_changed(self, checked):
        """Handle auto-calculate offsets checkbox change."""
        self.auto_calculate_offsets = checked

    def _on_auto_scales_changed(self, checked):
        """Handle auto-calculate scales checkbox change."""
        self.auto_calculate_scales = checked

    def _on_auto_weights_changed(self, checked):
        """Handle auto-suggest weights checkbox change."""
        self.auto_suggest_weights = checked

    def _on_height_scaling_changed(self, checked):
        """Handle height scaling checkbox change."""
        self.use_height_scaling = checked

    def _on_limb_scaling_changed(self, checked):
        """Handle limb scaling checkbox change."""
        self.use_limb_scaling = checked

    def _on_load_source_clicked(self):
        """Handle load source button click."""
        filedlg = gui.FileDialog(gui.FileDialog.Mode.OPEN, "Load Source Skeleton", self.window.theme)
        filedlg.add_filter(".json", "JSON skeleton files")
        filedlg.add_filter(".xml", "MuJoCo XML files")
        filedlg.add_filter("", "All files")
        filedlg.set_on_cancel(self._on_file_dialog_cancel)
        filedlg.set_on_done(self._on_source_skeleton_loaded)
        self.window.show_dialog(filedlg)

    def _on_load_target_clicked(self):
        """Handle load target button click."""
        filedlg = gui.FileDialog(gui.FileDialog.Mode.OPEN, "Load Target Skeleton", self.window.theme)
        filedlg.add_filter(".json", "JSON skeleton files")
        filedlg.add_filter(".xml", "MuJoCo XML files")
        filedlg.add_filter("", "All files")
        filedlg.set_on_cancel(self._on_file_dialog_cancel)
        filedlg.set_on_done(self._on_target_skeleton_loaded)
        self.window.show_dialog(filedlg)

    def _on_file_dialog_cancel(self):
        """Handle file dialog cancel."""
        self.window.close_dialog()

    def _on_source_skeleton_loaded(self, path):
        """Handle source skeleton loaded from file dialog."""
        self.window.close_dialog()
        self._load_source_skeleton_from_path(path, "auto")

    def _on_target_skeleton_loaded(self, path):
        """Handle target skeleton loaded from file dialog."""
        self.window.close_dialog()
        self._load_target_skeleton_from_path(path, "auto")

    def _load_source_skeleton_from_path(self, path, skeleton_type="auto"):
        """Load source skeleton from file path."""
        if os.path.exists(path):
            try:
                # Check if this is a robot pose JSON that needs XML path
                needs_xml = False
                if path.endswith('.json') and skeleton_type == "auto":
                    with open(path, 'r') as f:
                        data = json.load(f)
                    if "joint_angles" in data:
                        needs_xml = True

                if needs_xml:
                    # If XML path was provided, use it; otherwise prompt
                    if self.source_xml_path:
                        self.source_skeleton = SkeletonLoader.load(
                            path, skeleton_type="robot_pose", robot_xml_path=self.source_xml_path
                        )
                        print(f"Loaded source skeleton from robot pose: {len(self.source_skeleton)} bodies")
                        self._update_src_scene()
                        self._update_correspondence_table()
                    else:
                        # Prompt for XML file
                        self._prompt_for_source_xml(path)
                else:
                    # Load directly
                    self.source_skeleton = SkeletonLoader.load(path, skeleton_type)
                    print(f"Loaded source skeleton: {len(self.source_skeleton)} bodies")
                    self._update_src_scene()
                    self._update_correspondence_table()
            except Exception as e:
                print(f"Error loading source skeleton: {e}")
                # Show error dialog
                self._show_error_dialog(f"Failed to load source skeleton:\n{str(e)}")

    def _load_target_skeleton_from_path(self, path, skeleton_type="auto"):
        """Load target skeleton from file path."""
        if os.path.exists(path):
            try:
                # Check if this is a robot pose JSON that needs XML path
                needs_xml = False
                if path.endswith('.json') and skeleton_type == "auto":
                    with open(path, 'r') as f:
                        data = json.load(f)
                    if "joint_angles" in data:
                        needs_xml = True

                if needs_xml:
                    # If XML path was provided, use it; otherwise prompt
                    if self.target_xml_path:
                        self.target_skeleton = SkeletonLoader.load(
                            path, skeleton_type="robot_pose", robot_xml_path=self.target_xml_path
                        )
                        print(f"Loaded target skeleton from robot pose: {len(self.target_skeleton)} bodies")
                        self._update_tgt_scene()
                        self._update_correspondence_table()
                    else:
                        # Prompt for XML file
                        self._prompt_for_target_xml(path)
                else:
                    # Load directly
                    self.target_skeleton = SkeletonLoader.load(path, skeleton_type)
                    print(f"Loaded target skeleton: {len(self.target_skeleton)} bodies")
                    self._update_tgt_scene()
                    self._update_correspondence_table()
            except Exception as e:
                print(f"Error loading target skeleton: {e}")
                # Show error dialog
                self._show_error_dialog(f"Failed to load target skeleton:\n{str(e)}")

    def _show_error_dialog(self, message):
        """Show an error dialog."""
        dlg = gui.Dialog("Error")
        em = self.window.theme.font_size
        dlg_layout = gui.Vert(em, gui.Margins(em, em, em, em))
        dlg_layout.add_child(gui.Label(message))

        ok_button = gui.Button("OK")
        ok_button.set_on_clicked(self._on_error_dialog_ok)
        dlg_layout.add_child(ok_button)

        dlg.add_child(dlg_layout)
        self.window.show_dialog(dlg)

    def _on_error_dialog_ok(self):
        """Handle error dialog OK button."""
        self.window.close_dialog()

    def _prompt_for_source_xml(self, pose_json_path):
        """Prompt user to select XML file for source robot pose."""
        self.pending_source_pose_path = pose_json_path
        filedlg = gui.FileDialog(gui.FileDialog.Mode.OPEN, "Select Source Robot XML", self.window.theme)
        filedlg.add_filter(".xml", "MuJoCo XML files")
        filedlg.add_filter("", "All files")
        filedlg.set_on_cancel(self._on_file_dialog_cancel)
        filedlg.set_on_done(self._on_source_xml_selected)
        self.window.show_dialog(filedlg)

    def _prompt_for_target_xml(self, pose_json_path):
        """Prompt user to select XML file for target robot pose."""
        self.pending_target_pose_path = pose_json_path
        filedlg = gui.FileDialog(gui.FileDialog.Mode.OPEN, "Select Target Robot XML", self.window.theme)
        filedlg.add_filter(".xml", "MuJoCo XML files")
        filedlg.add_filter("", "All files")
        filedlg.set_on_cancel(self._on_file_dialog_cancel)
        filedlg.set_on_done(self._on_target_xml_selected)
        self.window.show_dialog(filedlg)

    def _on_source_xml_selected(self, xml_path):
        """Handle source XML file selection."""
        self.window.close_dialog()
        try:
            self.source_xml_path = xml_path
            self.source_skeleton = SkeletonLoader.load(
                self.pending_source_pose_path,
                skeleton_type="robot_pose",
                robot_xml_path=xml_path
            )
            print(f"Loaded source skeleton from robot pose: {len(self.source_skeleton)} bodies")
            self._update_src_scene()
            self._update_correspondence_table()
        except Exception as e:
            print(f"Error loading source skeleton from robot pose: {e}")
            self._show_error_dialog(f"Failed to load source skeleton:\n{str(e)}")

    def _on_target_xml_selected(self, xml_path):
        """Handle target XML file selection."""
        self.window.close_dialog()
        try:
            self.target_xml_path = xml_path
            self.target_skeleton = SkeletonLoader.load(
                self.pending_target_pose_path,
                skeleton_type="robot_pose",
                robot_xml_path=xml_path
            )
            print(f"Loaded target skeleton from robot pose: {len(self.target_skeleton)} bodies")
            self._update_tgt_scene()
            self._update_correspondence_table()
        except Exception as e:
            print(f"Error loading target skeleton from robot pose: {e}")
            self._show_error_dialog(f"Failed to load target skeleton:\n{str(e)}")

    def _update_src_scene(self):
        """Update source scene with loaded skeleton."""
        self._update_scene(self.src_scene, self.source_skeleton, "source")

    def _update_tgt_scene(self):
        """Update target scene with loaded skeleton."""
        self._update_scene(self.tgt_scene, self.target_skeleton, "target")

    def _update_scene(self, scene, skeleton, name):
        """Update a scene with skeleton data."""
        scene.scene.clear_geometry()

        if skeleton is None:
            return

        # Add skeleton to scene
        self._add_skeleton_to_scene(scene, skeleton, name)

        # Setup camera to fit skeleton
        bounds = scene.scene.bounding_box
        center = bounds.get_center()
        scene.setup_camera(60, bounds, center)

    def _add_skeleton_to_scene(self, scene, skeleton, name):
        """Add skeleton visualization to scene."""
        for body_name, data in skeleton.items():
            position = np.array(data["position"])
            orientation = np.array(data["orientation"])  # [w, x, y, z]

            # Create coordinate frame at body position
            frame = o3d.geometry.TriangleMesh.create_coordinate_frame(
                size=0.1, origin=position
            )

            # Rotate frame by orientation quaternion
            # Convert quaternion [w,x,y,z] to rotation matrix
            rotation_matrix = self._quaternion_to_rotation_matrix(orientation)
            frame.rotate(rotation_matrix, center=position)

            # Add frame to scene
            mat = rendering.MaterialRecord()
            mat.shader = "defaultUnlit"
            scene.scene.add_geometry(f"{name}_{body_name}_frame", frame, mat)

            # Add text label for body name
            scene.add_3d_label(position, body_name)

    def _quaternion_to_rotation_matrix(self, q):
        """Convert quaternion [w, x, y, z] to 3x3 rotation matrix."""
        w, x, y, z = q

        return np.array([
            [1 - 2*y*y - 2*z*z, 2*x*y - 2*w*z, 2*x*z + 2*w*y],
            [2*x*y + 2*w*z, 1 - 2*x*x - 2*z*z, 2*y*z - 2*w*x],
            [2*x*z - 2*w*y, 2*y*z + 2*w*x, 1 - 2*x*x - 2*y*y]
        ])

    def _update_correspondence_table(self):
        """Update the correspondence table UI."""
        table_layout = gui.Vert(0, gui.Margins(0, 0, 0, 0))

        if self.source_skeleton and self.target_skeleton:
            em = self.window.theme.font_size

            # Add table headers with grid layout
            header_layout = gui.Horiz(0, gui.Margins(0, 0, 0, em * 0.25))
            source_header = gui.Label("Source")
            source_header.text_color = gui.Color(0.8, 0.8, 0.8)
            target_header = gui.Label("Target")
            target_header.text_color = gui.Color(0.8, 0.8, 0.8)

            # Use grid layout for proper alignment
            grid = gui.VGrid(2, em * 0.5)
            grid.add_child(source_header)
            grid.add_child(target_header)

            table_layout.add_child(grid)

            # Sort source bodies alphabetically
            sorted_source_bodies = sorted(self.source_skeleton.keys())

            # Add rows for each source body using grid
            for source_body in sorted_source_bodies:
                # Source body label
                source_label = gui.Label(source_body)
                source_label.text_color = gui.Color(0.9, 0.9, 0.9)

                # Dropdown for target selection
                target_dropdown = gui.Combobox()

                # Create closure to capture source_body
                def make_callback(src_body):
                    def callback(text, index):
                        if text == "":
                            # Remove correspondence
                            self.correspondences.pop(src_body, None)
                        else:
                            # Add/update correspondence
                            self.correspondences[src_body] = text
                        print(f"Correspondence: {src_body} → {text if text else '(none)'}")
                    return callback

                target_dropdown.set_on_selection_changed(make_callback(source_body))

                # Populate dropdown with target bodies
                target_dropdown.add_item("")  # Empty option to remove mapping
                sorted_target_bodies = sorted(self.target_skeleton.keys())
                for target_body in sorted_target_bodies:
                    target_dropdown.add_item(target_body)

                # Set current selection if exists
                if source_body in self.correspondences:
                    target_name = self.correspondences[source_body]
                    if target_name in sorted_target_bodies:
                        # +1 because index 0 is the empty option
                        target_dropdown.selected_index = sorted_target_bodies.index(target_name) + 1

                # Add to grid
                grid.add_child(source_label)
                grid.add_child(target_dropdown)

        elif self.source_skeleton:
            info_label = gui.Label("Load target skeleton to create mappings")
            info_label.text_color = gui.Color(0.7, 0.7, 0.7)
            table_layout.add_child(info_label)
        elif self.target_skeleton:
            info_label = gui.Label("Load source skeleton to create mappings")
            info_label.text_color = gui.Color(0.7, 0.7, 0.7)
            table_layout.add_child(info_label)
        else:
            info_label = gui.Label("Load skeletons to begin")
            info_label.text_color = gui.Color(0.7, 0.7, 0.7)
            table_layout.add_child(info_label)

        # Update the proxy widget
        self.correspondence_table_proxy.set_widget(table_layout)

    def _on_export_clicked(self):
        """Handle export button click."""
        if not self.source_skeleton or not self.target_skeleton:
            self._show_error_dialog("Please load both source and target skeletons first.")
            return

        if not self.correspondences:
            self._show_error_dialog("Please create at least one body correspondence.")
            return

        # Show file save dialog
        filedlg = gui.FileDialog(gui.FileDialog.Mode.SAVE, "Save IK Config", self.window.theme)
        filedlg.add_filter(".json", "JSON files")
        filedlg.add_filter("", "All files")
        filedlg.set_on_cancel(self._on_file_dialog_cancel)
        filedlg.set_on_done(self._on_export_done)
        self.window.show_dialog(filedlg)

    def _on_export_done(self, path):
        """Handle export file dialog done."""
        self.window.close_dialog()

        # Ensure .json extension
        if not path.endswith('.json'):
            path += '.json'

        try:
            # Create IK config generator with Phase 2 features
            generator = IKConfigGenerator(
                source_skeleton=self.source_skeleton,
                target_skeleton=self.target_skeleton,
                correspondences=self.correspondences,
                robot_root_name=self.robot_root_name,
                human_root_name=self.human_root_name,
                human_height_assumption=self.human_height_assumption,
                auto_calculate_offsets=self.auto_calculate_offsets,
                auto_calculate_scales=self.auto_calculate_scales,
                auto_suggest_weights=self.auto_suggest_weights,
                use_height_scaling=self.use_height_scaling,
                use_limb_scaling=self.use_limb_scaling,
            )

            # Save config
            generator.save(path)

            # Build success message
            msg = f"IK config saved to:\n{path}\n\n{len(self.correspondences)} correspondences"
            if self.auto_calculate_offsets:
                msg += "\n✓ Rotation offsets calculated"
            if self.auto_calculate_scales:
                msg += "\n✓ Scale factors calculated"
            if self.auto_suggest_weights:
                msg += "\n✓ IK weights suggested"

            # Show success dialog
            self._show_success_dialog(msg)

        except Exception as e:
            self._show_error_dialog(f"Failed to export IK config:\n{str(e)}")

    def _show_success_dialog(self, message):
        """Show a success dialog."""
        dlg = gui.Dialog("Success")
        em = self.window.theme.font_size
        dlg_layout = gui.Vert(em, gui.Margins(em, em, em, em))
        dlg_layout.add_child(gui.Label(message))

        ok_button = gui.Button("OK")
        ok_button.set_on_clicked(self._on_error_dialog_ok)  # Reuse same callback
        dlg_layout.add_child(ok_button)

        dlg.add_child(dlg_layout)
        self.window.show_dialog(dlg)

    def run(self):
        """Run the application."""
        self.app.run()


if __name__ == "__main__":
    app = IKConfigEditorApp()
    app.run()
