import os
import json  # Now using JSON for settings
import customtkinter as ctk
import tkinter as tk
from tkinter import filedialog, Menu
from animExport import export_single_animation as export_anim
from animExport import export_all_animations as export_all_anims
from FBX_import import load_fbx_animations  # Import the actual FBX handler

# Path for the settings.json file
settings_file = "settings.json"

# Define color themes (including additional ones)
color_themes = {
    "Blue":   {"frame":"#2E2E2E","label":"#F5F5F5","btn":"#2F80ED","btn_hover":"#1C5DB6","btn_text":"#FFFFFF","btn_disabled":"#3A3A3A","btn_disabled_text":"#9A9A9A"},
    "Orange": {"frame":"#2E2E2E","label":"#F5F5F5","btn":"#F2994A","btn_hover":"#D9822B","btn_text":"#1A1A1A","btn_disabled":"#5A4A34","btn_disabled_text":"#B0A38C"},
    "Pink":   {"frame":"#2E2E2E","label":"#F5F5F5","btn":"#E0569B","btn_hover":"#C84583","btn_text":"#FFFFFF","btn_disabled":"#4A3A42","btn_disabled_text":"#B6A6AF"},
    "Red":    {"frame":"#2E2E2E","label":"#F5F5F5","btn":"#D64545","btn_hover":"#B93737","btn_text":"#FFFFFF","btn_disabled":"#4A2F2F","btn_disabled_text":"#B8A0A0"},
    "Yellow": {"frame":"#2E2E2E","label":"#F5F5F5","btn":"#F2C94C","btn_hover":"#D4AE3C","btn_text":"#1A1A1A","btn_disabled":"#5A5338","btn_disabled_text":"#B8B2A3"},
    "Purple": {"frame":"#2E2E2E","label":"#F5F5F5","btn":"#6C3EB8","btn_hover":"#56308F","btn_text":"#FFFFFF","btn_disabled":"#3F335A","btn_disabled_text":"#B1A9C6"},
}

