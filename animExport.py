import os

from fbx import (
    FbxAnimLayer,
    FbxAnimStack,
    FbxCriteria,
    FbxNode,
    FbxSkeleton,
    FbxTime,
)

# ----------------------------
# Small utilities
# ----------------------------

def get_fbx_time_mode(scene):
    return scene.GetGlobalSettings().GetTimeMode()

def fbx_time_to_frame(t, scene, auto_set_fps=True):
    if auto_set_fps:
        # True behavior: respect FBX scene framerate
        return int(t.GetFrameCount(get_fbx_time_mode(scene)))

    # Feature behavior: force conversion to 25 fps
    if hasattr(FbxTime, "ePAL"):
        return int(t.GetFrameCount(FbxTime.ePAL))

    # If this FBX binding lacks ePAL, fall back to raw time conversion
    # using seconds so the scaling feature still works.
    seconds = t.GetSecondDouble()
    return int(round(seconds * 30.0))

def dedupe_same_frame(keys):
    by_frame = {}
    for k in keys:
        by_frame[int(k["time"])] = k  # keeps last
    return sorted(by_frame.values(), key=lambda k: k["time"])

def simplify_linear_keys(keys, epsilon=1e-6):
    """
    Removes middle keys that lie on a straight line.
    Expects keys shaped like:
        {"time": ..., "value": ...}
    Preserves the original dicts.
    """
    if len(keys) <= 2:
        return keys

    simplified = [keys[0]]

    for i in range(1, len(keys) - 1):
        prev = simplified[-1]
        curr = keys[i]
        next_k = keys[i + 1]

        f0, v0 = float(prev["time"]), float(prev["value"])
        f1, v1 = float(curr["time"]), float(curr["value"])
        f2, v2 = float(next_k["time"]), float(next_k["value"])

        # Avoid divide-by-zero / duplicate-time weirdness
        if abs(f2 - f0) <= 1e-12:
            simplified.append(curr)
            continue

        t = (f1 - f0) / (f2 - f0)
        expected = v0 + (v2 - v0) * t

        if abs(v1 - expected) > epsilon:
            simplified.append(curr)

    simplified.append(keys[-1])
    return simplified

def collapse_flat_channel(axis_keys, start_time, flat_tolerance=0.045):
    """
    Collapse the whole channel to the animation start frame if every key
    stays within ±flat_tolerance of the first value.

    Example:
      base = 90.0
      flat_tolerance = 0.035

      Allowed range:
        89.965 to 90.035
    """
    if len(axis_keys) <= 1:
        return axis_keys

    base_value = float(axis_keys[0]["value"])

    for k in axis_keys[1:]:
        if abs(float(k["value"]) - base_value) > flat_tolerance:
            return axis_keys

    return [{
        "time": start_time,
        "value": base_value,
        "curve": axis_keys[0]["curve"],
    }]

def collapse_constant_channel(axis_keys, start_time, tolerance=1e-5):
    """
    Collapse the whole channel to the animation start frame if every key
    stays within ±tolerance of the first value.
    Good for nearly constant location channels with tiny float wobble.
    """
    if len(axis_keys) <= 1:
        return axis_keys

    base_value = float(axis_keys[0]["value"])

    for k in axis_keys[1:]:
        if abs(float(k["value"]) - base_value) > tolerance:
            return axis_keys

    return [{
        "time": start_time,
        "value": base_value,
        "curve": axis_keys[0]["curve"],
    }]

def collapse_nearly_constant_channel(axis_keys, start_time, epsilon=1e-6):
    """
    Collapse to animation start frame if every key is essentially identical
    to the first value within a very strict epsilon.
    Safe for all channel types.
    """
    if len(axis_keys) <= 1:
        return axis_keys

    base_value = float(axis_keys[0]["value"])

    for k in axis_keys[1:]:
        if abs(float(k["value"]) - base_value) > epsilon:
            return axis_keys

    return [{
        "time": start_time,
        "value": base_value,
        "curve": axis_keys[0]["curve"],
    }]

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

