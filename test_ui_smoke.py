import ast
from pathlib import Path
import tempfile
import os
import tkinter as tk

source = Path(__file__).with_name(".anim_Creator.py")
tree = ast.parse(source.read_text(encoding="utf-8"))
definitions = []
for node in tree.body:
    if isinstance(node, ast.Assign) and any(isinstance(t, ast.Name) and t.id == "root" for t in node.targets):
        break
    definitions.append(node)
scope = {"__file__": str(source)}
exec(compile(ast.Module(body=definitions, type_ignores=[]), str(source), "exec"), scope)
with tempfile.TemporaryDirectory() as directory:
    previous = os.getcwd()
    root = None
    try:
        os.chdir(directory)
        scope["settings_file"] = Path(directory) / "settings.json"
        root = scope["ctk"].CTk()
        root.withdraw()
        app = scope["FBXToAnimConverterApp"](root)
        app.main_frame.pack_forget()
        app.settings_frame.pack(fill="both", expand=True, padx=20, pady=20)
        root.update_idletasks()
        assert isinstance(app.settings_frame, scope["ctk"].CTkScrollableFrame)
        assert app.settings_frame._parent_frame.winfo_reqheight() <= 590
        app.use_cubic_curves.set(True)
        app.save_export_directory()
        assert app.settings["use_cubic_curves"] is True
        assert app.rotation_linear_epsilon == .003
        print("PASS hidden UI settings layout and persistence smoke test")
    finally:
        if root is not None:
            root.destroy()
        os.chdir(previous)
