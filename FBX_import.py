import re
from fbx import (
    FbxManager, FbxScene, FbxImporter,
    FbxAnimStack, FbxCriteria,
    FbxSkeleton
)

def clean_animation_name(name: str) -> str:
    """
    1) Remove everything before and including the first '|'
    2) Remove illegal filename characters (Windows-safe)
    3) Collapse whitespace and trim
    """
    # Step 1: remove prefix before '|'
    cleaned = name.split("|", 1)[-1] if "|" in name else name

    # Step 2: remove illegal filename chars (Windows)
    # Illegal: \ / : * ? " < > |  and control chars
    cleaned = re.sub(r'[\\/:*?"<>|]', "", cleaned)
    cleaned = re.sub(r"[\x00-\x1f]", "", cleaned)  # control chars

    # Optional: remove punctuation you dislike (you mentioned "!" etc)
    # If you want to keep underscores/dashes, this is safe:
    cleaned = re.sub(r"[!]+", "", cleaned)

    # Step 3: normalize whitespace
    cleaned = re.sub(r"\s+", " ", cleaned).strip()

    # Windows edge cases: no trailing dots/spaces
    cleaned = cleaned.rstrip(" .")

    # fallback if name becomes empty
    return cleaned or "Anim"

def _is_skeleton_node(node) -> bool:
    """Robust skeleton detection for Python FBX bindings."""
    attr = node.GetNodeAttribute()
    if not attr:
        return False

    # Most reliable across bindings:
    if isinstance(attr, FbxSkeleton):
        return True

    # Fallback (some bindings don't play nice with isinstance):
    try:
        return attr.GetClassId().Is(FbxSkeleton.ClassId)
    except Exception:
        return False

def _collect_bone_paths(node, parent_path, out_paths):
    """Collect full bone paths like Root|Spine|Arm."""
    name = node.GetName()
    current_path = f"{parent_path}|{name}" if parent_path else name

    if _is_skeleton_node(node):
        out_paths.append(current_path)

    for i in range(node.GetChildCount()):
        _collect_bone_paths(node.GetChild(i), current_path, out_paths)

def _collect_bone_names(node, out_names):
    """Collect flat bone names only."""
    if _is_skeleton_node(node):
        out_names.append(node.GetName())

    for i in range(node.GetChildCount()):
        _collect_bone_names(node.GetChild(i), out_names)

def load_fbx_animations(fbx_file: str, use_bone_paths: bool = True):
    """
    Returns:
      animations_with_originals: List[(original_stack_name, cleaned_display_name)]
      bones: List[str] (paths if use_bone_paths else names)
      scene: FbxScene
      manager: FbxManager  (caller must Destroy() it when done)
    """
    manager = FbxManager.Create()
    importer = FbxImporter.Create(manager, "")
    scene = FbxScene.Create(manager, "Scene")

    if not importer.Initialize(fbx_file, -1, manager.GetIOSettings()):
        importer.Destroy()
        manager.Destroy()
        raise Exception(f"Failed to initialize FBX importer for file: {fbx_file}")

    if not importer.Import(scene):
        importer.Destroy()
        manager.Destroy()
        raise Exception(f"Failed to import FBX file: {fbx_file}")

    importer.Destroy()

    # Animation stacks
    anim_stack_count = scene.GetSrcObjectCount(FbxCriteria.ObjectType(FbxAnimStack.ClassId))
    animations_with_originals = []
    for i in range(anim_stack_count):
        anim_stack = scene.GetSrcObject(FbxCriteria.ObjectType(FbxAnimStack.ClassId), i)
        original_name = anim_stack.GetName()
        cleaned_name = clean_animation_name(original_name)
        animations_with_originals.append((original_name, cleaned_name))

    # Bones
    bones = []
    root = scene.GetRootNode()
    if root:
        if use_bone_paths:
            _collect_bone_paths(root, "", bones)
        else:
            _collect_bone_names(root, bones)

    return animations_with_originals, bones, scene, manager
