import os

from fbx import (
    FbxAnimLayer,
    FbxAnimStack,
    FbxCriteria,
    FbxNode,
    FbxTime,
    FbxSkeleton,
)

# ----------------------------
# Small utilities
# ----------------------------

def get_fbx_time_mode(scene):
    return scene.GetGlobalSettings().GetTimeMode()

def fbx_time_to_frame(t, scene):
    # Correct conversion according to the FBX's own time mode
    return int(t.GetFrameCount(get_fbx_time_mode(scene)))

def dedupe_same_frame(keys):
    by_frame = {}
    for k in keys:
        by_frame[int(k["time"])] = k  # keeps last
    return sorted(by_frame.values(), key=lambda k: k["time"])

def simplify_axis_keys(axis_keys, value_epsilon=1e-6):
    """
    Remove redundant keys while preserving held poses.

    Keeps:
      - first key
      - last key
      - the last key before a value change
      - the first key after a value change

    Example:
      A A A B B  ->  A A B B
    so the value holds correctly until the change.
    """
    if len(axis_keys) <= 2:
        return axis_keys

    simplified = [axis_keys[0]]

    for i in range(1, len(axis_keys) - 1):
        prev_val = float(axis_keys[i - 1]["value"])
        curr_val = float(axis_keys[i]["value"])
        next_val = float(axis_keys[i + 1]["value"])

        changed_from_prev = abs(curr_val - prev_val) > value_epsilon
        changes_to_next = abs(curr_val - next_val) > value_epsilon

        # Keep transition boundaries:
        # - first key of new value
        # - last key of old value
        if changed_from_prev or changes_to_next:
            simplified.append(axis_keys[i])

    simplified.append(axis_keys[-1])
    return simplified

def get_transform_key(transform: str, axis: str) -> int:
    """
    Map transform+axis to Maya .anim channel index.

    translateX = 0, translateY = 1, translateZ = 2
    rotateX    = 3, rotateY    = 4, rotateZ    = 5
    scaleX     = 6, scaleY     = 7, scaleZ     = 8
    """
    key_map = {
        "translate": {"X": 0, "Y": 1, "Z": 2},
        "rotate": {"X": 3, "Y": 4, "Z": 5},
        "scale": {"X": 6, "Y": 7, "Z": 8},
    }
    return key_map[transform][axis]


def time_unit_from_fps(fps: int) -> str:
    """Best-effort mapping of FPS to Maya .anim timeUnit."""
    mapping = {
        15: "game",
        24: "film",
        25: "pal",
        30: "ntsc",
        48: "show",
        50: "palf",
        60: "ntscf",
    }
    return mapping.get(int(fps), "pal")


def is_skeleton_node(node: FbxNode) -> bool:
    """Robust skeleton detection for Python FBX bindings."""
    if not node:
        return False

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


# ----------------------------
# Keyframe extraction (skeleton-only, node-safe)
# ----------------------------

def extract_keyframe_data_from_node(node: FbxNode, anim_layer: FbxAnimLayer, scene):
    """Extract keyframes from LclTranslation/LclRotation/LclScaling curves."""
    keyframe_data = []

    anim_curves = {
        "translateX": node.LclTranslation.GetCurve(anim_layer, "X"),
        "translateY": node.LclTranslation.GetCurve(anim_layer, "Y"),
        "translateZ": node.LclTranslation.GetCurve(anim_layer, "Z"),
        "rotateX": node.LclRotation.GetCurve(anim_layer, "X"),
        "rotateY": node.LclRotation.GetCurve(anim_layer, "Y"),
        "rotateZ": node.LclRotation.GetCurve(anim_layer, "Z"),
        "scaleX": node.LclScaling.GetCurve(anim_layer, "X"),
        "scaleY": node.LclScaling.GetCurve(anim_layer, "Y"),
        "scaleZ": node.LclScaling.GetCurve(anim_layer, "Z"),
    }

    for curve_name, curve in anim_curves.items():
        if not curve:
            continue

        for i in range(curve.KeyGetCount()):
            key = curve.KeyGet(i)
            keyframe_data.append(
                {
                    "curve": curve_name,
                    # Store as 0-based in target fps here; export adds +1 so Maya starts at 1
                    "time": fbx_time_to_frame(key.GetTime(), scene),
                    "value": key.GetValue(),
                }
            )

    return keyframe_data