def extract_keyframe_data_from_node(node: FbxNode, anim_layer: FbxAnimLayer, scene, auto_set_fps=True):
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
                    "time": fbx_time_to_frame(key.GetTime(), scene, auto_set_fps=auto_set_fps),
                    "value": key.GetValue(),
                }
            )

    return keyframe_data


def get_skeleton_bones_with_keyframes(anim_stack: FbxAnimStack, scene, ignored_bones, auto_set_fps=True):
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

        keyframes = extract_keyframe_data_from_node(node, anim_layer, scene, auto_set_fps=auto_set_fps)
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
    location_ignored_bones=None,
    write_scale=True,
    use_linear_reduction=True,
    auto_set_fps=True,
    reverse_animation=False,
    rotation_linear_epsilon=3e-3,
):
    """
    Export a single FBX AnimStack to a Maya .anim file.

    Notes:
    - Skeleton-only export (no meshes/nulls/cameras).
    - Keys are shifted so animation starts at frame 1.
    """

    print(f"Exporting animation: {anim_original} to {save_path}")
    ignored_bones = ignored_bones or set()
    location_ignored_bones = location_ignored_bones or set()

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

    bones = get_skeleton_bones_with_keyframes(anim_stack, scene, ignored_bones, auto_set_fps=auto_set_fps)
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

            transforms = ["translate", "rotate"]
            if write_scale:
                transforms.append("scale")

            for transform in transforms:
                if transform == "translate" and bone_name in location_ignored_bones:
                    continue

                for axis in ("X", "Y", "Z"):
                    curve_name = f"{transform}{axis}"  # e.g. translateX
                    axis_keys = [k for k in keyframes if k["curve"] == curve_name]
                    if not axis_keys:
                        continue

                    # Sort (FBX can sometimes return out of order)
                    axis_keys.sort(key=lambda k: k["time"])
                    axis_keys = dedupe_same_frame(axis_keys)

                    if reverse_animation:
                        axis_keys = reverse_axis_keys(axis_keys, start_time, end_time)

                    if use_linear_reduction:
                        if transform in ("translate", "scale"):
                            axis_keys = collapse_constant_channel(axis_keys, start_time, tolerance=1e-5)

                        elif transform == "rotate":
                            axis_keys = collapse_flat_channel(axis_keys, start_time, flat_tolerance=0.11)
                        if len(axis_keys) > 2:
                            if transform == "translate":
                                linear_epsilon = 1e-6
                            elif transform == "rotate":
                                linear_epsilon = rotation_linear_epsilon

                            while True:
                                new_axis_keys = simplify_linear_keys(axis_keys, epsilon=linear_epsilon)
                                if len(new_axis_keys) == len(axis_keys):
                                    break
                                axis_keys = new_axis_keys
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


def export_all_animations(
    animations,
    export_dir,
    scene,
    ignored_bones=set(),
    location_ignored_bones=set(),
    write_scale=True,
    use_linear_reduction=True,
    auto_set_fps=True,
    reverse_animation=False,
    rotation_linear_epsilon=3e-3,
):
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
            location_ignored_bones=location_ignored_bones,
            write_scale=write_scale,
            use_linear_reduction=use_linear_reduction,
            auto_set_fps=auto_set_fps,
            reverse_animation=reverse_animation,
            rotation_linear_epsilon=rotation_linear_epsilon,
        )

def reverse_axis_keys(axis_keys, start_time, end_time):
    """
    Reverse key timing across the animation span.
    Example:
      start=0, end=20
      key at 3 becomes 17
      key at 20 becomes 0
    """
    reversed_keys = []
    for k in axis_keys:
        reversed_keys.append({
            "time": start_time + end_time - int(k["time"]),
            "value": k["value"],
            "curve": k["curve"],
        })
    reversed_keys.sort(key=lambda x: x["time"])
    return dedupe_same_frame(reversed_keys)