class FBXToAnimConverterApp:
    def __init__(self, root):
        self.export_dir = None
        self.root = root
        self.root.title(".anim Creator")

        # FBX lifetime / loaded data
        self.fbx_manager = None
        self.scene = None
        self.fbx_file = None

        self.animations_with_originals = []
        self.animations = []
        self.bone_names = []
        self.default_ignored_bones = set()
        self.ignored_bones = set()
        self.location_ignored_bones = set()
        self.write_scale = False
        self.use_linear_reduction = True
        self.reverse_animation = False

        # Padding values for the main frame
        self.main_frame_padding = {'padx': 20, 'pady': 20}  # Define padding here

        # Set window size and allow maximization
        self.root.geometry("540x630")
        self.root.resizable(False, False)

        # Set the theme for customtkinter
        ctk.set_appearance_mode("dark")  # Dark mode
        
        # Load settings from the JSON file
        self.settings = self.load_settings()

        self.auto_set_fps = self.settings.get("auto_set_fps", True)

        self.theme_var = tk.StringVar(value=self.settings.get("theme", "Blue"))

        # Apply the saved window position
        window_position = self.settings.get("window_position", "100x100")
        self.root.geometry(f"540x630+{window_position.split('x')[0]}+{window_position.split('x')[1]}")

        # Build UI components
        self.build_ui()

        # Hotkeys
        self.root.bind("<Control-e>", lambda e: self.export_single_animation())
        self.root.bind("<Control-r>", lambda e: self.rename_animation())
        self.root.bind("<Control-c>", lambda e: self.delete_animation())

        # Apply the saved theme after building the UI
        self.apply_saved_theme()
        self._icon_img = None
        script_dir = os.path.dirname(os.path.abspath(__file__))
        png_path = os.path.join(script_dir, "icon.png")
        ico_path = os.path.join(script_dir, "icon.ico")

        self._png_path = png_path
        self._ico_path = ico_path

        try:
            self.root.iconbitmap(self._ico_path)
        except Exception:
            pass
        
        self._update_export_all_state()

    def load_settings(self):
        defaults = {
            "default_export_dir": "",
            "theme": "Blue",
            "window_position": "100x100",
            "ignored_bones_presets": {},
            "location_ignored_bones_presets": {},
            "auto_set_fps": True
        }

        if os.path.exists(settings_file):
            try:
                with open(settings_file, "r", encoding="utf-8") as f:
                    settings = json.load(f)
            except Exception:
                settings = {}
        else:
            settings = {}

        for k, v in defaults.items():
            settings.setdefault(k, v)

        return settings

    def apply_window_icon(self, win):
        """Apply app icon reliably to any CTkToplevel (Windows/CTk safe)."""
        try:
            # Ensure icon image is cached
            if getattr(self, "_icon_img", None) is None and getattr(self, "_png_path", None):
                try:
                    self._icon_img = tk.PhotoImage(file=self._png_path)
                except Exception:
                    self._icon_img = None

            def apply_once():
                try:
                    if getattr(self, "_icon_img", None) is not None:
                        win.iconphoto(True, self._icon_img)
                    else:
                        win.iconbitmap(self._ico_path)
                except Exception:
                    pass

            # Apply after mapping + re-apply shortly after (CTk can stomp once)
            win.after_idle(apply_once)
            win.after(60, apply_once)
            win.after(250, apply_once)

        except Exception:
            pass

    def build_ui(self):
        """Build the user interface for the application."""
        self.main_frame = ctk.CTkFrame(self.root)
        self.main_frame.pack(fill="both", expand=True, **self.main_frame_padding)

        # --- Top row for symmetrical button layout ---
        self.top_buttons_frame = ctk.CTkFrame(self.main_frame, fg_color="transparent")
        self.top_buttons_frame.pack(fill="x", padx=0, pady=(0, 10))

        self.top_left_frame = ctk.CTkFrame(self.top_buttons_frame, fg_color="transparent")
        self.top_left_frame.pack(side="left", anchor="n")

        self.top_right_frame = ctk.CTkFrame(self.top_buttons_frame, fg_color="transparent")
        self.top_right_frame.pack(side="right", anchor="n")

        # Left column
        self.settings_button = self.create_button(
            root=self.top_left_frame,
            text="Settings",
            command=self.toggle_settings,
            anchor="w",
            padx=10,
            pady=(10, 10)
        )

        self.scale_toggle_button = self.create_button(
            root=self.top_left_frame,
            text="Scale: Off",
            command=self.toggle_scale_export,
            anchor="w",
            padx=10,
            pady=(0, 10)
        )

        self.linear_toggle_button = self.create_button(
            root=self.top_left_frame,
            text="Clean: On",
            command=self.toggle_linear_reduction,
            anchor="w",
            padx=10,
            pady=(0, 0)
        )

        # Right column
        self.ignored_bones_button = self.create_button(
            root=self.top_right_frame,
            text="Ignored Bones",
            command=self.open_bone_selection_window,
            anchor="ne",
            padx=10,
            pady=(10, 10)
        )

        self.location_ignored_bones_button = self.create_button(
            root=self.top_right_frame,
            text="Location Ignore",
            command=self.open_location_bone_selection_window,
            anchor="ne",
            padx=10,
            pady=(0, 10)
        )

        self.reverse_toggle_button = self.create_button(
            root=self.top_right_frame,
            text="Reverse: Off",
            command=self.toggle_reverse_animation,
            anchor="ne",
            padx=10,
            pady=(0, 0)
        )

        # Hide right column until FBX is loaded
        self.top_right_frame.pack_forget()

        # Label for showing the FBX file name at the top
        self.fbx_label = ctk.CTkLabel(self.main_frame, text="Select an FBX file to begin", font=("Arial", 14))
        self.fbx_label.pack(pady=6)

        # File selection button
        self.select_fbx_button = ctk.CTkButton(
            self.main_frame,
            text="Select FBX File",
            command=self.select_fbx_file,
            width=25
        )
        self.select_fbx_button.pack(pady=6)

        # Rounded Listbox frame with left padding
        self.listbox_frame = ctk.CTkFrame(self.main_frame, fg_color="#2E2E2E", corner_radius=15)
        self.listbox_frame.pack(pady=6, padx=(5, 5), fill="both")

        # Inner container for listbox + scrollbar
        self.listbox_inner = tk.Frame(self.listbox_frame, bg="#2E2E2E")
        self.listbox_inner.pack(pady=6, padx=8, fill="both", expand=True)

        self.anim_scrollbar = tk.Scrollbar(self.listbox_inner)
        self.anim_scrollbar.pack(side="right", fill="y")

        self.anim_listbox = tk.Listbox(
            self.listbox_inner,
            height=7,
            bg="#2E2E2E",
            fg="white",
            selectbackground="#4A90E2",
            selectforeground="white",
            bd=1,
            relief="solid",
            highlightthickness=1,
            highlightbackground="#555555",
            highlightcolor="#4A90E2",
            borderwidth=0,
            font=("Calibri", 14),
            yscrollcommand=self.anim_scrollbar.set
        )
        self.anim_listbox.configure(activestyle="none")
        self.anim_listbox.pack(side="left", fill="both", expand=True)

        self.anim_scrollbar.config(command=self.anim_listbox.yview)

        self.anim_listbox.bind('<Button-3>', self.show_context_menu)

        # Right-click context menu for rename, delete, and export
        self.context_menu = Menu(self.root, tearoff=0)
        self.context_menu.add_command(label="Export", command=self.export_single_animation)
        self.context_menu.add_command(label="Rename", command=self.rename_animation)
        self.context_menu.add_command(label="Delete", command=self.delete_animation)

        # Custom Export Directory selection
        self.export_dir_frame = ctk.CTkFrame(self.main_frame)
        self.export_dir_frame.pack(pady=6)

        # Save the browse button as an instance variable
        self.export_dir_entry = ctk.CTkEntry(self.export_dir_frame, width=300)
        self.export_dir_entry.pack(side="left", padx=(0, 5))
        self.export_dir_entry.bind("<KeyRelease>", lambda e: self._update_export_all_state())

        default_dir = self.settings.get("default_export_dir", "")
        if default_dir:
            self.export_dir_entry.insert(0, default_dir)


        # Store browse button as an instance variable for color updates
        self.browse_button = ctk.CTkButton(self.export_dir_frame, text="Browse", command=self.select_export_directory)
        self.browse_button.pack(side="left", padx=(5, 0))

        # Export all button
        self.export_all_button = ctk.CTkButton(self.main_frame, text="Export All Animations", command=self.export_all_animations_handler, width=25, state="disabled")
        self.export_all_button.pack(pady=6)

        # Status area
        self.status_label = tk.Message(
            self.main_frame,
            text="",
            fg="white",
            bg="#2E2E2E",
            font=("Segoe UI", 11),
            justify="center",
            anchor="center",
            width=500,
            bd=0,
            highlightthickness=0
        )
        self.status_label.pack(fill="x", padx=6, pady=(12, 16), ipady=6)

        # Hidden settings frame
        self.build_settings_frame()

    def _get_export_dir(self) -> str:
        return (self.export_dir or self.export_dir_entry.get().strip() or self.settings.get("default_export_dir", "")).strip()

    def _update_export_all_state(self):
        # Your rule: if there's an FBX loaded, undarkens
        new_state = "normal" if self.scene is not None else "disabled"
        self.export_all_button.configure(state=new_state)

        # Force correct colors after state change (important!)
        try:
            self.update_ui_colors(self.settings.get("theme", "Blue"))
        except Exception:
            pass

    def set_status(self, text: str, is_error: bool = False, source: str = ""):
        self.status_label.configure(
            text=text,
            fg=("red" if is_error else "green")
        )
        self._last_status_text = text

    def toggle_scale_export(self):
        self.write_scale = not getattr(self, "write_scale", False)
        self.scale_toggle_button.configure(text=f"Scale: {'On' if self.write_scale else 'Off'}")

    def toggle_linear_reduction(self):
        self.use_linear_reduction = not getattr(self, "use_linear_reduction", False)
        self.linear_toggle_button.configure(
            text=f"Clean: {'On' if self.use_linear_reduction else 'Off'}"
        )

    def toggle_auto_set_fps(self):
        self.auto_set_fps = not getattr(self, "auto_set_fps", True)
        self.auto_fps_toggle_button.configure(
            text=f"Auto FPS: {'On' if self.auto_set_fps else 'Off'}"
        )
        self.settings["auto_set_fps"] = self.auto_set_fps
        self.save_settings()

    def toggle_reverse_animation(self):
        self.reverse_animation = not getattr(self, "reverse_animation", False)
        self.reverse_toggle_button.configure(
            text=f"Reverse: {'On' if self.reverse_animation else 'Off'}"
            )

    def open_location_bone_selection_window(self):
        if not getattr(self, "bone_names", None):
            self.set_status("No bones loaded. Load an FBX first.", is_error=True)
            return

        try:
            if hasattr(self, "location_bone_selection_window") and self.location_bone_selection_window.winfo_exists():
                self.location_bone_selection_window.lift()
                return
        except Exception:
            pass

        bone_names = self.bone_names

        """Location-only ignore window for stripping translation keys while keeping rotation."""
        stripped_paths = []
        for p in bone_names:
            parts = [x for x in p.split("|") if x]
            if len(parts) <= 2:
                continue
            stripped_paths.append("|".join(parts[2:]))

        self.location_bone_selection_window = ctk.CTkToplevel(self.root)
        self.apply_window_icon(self.location_bone_selection_window)
        self.location_bone_selection_window.title("Choose which bones should ignore location")
        self.center_window(self.location_bone_selection_window, 620, 620)
        self.location_bone_selection_window.grab_set()
        self.location_bone_selection_window.transient(self.root)

        self._location_bone_ctrl_held = False
        self.location_bone_selection_window.bind("<Control_L>", lambda e: setattr(self, "_location_bone_ctrl_held", True))
        self.location_bone_selection_window.bind("<KeyRelease-Control_L>", lambda e: setattr(self, "_location_bone_ctrl_held", False))

        self._location_bone_shift_held = False
        self.location_bone_selection_window.bind("<Shift_L>", lambda e: setattr(self, "_location_bone_shift_held", True))
        self.location_bone_selection_window.bind("<KeyRelease-Shift_L>", lambda e: setattr(self, "_location_bone_shift_held", False))

        self.location_bone_selection_window.protocol(
            "WM_DELETE_WINDOW",
            lambda: (self.location_bone_selection_window.destroy(), self.root.lift())
        )
        self.location_bone_selection_window.bind(
            "<Escape>",
            lambda e: (self.location_bone_selection_window.destroy(), self.root.lift())
        )

        self.location_scroll_frame = ctk.CTkScrollableFrame(self.location_bone_selection_window, width=590, height=455)
        self.location_scroll_frame.pack(pady=(10, 6), padx=10, fill="both", expand=True)

        self.location_bone_rows = {}
        self.location_bone_order = []
        self._location_bone_tree = self._build_bone_tree(stripped_paths)

        button_frame = ctk.CTkFrame(self.location_bone_selection_window, fg_color=None)
        button_frame.pack(pady=(8, 6), padx=10, fill="x")

        self.settings.setdefault("location_ignored_bones_presets", {})
        self.location_preset_panel_open = False

        BTN_W = 90

        self.location_presets_toggle_btn = ctk.CTkButton(
            button_frame,
            text="Presets",
            width=BTN_W,
            command=self._toggle_location_preset_panel
        )
        self.location_presets_toggle_btn.pack(side="left", padx=(0, 6))

        ctk.CTkButton(button_frame, text="Invert", width=BTN_W, command=self._invert_location_bones).pack(side="left", padx=4)
        ctk.CTkButton(button_frame, text="None", width=BTN_W, command=self._select_no_location_bones).pack(side="left", padx=4)

        self.location_apply_button = ctk.CTkButton(
            button_frame,
            text="Skip",
            width=BTN_W,
            command=self.apply_location_bone_selection
        )
        self.location_apply_button.pack(side="right", padx=5)

        self.location_preset_actions_frame = ctk.CTkFrame(self.location_bone_selection_window, fg_color=None)

        preset_names = sorted(self.settings["location_ignored_bones_presets"].keys())
        if preset_names:
            self.location_preset_var = tk.StringVar(value=preset_names[0])
            menu_values = preset_names
        else:
            self.location_preset_var = tk.StringVar(value="(None)")
            menu_values = ["(None)"]

        self.location_preset_menu = ctk.CTkOptionMenu(
            self.location_preset_actions_frame,
            values=menu_values,
            variable=self.location_preset_var,
            width=220
        )
        self.location_preset_menu.pack(side="left", padx=(0, 8))

        ctk.CTkButton(
            self.location_preset_actions_frame,
            text="Load",
            width=BTN_W,
            command=self._load_selected_location_preset
        ).pack(side="left", padx=4)

        ctk.CTkButton(
            self.location_preset_actions_frame,
            text="Save As",
            width=BTN_W,
            command=self._save_current_as_location_preset
        ).pack(side="left", padx=4)

        ctk.CTkButton(
            self.location_preset_actions_frame,
            text="Update",
            width=BTN_W,
            command=self._update_selected_location_preset
        ).pack(side="left", padx=4)

        ctk.CTkButton(
            self.location_preset_actions_frame,
            text="Delete",
            width=BTN_W,
            command=self._delete_selected_location_preset
        ).pack(side="left", padx=4)

        self.location_preset_actions_frame.pack(pady=(0, 8), padx=10, fill="x")
        self.location_preset_actions_frame.pack_forget()

        self._rebuild_location_bone_rows()
        self.update_theme_for_window(self.location_bone_selection_window)

    def _rebuild_location_bone_rows(self):
        for child in self.location_scroll_frame.winfo_children():
            child.destroy()

        self.location_bone_rows.clear()
        self.location_bone_order.clear()

        def add_row(display_name, full_path, depth, has_children, parent_path):
            row = ctk.CTkFrame(self.location_scroll_frame, fg_color=None)
            row.pack(anchor="w", fill="x", padx=6, pady=1)

            expanded = tk.BooleanVar(value=False)
            indent_px = depth * 18
            ctk.CTkLabel(row, text="", width=indent_px).pack(side="left")

            if has_children:
                toggle_btn = ctk.CTkButton(
                    row,
                    text="▶",
                    width=22,
                    height=22,
                    command=lambda p=full_path: self.toggle_location_expand(p)
                )
                toggle_btn.pack(side="left", padx=(0, 6))
            else:
                toggle_btn = None
                ctk.CTkLabel(row, text="", width=22).pack(side="left", padx=(0, 6))

            var = tk.BooleanVar(value=(full_path in self.location_ignored_bones))
            cb = ctk.CTkCheckBox(
                row,
                text=display_name,
                variable=var,
                command=lambda p=full_path: self.on_location_bone_checkbox_clicked(p)
            )
            cb.pack(side="left", anchor="w")

            self.location_bone_rows[full_path] = {
                "frame": row,
                "var": var,
                "depth": depth,
                "parent": parent_path,
                "toggle": toggle_btn,
                "expanded": expanded,
            }
            self.location_bone_order.append(full_path)

        def walk(node_dict, depth=0, parent_path=None):
            for part, meta in node_dict.items():
                full = meta["__path"]
                children = meta["__children"]
                add_row(part, full, depth, bool(children), parent_path)
                walk(children, depth + 1, full)

        walk(self._location_bone_tree, 0, None)

        for path, row in self.location_bone_rows.items():
            if row["parent"] is not None:
                row["frame"].pack_forget()

        self.update_location_apply_button_text()

    def on_location_bone_checkbox_clicked(self, bone_path: str):
        row = self.location_bone_rows.get(bone_path)
        if not row:
            return

        new_state = row["var"].get()
        if getattr(self, "_location_bone_shift_held", False):
            for child in self._location_descendants(bone_path):
                if child in self.location_bone_rows:
                    self.location_bone_rows[child]["var"].set(new_state)

        self.update_location_apply_button_text()

    def _location_direct_children(self, parent_path: str):
        parent_depth = self.location_bone_rows[parent_path]["depth"]
        prefix = parent_path + "|"
        out = []
        for p in self.location_bone_order:
            if not p.startswith(prefix):
                continue
            if self.location_bone_rows[p]["depth"] == parent_depth + 1:
                out.append(p)
        return out

    def _next_non_descendant_visible_location_frame(self, parent_path: str):
        parent_idx = self.location_bone_order.index(parent_path)
        prefix = parent_path + "|"

        for i in range(parent_idx + 1, len(self.location_bone_order)):
            p = self.location_bone_order[i]
            if p.startswith(prefix):
                continue
            fr = self.location_bone_rows[p]["frame"]
            if fr.winfo_manager():
                return fr
        return None

    def _show_location_subtree(self, parent_path: str, show_all: bool):
        anchor = self._next_non_descendant_visible_location_frame(parent_path)
        parent_frame = self.location_bone_rows[parent_path]["frame"]

        prev = parent_frame
        for child in self._location_direct_children(parent_path):
            fr = self.location_bone_rows[child]["frame"]
            if anchor is not None:
                fr.pack(anchor="w", fill="x", padx=6, pady=1, before=anchor)
            else:
                fr.pack(anchor="w", fill="x", padx=6, pady=1)
            prev = fr

            if show_all:
                self.location_bone_rows[child]["expanded"].set(True)
                if self.location_bone_rows[child]["toggle"] is not None:
                    self.location_bone_rows[child]["toggle"].configure(text="▼")
                self._show_location_subtree(child, show_all=True)

    def _invert_location_bones(self):
        for row in self.location_bone_rows.values():
            row["var"].set(not row["var"].get())
        self.update_location_apply_button_text()

    def _location_descendants(self, parent_path: str):
        prefix = parent_path + "|"
        for p in self.location_bone_order:
            if p.startswith(prefix):
                yield p

    def toggle_location_expand(self, bone_path: str):
        row = self.location_bone_rows.get(bone_path)
        if not row:
            return

        expanded_now = row["expanded"].get()
        row["expanded"].set(not expanded_now)

        if row["toggle"] is not None:
            row["toggle"].configure(text="▼" if not expanded_now else "▶")

        expand_all = getattr(self, "_location_bone_ctrl_held", False)

        if not expanded_now:
            self._show_location_subtree(bone_path, show_all=expand_all)
            if expand_all:
                for p in self._location_descendants(bone_path):
                    self.location_bone_rows[p]["expanded"].set(True)
                    if self.location_bone_rows[p]["toggle"] is not None:
                        self.location_bone_rows[p]["toggle"].configure(text="▼")
        else:
            for p in self._location_descendants(bone_path):
                self.location_bone_rows[p]["frame"].pack_forget()
                self.location_bone_rows[p]["expanded"].set(False)
                if self.location_bone_rows[p]["toggle"] is not None:
                    self.location_bone_rows[p]["toggle"].configure(text="▶")

    def _select_no_location_bones(self):
        for row in self.location_bone_rows.values():
            row["var"].set(False)
        self.update_location_apply_button_text()

    def update_location_apply_button_text(self):
        if any(row["var"].get() for row in self.location_bone_rows.values()):
            self.location_apply_button.configure(text="Apply")
        else:
            self.location_apply_button.configure(text="Skip")

    def apply_location_bone_selection(self):
        self.location_ignored_bones = {path for path, row in self.location_bone_rows.items() if row["var"].get()}
        self.set_status("Location ignore bones applied.", is_error=False)

        try:
            self.location_bone_selection_window.destroy()
        except Exception:
            pass
        self.root.lift()

    def open_bone_selection_window(self):
        if not getattr(self, "bone_names", None):
            self.set_status("No bones loaded. Load an FBX first.", is_error=True)
            return

        try:
            if hasattr(self, "bone_selection_window") and self.bone_selection_window.winfo_exists():
                self.bone_selection_window.lift()
                return
        except Exception:
            pass

        bone_names = self.bone_names  # ← THIS LINE FIXES YOUR ERROR
        """
        Bone ignore window:
        - Removes the first 2 hierarchy levels (RootNode + Armature name) from ALL paths for UI
        so they cannot appear as parents in the tree.
        - Presets panel uses consistent button widths and fits better.
        - Theme is applied AFTER widgets are created.
        """

        # ---- Strip the first two segments from every path so RootNode/Armature cannot appear ----
        # Example: "RootNode|Zelda|Root|Spine" -> "Root|Spine"
        stripped_paths = []
        for p in bone_names:
            parts = [x for x in p.split("|") if x]
            if len(parts) <= 2:
                # header nodes only; ignore
                continue
            stripped_paths.append("|".join(parts[2:]))

        self.bone_selection_window = ctk.CTkToplevel(self.root)
        self.apply_window_icon(self.bone_selection_window)

        self.bone_selection_window.title("Choose which bones to ignore")
        self.center_window(self.bone_selection_window, 620, 620)  # a bit wider so buttons fit
        # IMPORTANT: apply theme later after widgets exist
        

        self.bone_selection_window.grab_set()
        self.bone_selection_window.transient(self.root)

        # ctrl tracking ONLY for this window (used for expand-all)
        self._bone_ctrl_held = False
        self.bone_selection_window.bind("<Control_L>", lambda e: setattr(self, "_bone_ctrl_held", True))
        self.bone_selection_window.bind("<KeyRelease-Control_L>", lambda e: setattr(self, "_bone_ctrl_held", False))

        self._bone_shift_held = False
        self.bone_selection_window.bind("<Shift_L>", lambda e: setattr(self, "_bone_shift_held", True))
        self.bone_selection_window.bind("<KeyRelease-Shift_L>", lambda e: setattr(self, "_bone_shift_held", False))

        # Scrollable area
        self.scroll_frame = ctk.CTkScrollableFrame(self.bone_selection_window, width=590, height=455)
        self.scroll_frame.pack(pady=(10, 6), padx=10, fill="both", expand=True)

        self.bone_rows = {}
        self.bone_order = []
        self._bone_tree = self._build_bone_tree(stripped_paths)

        # --- Bottom bar: Presets toggle + helpers + Apply/Skip ---
        button_frame = ctk.CTkFrame(self.bone_selection_window, fg_color=None)
        button_frame.pack(pady=(8, 6), padx=10, fill="x")

        self.settings.setdefault("ignored_bones_presets", {})
        self.preset_panel_open = False

        BTN_W = 90  # uniform button width

        self.presets_toggle_btn = ctk.CTkButton(
            button_frame,
            text="Presets",
            width=BTN_W,
            command=self._toggle_preset_panel
        )
        self.presets_toggle_btn.pack(side="left", padx=(0, 6))

        ctk.CTkButton(button_frame, text="Invert", width=BTN_W, command=self._invert_bones).pack(side="left", padx=4)
        ctk.CTkButton(button_frame, text="None", width=BTN_W, command=self._select_no_bones).pack(side="left", padx=4)

        self.apply_button = ctk.CTkButton(button_frame, text="Skip", width=BTN_W, command=self.apply_bone_selection)
        self.apply_button.pack(side="right", padx=5)

        # Preset action panel (hidden until toggled)
        self.preset_actions_frame = ctk.CTkFrame(self.bone_selection_window, fg_color=None)

        preset_names = sorted(self.settings["ignored_bones_presets"].keys())
        if preset_names:
            self.preset_var = tk.StringVar(value=preset_names[0])
            menu_values = preset_names
        else:
            self.preset_var = tk.StringVar(value="(None)")
            menu_values = ["(None)"]

        self.preset_menu = ctk.CTkOptionMenu(
            self.preset_actions_frame,
            values=menu_values,
            variable=self.preset_var,
            width=220
        )
        self.preset_menu.pack(side="left", padx=(0, 8))

        ctk.CTkButton(self.preset_actions_frame, text="Load", width=BTN_W, command=self._load_selected_preset).pack(side="left", padx=4)
        ctk.CTkButton(self.preset_actions_frame, text="Save As", width=BTN_W, command=self._save_current_as_preset).pack(side="left", padx=4)
        ctk.CTkButton(self.preset_actions_frame, text="Update", width=BTN_W, command=self._update_selected_preset).pack(side="left", padx=4)
        ctk.CTkButton(self.preset_actions_frame, text="Delete", width=BTN_W, command=self._delete_selected_preset).pack(side="left", padx=4)

        self.preset_actions_frame.pack(pady=(0, 8), padx=10, fill="x")
        self.preset_actions_frame.pack_forget()

        self._rebuild_bone_rows()

        # NOW apply theme so it hits EVERYTHING inside this window
        self.update_theme_for_window(self.bone_selection_window)

    def _toggle_preset_panel(self):
        self.preset_panel_open = not getattr(self, "preset_panel_open", False)

        t = color_themes.get(self.settings.get("theme", "Blue"), color_themes["Blue"])

        if self.preset_panel_open:
            self.preset_actions_frame.pack(pady=(0, 8), padx=10, fill="x")
            # Darken when toggled: use frame color
            self.presets_toggle_btn.configure(fg_color=t["frame"])
        else:
            self.preset_actions_frame.pack_forget()
            self.presets_toggle_btn.configure(fg_color=t["btn"])


    def _refresh_preset_menu(self):
        preset_names = sorted(self.settings.get("ignored_bones_presets", {}).keys())
        if preset_names:
            self.preset_menu.configure(values=preset_names)
            if self.preset_var.get() not in preset_names:
                self.preset_var.set(preset_names[0])
        else:
            self.preset_menu.configure(values=["(None)"])
            self.preset_var.set("(None)")


    def _update_selected_preset(self):
        name = self.preset_var.get()
        if name == "(None)":
            self.set_status("No preset selected to update.", is_error=True)
            return

        selected_ignored = [p for p, r in self.bone_rows.items() if r["var"].get()]
        self.settings.setdefault("ignored_bones_presets", {})[name] = selected_ignored
        self.save_settings()
        self.set_status(f"Preset updated: {name}", is_error=False)

    def _toggle_location_preset_panel(self):
        self.location_preset_panel_open = not getattr(self, "location_preset_panel_open", False)

        t = color_themes.get(self.settings.get("theme", "Blue"), color_themes["Blue"])

        if self.location_preset_panel_open:
            self.location_preset_actions_frame.pack(pady=(0, 8), padx=10, fill="x")
            self.location_presets_toggle_btn.configure(fg_color=t["frame"])
        else:
            self.location_preset_actions_frame.pack_forget()
            self.location_presets_toggle_btn.configure(fg_color=t["btn"])


    def _refresh_location_preset_menu(self):
        preset_names = sorted(self.settings.get("location_ignored_bones_presets", {}).keys())
        if preset_names:
            self.location_preset_menu.configure(values=preset_names)
            if self.location_preset_var.get() not in preset_names:
                self.location_preset_var.set(preset_names[0])
        else:
            self.location_preset_menu.configure(values=["(None)"])
            self.location_preset_var.set("(None)")


    def _load_selected_location_preset(self):
        name = self.location_preset_var.get()
        if name == "(None)":
            return

        presets = self.settings.get("location_ignored_bones_presets", {})
        bones = set(presets.get(name, []))

        for path, row in self.location_bone_rows.items():
            row["var"].set(path in bones)

        self.update_location_apply_button_text()
        self.set_status(f"Location preset loaded: {name}", is_error=False)


    def _save_current_as_location_preset(self):
        win = ctk.CTkToplevel(self.location_bone_selection_window)
        self.apply_window_icon(win)
        win.title("Save Location Preset")
        self.center_window(win, 320, 140)
        self.update_theme_for_window(win)
        win.grab_set()
        win.transient(self.location_bone_selection_window)

        entry = ctk.CTkEntry(win, width=260, placeholder_text="Preset name...")
        entry.pack(pady=(18, 10), padx=10)

        def do_save():
            name = entry.get().strip()
            if not name:
                return

            selected_ignored = [p for p, r in self.location_bone_rows.items() if r["var"].get()]
            self.settings.setdefault("location_ignored_bones_presets", {})[name] = selected_ignored
            self.save_settings()
            self._refresh_location_preset_menu()
            self.location_preset_var.set(name)

            try:
                win.grab_release()
            except Exception:
                pass
            win.destroy()

            self.set_status(f"Location preset saved: {name}", is_error=False)

        ctk.CTkButton(win, text="Save", command=do_save).pack(pady=(0, 12))


    def _update_selected_location_preset(self):
        name = self.location_preset_var.get()
        if name == "(None)":
            self.set_status("No location preset selected to update.", is_error=True)
            return

        selected_ignored = [p for p, r in self.location_bone_rows.items() if r["var"].get()]
        self.settings.setdefault("location_ignored_bones_presets", {})[name] = selected_ignored
        self.save_settings()
        self.set_status(f"Location preset updated: {name}", is_error=False)


    def _delete_selected_location_preset(self):
        name = self.location_preset_var.get()
        if name == "(None)":
            return

        presets = self.settings.get("location_ignored_bones_presets", {})
        if name in presets:
            del presets[name]
            self.settings["location_ignored_bones_presets"] = presets
            self.save_settings()
            self._refresh_location_preset_menu()
            self.location_preset_var.set("(None)")
            self.set_status(f"Location preset deleted: {name}", is_error=False)

    def _build_bone_tree(self, paths):
        """
        Convert ['Root|Spine|Arm', ...] into a nested dict:
        { 'Root': { '__path': 'Root', '__children': { 'Spine': {...}}}}
        """
        tree = {}
        for p in paths:
            parts = [x for x in p.split('|') if x]
            node = tree
            acc = []
            for part in parts:
                acc.append(part)
                full = '|'.join(acc)
                node = node.setdefault(part, {"__path": full, "__children": {}})["__children"]
        return tree

    def _rebuild_bone_rows(self):
        # Clear scroll frame
        for child in self.scroll_frame.winfo_children():
            child.destroy()

        self.bone_rows.clear()
        self.bone_order.clear()

        def add_row(display_name, full_path, depth, has_children, parent_path):
            row = ctk.CTkFrame(self.scroll_frame, fg_color=None)
            row.pack(anchor="w", fill="x", padx=6, pady=1)

            expanded = tk.BooleanVar(value=False)

            # Blender-like indentation BEFORE arrow (so arrows sit next to parent)
            indent_px = depth * 18  # tweak to taste
            ctk.CTkLabel(row, text="", width=indent_px).pack(side="left")

            # Arrow button (triangle)
            if has_children:
                toggle_btn = ctk.CTkButton(
                    row,
                    text="▶",     # collapsed
                    width=22,
                    height=22,
                    command=lambda p=full_path: self.toggle_expand(p)
                )
                toggle_btn.pack(side="left", padx=(0, 6))
            else:
                toggle_btn = None
                ctk.CTkLabel(row, text="", width=22).pack(side="left", padx=(0, 6))

            # Checkbox
            var = tk.BooleanVar(value=(full_path in self.ignored_bones))
            cb = ctk.CTkCheckBox(
                row,
                text=display_name,
                variable=var,
                command=lambda p=full_path: self.on_bone_checkbox_clicked(p)
            )
            cb.pack(side="left", anchor="w")

            self.bone_rows[full_path] = {
                "frame": row,
                "var": var,
                "depth": depth,
                "parent": parent_path,
                "toggle": toggle_btn,
                "expanded": expanded,
            }
            self.bone_order.append(full_path)

        def walk(node_dict, depth=0, parent_path=None):
            for part, meta in node_dict.items():
                full = meta["__path"]
                children = meta["__children"]

                add_row(part, full, depth, bool(children), parent_path)
                walk(children, depth + 1, full)

        walk(self._bone_tree, 0, None)

        # Collapse all descendants by default
        for path, row in self.bone_rows.items():
            if row["parent"] is not None:
                row["frame"].pack_forget()

        self.update_apply_button_text()

    def on_bone_checkbox_clicked(self, bone_path: str):
        """If Shift is held, apply the same check-state to all descendants."""
        row = self.bone_rows.get(bone_path)
        if not row:
            return

        new_state = row["var"].get()

        if getattr(self, "_bone_shift_held", False):
            for child in self._descendants(bone_path):
                if child in self.bone_rows:
                    self.bone_rows[child]["var"].set(new_state)

        self.update_apply_button_text()

    def _direct_children(self, parent_path: str):
        parent_depth = self.bone_rows[parent_path]["depth"]
        prefix = parent_path + "|"
        out = []
        for p in self.bone_order:
            if not p.startswith(prefix):
                continue
            if self.bone_rows[p]["depth"] == parent_depth + 1:
                out.append(p)
        return out


    def _next_non_descendant_visible_frame(self, parent_path: str):
        """
        Find the next visible frame AFTER parent_path in bone_order that is NOT a descendant.
        Used to insert children in the correct visual position (fixes ordering bug).
        """
        parent_idx = self.bone_order.index(parent_path)
        prefix = parent_path + "|"

        for i in range(parent_idx + 1, len(self.bone_order)):
            p = self.bone_order[i]
            if p.startswith(prefix):
                continue
            # not a descendant
            fr = self.bone_rows[p]["frame"]
            if fr.winfo_manager():  # visible
                return fr
        return None


    def _show_subtree(self, parent_path: str, show_all: bool):
        """
        Show children directly under the parent, BEFORE the next sibling/ancestor row.
        If show_all=True, recursively show all descendants.
        """
        anchor = self._next_non_descendant_visible_frame(parent_path)
        parent_frame = self.bone_rows[parent_path]["frame"]

        # Insert children right after parent, in correct order
        prev = parent_frame
        for child in self._direct_children(parent_path):
            fr = self.bone_rows[child]["frame"]
            # pack AFTER prev, but BEFORE anchor (if anchor exists)
            if anchor is not None:
                fr.pack(anchor="w", fill="x", padx=6, pady=1, before=anchor)
            else:
                fr.pack(anchor="w", fill="x", padx=6, pady=1)

            # Force correct stacking by re-packing after prev if no anchor
            # (pack() keeps order; this is just safety)
            prev = fr

            if show_all:
                # mark expanded + toggle UI for nodes with children
                self.bone_rows[child]["expanded"].set(True)
                if self.bone_rows[child]["toggle"] is not None:
                    self.bone_rows[child]["toggle"].configure(text="▼")
                self._show_subtree(child, show_all=True)


    def _invert_bones(self):
        for row in self.bone_rows.values():
            row["var"].set(not row["var"].get())
        self.update_apply_button_text()

    def _descendants(self, parent_path: str):
        """Yield all descendant bone paths (not including the parent)."""
        prefix = parent_path + "|"
        for p in self.bone_order:
            if p.startswith(prefix):
                yield p


    def toggle_expand(self, bone_path: str):
        row = self.bone_rows.get(bone_path)
        if not row:
            return

        expanded_now = row["expanded"].get()
        row["expanded"].set(not expanded_now)

        # Update arrow
        if row["toggle"] is not None:
            row["toggle"].configure(text="▼" if not expanded_now else "▶")

        expand_all = getattr(self, "_bone_ctrl_held", False)

        if not expanded_now:
            # expanding
            self._show_subtree(bone_path, show_all=expand_all)
            if expand_all:
                # mark all descendants as expanded and set arrows
                for p in self._descendants(bone_path):
                    self.bone_rows[p]["expanded"].set(True)
                    if self.bone_rows[p]["toggle"] is not None:
                        self.bone_rows[p]["toggle"].configure(text="▼")
        else:
            # collapsing: hide all descendants
            for p in self._descendants(bone_path):
                self.bone_rows[p]["frame"].pack_forget()
                self.bone_rows[p]["expanded"].set(False)
                if self.bone_rows[p]["toggle"] is not None:
                    self.bone_rows[p]["toggle"].configure(text="▶")

    def _load_selected_preset(self):
        name = self.preset_var.get()
        if name == "(None)":
            return

        presets = self.settings.get("ignored_bones_presets", {})
        bones = set(presets.get(name, []))

        # Apply to visible rows; keep auto-ignored header bones intact
        for path, row in self.bone_rows.items():
            row["var"].set(path in bones)

        self.update_apply_button_text()
        self.set_status(f"Preset loaded: {name}", is_error=False)


    def _save_current_as_preset(self):
        # Ask a preset name
        win = ctk.CTkToplevel(self.bone_selection_window)
        self.apply_window_icon(win)
        win.title("Save Preset")
        self.center_window(win, 320, 140)
        self.update_theme_for_window(win)
        win.grab_set()
        win.transient(self.bone_selection_window)

        entry = ctk.CTkEntry(win, width=260, placeholder_text="Preset name...")
        entry.pack(pady=(18, 10), padx=10)

        def do_save():
            name = entry.get().strip()
            if not name:
                return

            selected_ignored = [p for p, r in self.bone_rows.items() if r["var"].get()]
            # Store ONLY real bones from this window (header bones are handled separately)
            self.settings.setdefault("ignored_bones_presets", {})[name] = selected_ignored
            self.save_settings()
            self._refresh_preset_menu()
            self.preset_var.set(name)

            try:
                win.grab_release()
            except Exception:
                pass
            win.destroy()

            self.set_status(f"Preset saved: {name}", is_error=False)

        btn = ctk.CTkButton(win, text="Save", command=do_save)
        btn.pack(pady=(0, 12))

    def _delete_selected_preset(self):
        name = self.preset_var.get()
        if name == "(None)":
            return

        presets = self.settings.get("ignored_bones_presets", {})
        if name in presets:
            del presets[name]
            self.settings["ignored_bones_presets"] = presets
            self.save_settings()
            self._refresh_preset_menu()
            self.preset_var.set("(None)")
            self.set_status(f"Preset deleted: {name}", is_error=False)

    def _select_no_bones(self):
        for row in self.bone_rows.values():
            row["var"].set(False)
        self.update_apply_button_text()


    def update_apply_button_text(self):
        if any(row["var"].get() for row in self.bone_rows.values()):
            self.apply_button.configure(text="Apply")
        else:
            self.apply_button.configure(text="Skip")


    def build_settings_frame(self):
        """Build the settings frame UI."""
        self.settings_frame = ctk.CTkFrame(self.root)
        self.settings_frame.pack_forget()

        # Back Button
        self.back_button = ctk.CTkButton(self.settings_frame, text="Back", command=self.toggle_settings)
        self.back_button.pack(anchor="nw", padx=10, pady=10)

        # Settings frame content
        ctk.CTkLabel(self.settings_frame, text="Default Export Directory:").pack(pady=10)
        self.settings_export_dir_entry = ctk.CTkEntry(self.settings_frame, width=300)
        self.settings_export_dir_entry.pack(pady=10)
        if self.settings.get("default_export_dir"):
            self.settings_export_dir_entry.insert(0, self.settings["default_export_dir"])

        # Store browse button in settings as instance variable for color updates
        self.browse_button_settings = ctk.CTkButton(self.settings_frame, text="Browse", command=self.select_default_export_directory)
        self.browse_button_settings.pack(pady=10)

        # Color theme options with new themes (Pink, Red, Yellow, Purple)
        ctk.CTkLabel(self.settings_frame, text="Color Theme:").pack(pady=(10, 6))

        self.theme_menu = ctk.CTkOptionMenu(
            self.settings_frame,
            values=list(color_themes.keys()),
            variable=self.theme_var,
            command=self.set_theme
        )
        self.theme_menu.pack(pady=(0, 10))

        self.auto_fps_toggle_button = ctk.CTkButton(
            self.settings_frame,
            text=f"Auto FPS: {'On' if self.auto_set_fps else 'Off'}",
            command=self.toggle_auto_set_fps
        )
        self.auto_fps_toggle_button.pack(pady=(5, 10))

        # Store Save button as an instance variable for color updates
        self.save_button = ctk.CTkButton(self.settings_frame, text="Save", command=self.save_export_directory)
        self.save_button.pack(pady=20)

    def create_button(self, root, text, command, anchor, padx, pady):
        button = ctk.CTkButton(root, text=text, command=command)
        button.pack(anchor=anchor, padx=padx, pady=pady)
        return button

    def toggle_settings(self):
        """Toggles between the main window and the settings window"""
        if self.main_frame.winfo_ismapped():  # If main frame is visible
            self.main_frame.pack_forget()  # Hide main frame
            self.settings_frame.pack(fill="both", expand=True, padx=20, pady=20)  # Apply padding when showing
        else:
            self.settings_frame.pack_forget()  # Hide settings frame
            self.main_frame.pack(fill="both", expand=True, **self.main_frame_padding)  # Show main frame with padding

    def update_ui_colors(self, theme_name: str):
        t = color_themes.get(theme_name, color_themes["Blue"])

        # frames
        if hasattr(self, "main_frame"):
            self.main_frame.configure(fg_color=t["frame"])
        if hasattr(self, "settings_frame"):
            self.settings_frame.configure(fg_color=t["frame"])

        # main widgets
        if hasattr(self, "fbx_label"):
            self.fbx_label.configure(text_color=t["label"])
        if hasattr(self, "status_label"):
            self.status_label.configure(bg=t["frame"])

        for wname in ("select_fbx_button", "export_all_button", "settings_button", "scale_toggle_button", "browse_button", "ignored_bones_button", "linear_toggle_button", "location_ignored_bones_button", "reverse_toggle_button"):
            w = getattr(self, wname, None)
            if not w:
                continue

            # Normal button styling
            try:
                w.configure(
                    fg_color=t["btn"],
                    hover_color=t.get("btn_hover", t["btn"]),
                    text_color=t["btn_text"],
                )
            except Exception:
                pass

            # Manual disabled styling
            try:
                if str(w.cget("state")) == "disabled":
                    w.configure(
                        fg_color=t.get("btn_disabled", "#4A4A4A"),
                        hover_color=t.get("btn_disabled", "#4A4A4A"),
                        text_color=t.get("btn_disabled_text", "#A8A8A8"),
                    )
            except Exception:
                pass

        # settings widgets
        for wname in ("back_button", "browse_button_settings", "save_button", "auto_fps_toggle_button", "theme_menu"):
            w = getattr(self, wname, None)
            if not w:
                continue

            try:
                if isinstance(w, ctk.CTkOptionMenu):
                    w.configure(
                        fg_color=t["btn"],
                        button_color=t["btn"],
                        button_hover_color=t.get("btn_hover", t["btn"]),
                        text_color=t["btn_text"],
                    )
                else:
                    w.configure(
                        fg_color=t["btn"],
                        hover_color=t.get("btn_hover", t["btn"]),
                        text_color=t["btn_text"],
                    )
            except Exception:
                pass

            try:
                if str(w.cget("state")) == "disabled":
                    if isinstance(w, ctk.CTkOptionMenu):
                        w.configure(
                            fg_color=t.get("btn_disabled", "#4A4A4A"),
                            button_color=t.get("btn_disabled", "#4A4A4A"),
                            button_hover_color=t.get("btn_disabled", "#4A4A4A"),
                            text_color=t.get("btn_disabled_text", "#A8A8A8"),
                        )
                    else:
                        w.configure(
                            fg_color=t.get("btn_disabled", "#4A4A4A"),
                            hover_color=t.get("btn_disabled", "#4A4A4A"),
                            text_color=t.get("btn_disabled_text", "#A8A8A8"),
                        )
            except Exception:
                pass

        self.root.update_idletasks()

    def _destroy_current_fbx(self):
        self.scene = None
        self.fbx_manager = None

    def select_fbx_file(self):
        """Handles the selection of an FBX file, loads animations, and retrieves bone names."""
        self.fbx_file = filedialog.askopenfilename(
            title="Select FBX File",
            filetypes=[("FBX files", "*.fbx")]
        )
        if not self.fbx_file:
            return

        try:
            # Destroy previously loaded FBX first
            self._destroy_current_fbx()

            # Close any currently open bone windows from the previous FBX
            try:
                if hasattr(self, "bone_selection_window") and self.bone_selection_window.winfo_exists():
                    self.bone_selection_window.destroy()
            except Exception:
                pass

            try:
                if hasattr(self, "location_bone_selection_window") and self.location_bone_selection_window.winfo_exists():
                    self.location_bone_selection_window.destroy()
            except Exception:
                pass

            # load_fbx_animations returns (animations, bones, scene, manager)
            animations, bone_names, scene, manager = load_fbx_animations(
                self.fbx_file,
                use_bone_paths=True
            )

            self.fbx_manager = manager
            self.animations_with_originals = animations
            self.animations = [name for _, name in animations]
            self.scene = scene
            self.bone_names = bone_names or []

            # Rebuild only FBX-specific default ignored header bones
            self.default_ignored_bones = set()
            if self.bone_names:
                parts = [p for p in self.bone_names[0].split("|") if p]
                if len(parts) >= 1:
                    self.default_ignored_bones.add(parts[0])   # RootNode
                if len(parts) >= 2:
                    self.default_ignored_bones.add(parts[1])   # Armature name

            # Keep existing user-selected ignore lists.
            # Optional: filter out paths that do not exist in the new FBX.
            valid_stripped_paths = set()
            for p in self.bone_names:
                parts = [x for x in p.split("|") if x]
                if len(parts) > 2:
                    valid_stripped_paths.add("|".join(parts[2:]))

            self.ignored_bones = {b for b in self.ignored_bones if b in valid_stripped_paths}
            self.location_ignored_bones = {b for b in self.location_ignored_bones if b in valid_stripped_paths}

            # Populate animations list
            self.anim_listbox.delete(0, tk.END)
            for _, anim_name in animations:
                self.anim_listbox.insert(tk.END, anim_name)

            self.fbx_label.configure(text=f"Loaded: {os.path.basename(self.fbx_file)}")

            if self.bone_names:
                if not self.top_right_frame.winfo_ismapped():
                    self.top_right_frame.pack(side="right", anchor="n")
                self.set_status("FBX loaded successfully.", is_error=False)
            else:
                self.set_status("No skeleton bones found.", is_error=True)
                if self.top_right_frame.winfo_ismapped():
                    self.top_right_frame.pack_forget()

        except Exception as e:
            self.set_status(f"Error loading FBX file: {e}", is_error=True, source="fbx_import")
            self.ignored_bones_button.place_forget()
            self.location_ignored_bones_button.place_forget()
            self._destroy_current_fbx()

        self._update_export_all_state()

    def apply_bone_selection(self):
        """Apply the selected bones and update the status label."""
        self.ignored_bones = {path for path, row in self.bone_rows.items() if row["var"].get()}

        self.set_status("Ready to Export!", is_error=False)

        try:
            self.bone_selection_window.destroy()
        except Exception:
            pass
        self.root.lift()

    def center_window(self, window, width, height):
        """Center a window relative to the main root window."""
        self.root.update_idletasks()  # Update root window dimensions
        x = self.root.winfo_x() + (self.root.winfo_width() // 2) - (width // 2)
        y = self.root.winfo_y() + (self.root.winfo_height() // 2) - (height // 2)
        window.geometry(f"{width}x{height}+{x}+{y}")

    def update_theme_for_window(self, window):
        t = color_themes.get(self.settings.get("theme", "Blue"), color_themes["Blue"])

        try:
            window.configure(fg_color=t["frame"])
        except Exception:
            pass

        def walk(w):
            try:
                if isinstance(w, ctk.CTkLabel):
                    w.configure(text_color=t["label"])

                elif isinstance(w, ctk.CTkButton):
                    # Normal button styling
                    w.configure(
                        fg_color=t["btn"],
                        hover_color=t.get("btn_hover", t["btn"]),
                        text_color=t["btn_text"],
                    )
                    # Manual disabled styling (because some CTk versions don't support disabled_color args)
                    try:
                        if str(w.cget("state")) == "disabled":
                            w.configure(
                                fg_color=t.get("btn_disabled", "#4A4A4A"),
                                hover_color=t.get("btn_disabled", "#4A4A4A"),
                                text_color=t.get("btn_disabled_text", "#A8A8A8"),
                            )
                    except Exception:
                        pass

                elif isinstance(w, ctk.CTkCheckBox):
                    w.configure(
                        fg_color=t["btn"],
                        text_color=t["btn_text"]
                    )

                elif isinstance(w, ctk.CTkOptionMenu):
                    # OptionMenu uses button_color/button_hover_color for the clickable part
                    w.configure(
                        fg_color=t["btn"],
                        button_color=t["btn"],
                        button_hover_color=t.get("btn_hover", t["btn"]),
                        text_color=t["btn_text"],
                    )
                    # Manual disabled styling if supported by your CTk version
                    try:
                        if str(w.cget("state")) == "disabled":
                            w.configure(
                                fg_color=t.get("btn_disabled", "#4A4A4A"),
                                button_color=t.get("btn_disabled", "#4A4A4A"),
                                button_hover_color=t.get("btn_disabled", "#4A4A4A"),
                                text_color=t.get("btn_disabled_text", "#A8A8A8"),
                            )
                    except Exception:
                        pass

                elif isinstance(w, ctk.CTkEntry):
                    w.configure(text_color=t["label"])

                elif isinstance(w, (ctk.CTkFrame, ctk.CTkScrollableFrame)):
                    w.configure(fg_color=t["frame"])

            except Exception:
                pass

            # recurse
            try:
                for child in w.winfo_children():
                    walk(child)
            except Exception:
                pass

        walk(window)

        # Special case: if presets toggle exists, force its correct color immediately
        if hasattr(self, "presets_toggle_btn") and self.presets_toggle_btn.winfo_exists():
            if getattr(self, "preset_panel_open", False):
                self.presets_toggle_btn.configure(fg_color=t["frame"])
            else:
                self.presets_toggle_btn.configure(fg_color=t["btn"])
        if hasattr(self, "location_presets_toggle_btn") and self.location_presets_toggle_btn.winfo_exists():
            if getattr(self, "location_preset_panel_open", False):
                self.location_presets_toggle_btn.configure(fg_color=t["frame"])
            else:
                self.location_presets_toggle_btn.configure(fg_color=t["btn"])
                
        window.update_idletasks()

    def show_context_menu(self, event):
        try:
            self.selected_animation_index = self.anim_listbox.nearest(event.y)
            self.anim_listbox.selection_clear(0, tk.END)
            self.anim_listbox.selection_set(self.selected_animation_index)
            self.context_menu.post(event.x_root, event.y_root)
        except IndexError:
            pass

    def rename_animation(self):
        sel = self.anim_listbox.curselection()
        if not sel:
            self.set_status("Select an animation first.", is_error=True)
            return
        index = sel[0]

        original_display_name = self.anim_listbox.get(index)

        rename_window = ctk.CTkToplevel(self.root)
        rename_window.title("Rename Animation")
        self.center_window(rename_window, 360, 180)

        self.update_theme_for_window(rename_window)
        rename_window.grab_set()
        rename_window.transient(self.root)
        self.apply_window_icon(rename_window)

        entry_box = ctk.CTkEntry(rename_window, width=300)
        entry_box.insert(0, original_display_name)
        entry_box.pack(pady=20)


        def commit_rename():
            new_name = entry_box.get().strip()
            if not new_name:
                self.set_status("Name cannot be empty.", is_error=True)
                return

            # Update listbox
            self.anim_listbox.delete(index)
            self.anim_listbox.insert(index, new_name)

            # Update internal lists
            if 0 <= index < len(self.animations):
                self.animations[index] = new_name

            # Keep ORIGINAL stack name, replace only display name
            if 0 <= index < len(self.animations_with_originals):
                original_stack = self.animations_with_originals[index][0]
                self.animations_with_originals[index] = (original_stack, new_name)

            self.set_status(f"Animation renamed to: {new_name}", is_error=False)

            try:
                rename_window.grab_release()
            except Exception:
                pass
            rename_window.destroy()

        def cancel():
            try:
                rename_window.grab_release()
            except Exception:
                pass
            rename_window.destroy()

        btn_row = ctk.CTkFrame(rename_window, fg_color=None)
        btn_row.pack(pady=10, padx=10, fill="x")

        ctk.CTkButton(btn_row, text="Cancel", command=cancel).pack(side="left", padx=5)
        ctk.CTkButton(btn_row, text="Rename", command=commit_rename).pack(side="right", padx=5)

    def delete_animation(self):
        sel = self.anim_listbox.curselection()
        if not sel:
            self.set_status("Select an animation first.", is_error=True)
            return

        index = sel[0]
        del self.animations[index]
        del self.animations_with_originals[index]
        self.anim_listbox.delete(index)
        self.set_status("Animation deleted.", is_error=False)


    def export_single_animation(self):
        sel = self.anim_listbox.curselection()
        if not sel:
            self.set_status("Select an animation first.", is_error=True)
            return

        idx = sel[0]
        display_name = self.anim_listbox.get(idx)

        # Find original stack name
        anim_stack = None
        for stack_name, disp in self.animations_with_originals:
            if disp == display_name:
                anim_stack = stack_name
                break

        if not anim_stack:
            self.set_status("Error: Animation stack not found.", is_error=True)
            return

        save_path = filedialog.asksaveasfilename(
            defaultextension=".anim",
            filetypes=[("Anim files", "*.anim")],
            initialfile=f"{display_name}.anim"
        )
        if not save_path:
            self.set_status("Export canceled.", is_error=True)
            return

        export_anim(
            anim_stack,
            save_path,
            self.scene,
            ignored_bones=self._ignored_bone_names_for_export(),
            location_ignored_bones=self._location_ignored_bone_names_for_export(),
            write_scale=self.write_scale,
            use_linear_reduction=self.use_linear_reduction,
            auto_set_fps=self.auto_set_fps,
            reverse_animation=self.reverse_animation,
        )


        self.set_status(f"Exported {display_name}\n{save_path}", is_error=False)

    def export_all_animations_handler(self):
        if not self.scene:
            self.set_status("Error: No FBX file loaded!", is_error=True)
            return

        export_dir = self._get_export_dir()
        if not export_dir or not os.path.isdir(export_dir):
            self.set_status("Error: Please select a valid export directory!", is_error=True)
            return

        os.makedirs(export_dir, exist_ok=True)

        export_all_anims(
            self.animations_with_originals,
            export_dir,
            self.scene,
            ignored_bones=self._ignored_bone_names_for_export(),
            location_ignored_bones=self._location_ignored_bone_names_for_export(),
            write_scale=self.write_scale,
            use_linear_reduction=self.use_linear_reduction,
            auto_set_fps=self.auto_set_fps,
        )

        self.set_status("All animations exported successfully!", is_error=False)

    def select_export_directory(self):
        self.export_dir = filedialog.askdirectory(title="Select Custom Export Directory")
        if self.export_dir:
            self.export_dir_entry.delete(0, tk.END)
            self.export_dir_entry.insert(0, self.export_dir)
            self.set_status(f"Custom export directory set to: {self.export_dir}")
            self._update_export_all_state()

    def select_default_export_directory(self):
        """Browse for a default export directory but do NOT save until user clicks Save."""
        chosen = filedialog.askdirectory(title="Select Default Export Directory")
        if chosen:
            self.settings_export_dir_entry.delete(0, tk.END)
            self.settings_export_dir_entry.insert(0, chosen)
            self.set_status(f"Default export directory selected (not saved yet).", is_error=False)

    def save_export_directory(self):
        """Save default export directory from the settings entry."""
        path = self.settings_export_dir_entry.get().strip()
        self.settings["default_export_dir"] = path
        self.save_settings()
        self._update_export_all_state()
        self.set_status(f"Default export folder saved: {path}", is_error=False)


    def save_settings(self):
        self.settings["window_position"] = f"{self.root.winfo_x()}x{self.root.winfo_y()}"

        with open(settings_file, 'w') as f:
            json.dump(self.settings, f, indent=4)

    def apply_saved_theme(self):
        self.set_theme(self.settings.get("theme", "Blue"))

    def set_theme(self, theme_name: str):
        if theme_name not in color_themes:
            theme_name = "Blue"

        self.theme_var.set(theme_name)
        self.settings["theme"] = theme_name

        # Let the OptionMenu finish updating itself first
        self.root.after_idle(lambda: self.update_ui_colors(theme_name))

        self.save_settings()
        
    def _ignored_bone_names_for_export(self):
        all_ignored = set(self.default_ignored_bones or set()) | set(self.ignored_bones or set())
        return {b.split("|")[-1] for b in all_ignored if b}

    def _location_ignored_bone_names_for_export(self):
        # location_ignored_bones may contain paths like "Root|Spine|Face"
        # exporter compares against node.GetName() so we pass only leaf names
        return {b.split("|")[-1] for b in (self.location_ignored_bones or set()) if b}


# Set up the main Tkinter window
root = ctk.CTk()

# Override the close button to ensure it properly closes the app
def on_closing():
    try:
        app.save_settings()
    except Exception:
        pass

    # Close any child windows first
    for win_name in (
        "bone_selection_window",
        "location_bone_selection_window",
    ):
        try:
            win = getattr(app, win_name, None)
            if win is not None and win.winfo_exists():
                try:
                    win.grab_release()
                except Exception:
                    pass
                win.destroy()
        except Exception:
            pass

    # Do NOT manually destroy FBX manager on app exit
    # Let process shutdown clean it up
    app.scene = None
    app.fbx_manager = None

    root.destroy()

root.protocol("WM_DELETE_WINDOW", on_closing)

app = FBXToAnimConverterApp(root)
root.mainloop()