def get_skeleton_bones_with_keyframes(anim_stack: FbxAnimStack, scene, ignored_bones):
    """Return list of (node, keyframes) for skeleton nodes with any keys."""
    ignored_bones = ignored_bones or set()

    results = []
    anim_layer = anim_stack.GetMember(FbxAnimLayer.ClassId, 0)
    if not anim_layer:
        return results

    node_count = scene.GetSrcObjectCount(FbxCriteria.ObjectType(FbxNode.ClassId))
    for i in range(node_count):
        node = scene.GetSrcObject(FbxCriteria.ObjectType(FbxNode.ClassId), i)
        if not node:
            continue

        if not is_skeleton_node(node):
            continue

        bone_name = node.GetName()
        if bone_name in ignored_bones:
            continue

        keyframes = extract_keyframe_data_from_node(node, anim_layer, scene)
        if keyframes:
            results.append((node, keyframes))

    return results


# ----------------------------
# Export
# ----------------------------

def export_single_animation(
    anim_original: str,
    save_path: str,
    scene,
    ignored_bones=None,
):
    """
    Export a single FBX AnimStack to a Maya .anim file.

    Notes:
    - Skeleton-only export (no meshes/nulls/cameras).
    - Keys are shifted so animation starts at frame 1.
    """

    print(f"Exporting animation: {anim_original} to {save_path}")
    ignored_bones = ignored_bones or set()

    # Find animation stack by exact name
    anim_stack = None
    count = scene.GetSrcObjectCount(FbxCriteria.ObjectType(FbxAnimStack.ClassId))
    for i in range(count):
        stack = scene.GetSrcObject(FbxCriteria.ObjectType(FbxAnimStack.ClassId), i)
        if stack and stack.GetName() == anim_original:
            anim_stack = stack
            break

    if not anim_stack:
        print(f"Animation stack {anim_original} not found.")
        return

    bones = get_skeleton_bones_with_keyframes(anim_stack, scene, ignored_bones)
    if not bones:
        print("No animated skeleton bones found.")
        return

    # Collect all key times (0-based) to compute end
    all_key_times = [kf["time"] for _, keys in bones for kf in keys]

    if all_key_times:
        start_time = min(all_key_times)
        end_time = max(all_key_times)
    else:
        start_time = 0
        end_time = 0

    # Write .anim
    with open(save_path, "w", encoding="utf-8") as f:
        f.write("animVersion 1.1;\n")
        f.write("mayaVersion 2025;\n")
        f.write(f"timeUnit pal;\n")
        f.write("linearUnit cm;\n")
        f.write("angularUnit deg;\n")
        f.write(f"startTime {start_time};\n")
        f.write(f"endTime {end_time};\n")

        for node, keyframes in bones:
            bone_name = node.GetName()
            child_count = node.GetChildCount()

            for transform in ("translate", "rotate", "scale"):
                for axis in ("X", "Y", "Z"):
                    curve_name = f"{transform}{axis}"  # e.g. translateX
                    axis_keys = [k for k in keyframes if k["curve"] == curve_name]
                    if not axis_keys:
                        continue

                    # Sort (FBX can sometimes return out of order)
                    axis_keys.sort(key=lambda k: k["time"])
                    axis_keys = dedupe_same_frame(axis_keys)
                    axis_keys = simplify_axis_keys(axis_keys, value_epsilon=1e-6)

                    if not axis_keys:
                        continue


                    # Channel header
                    f.write(
                        f"anim {transform}.{curve_name} {curve_name} {bone_name} 0 {child_count} {get_transform_key(transform, axis)};\n"
                    )
                    f.write("animData {\n")
                    f.write("  input time;\n")
                    f.write("  output linear;\n")
                    f.write("  weighted 0;\n")
                    f.write("  preInfinity constant;\n")
                    f.write("  postInfinity constant;\n")
                    f.write("  keys {\n")

                    for idx, kf in enumerate(axis_keys):
                        time_exact = int(kf["time"])   # <- no shift
                        value = kf["value"]

                        # Safe integer formatting
                        if isinstance(value, float) and value.is_integer():
                            value = int(value)

                        if idx == 0:
                            f.write(f"    {time_exact} {value} fixed fixed 1 0 0 0 1 0 1;\n")
                        else:
                            f.write(f"    {time_exact} {value} linear linear 1 0 0;\n")


                    f.write("  }\n")
                    f.write("}\n")

    print(f"Animation {anim_original} exported successfully.")


def export_all_animations(animations, export_dir, scene, ignored_bones=set()):
    """
    animations can be:
      - list[str] of original stack names (legacy)
      - list[tuple[str,str]] of (original_stack, display_name) (new)
    """
    if not os.path.exists(export_dir):
        os.makedirs(export_dir)

    for item in animations:
        if isinstance(item, (tuple, list)) and len(item) >= 2:
            original_stack, display_name = item[0], item[1]
        else:
            original_stack, display_name = item, item

        save_path = os.path.join(export_dir, f"{display_name}.anim")
        export_single_animation(
            original_stack,
            save_path,
            scene,
            ignored_bones=ignored_bones,
        )

