"""Cubic .anim export for Toolbox's direct graph importer."""
import math
import os
from fbx import FbxAnimLayer, FbxAnimStack, FbxCriteria, FbxNode, FbxTime
from curveFit import fit

MARKER = "// toolboxCurveGraph 1"


def evaluate(curve, time):
    result = curve.Evaluate(time)
    return float(result[0] if isinstance(result, tuple) else result)


def graph_keys(curve, fps):
    """Read independent FBX slopes (per second) as per-frame Hermite slopes."""
    keys = []
    for i in range(curve.KeyGetCount()):
        time = curve.KeyGetTime(i).GetSecondDouble()*fps
        keys.append({"time": time, "value": float(curve.KeyGetValue(i)),
                     "in": float(curve.KeyGetLeftDerivative(i))/fps,
                     "out": float(curve.KeyGetRightDerivative(i))/fps})
    # Prove the extracted polynomial agrees with the SDK evaluator at subframes.
    # Weighted/constant-next curves need a different representation; don't silently flatten them.
    from curveFit import polynomial, at
    for a, b in zip(keys, keys[1:]):
        p = polynomial(a, b)
        for u in (0.125, 0.25, 0.5, 0.75, 0.875):
            t = FbxTime()
            t.SetSecondDouble((a["time"]+u*(b["time"]-a["time"]))/fps)
            expected = evaluate(curve, t)
            if abs(at(p, u)-expected) > max(1e-5, abs(expected)*2e-6):
                raise ValueError("This FBX curve uses interpolation not representable by "
                                 "unweighted cubic tangents. Bake it in Blender first.")
    return keys


def export_graph(anim_original, save_path, scene, ignored_bones=None,
                 location_ignored_bones=None, write_scale=True,
                 use_linear_reduction=True, auto_set_fps=True,
                 reverse_animation=False, rotation_linear_epsilon=0.003):
    from animExport import is_skeleton_node, get_transform_key
    ignored_bones = ignored_bones or set()
    location_ignored_bones = location_ignored_bones or set()
    if not math.isfinite(rotation_linear_epsilon) or rotation_linear_epsilon <= 0:
        raise ValueError("Rotation tolerance must be finite and greater than zero.")
    stack = next((scene.GetSrcObject(FbxCriteria.ObjectType(FbxAnimStack.ClassId), i)
                  for i in range(scene.GetSrcObjectCount(FbxCriteria.ObjectType(FbxAnimStack.ClassId)))
                  if scene.GetSrcObject(FbxCriteria.ObjectType(FbxAnimStack.ClassId), i).GetName()
                  == anim_original), None)
    if stack is None:
        raise ValueError("Animation stack not found: " + anim_original)
    if stack.GetMemberCount(FbxAnimLayer.ClassId) != 1:
        raise ValueError("Bake multiple FBX animation layers before cubic export.")
    layer = stack.GetMember(FbxAnimLayer.ClassId, 0)
    fps = FbxTime.GetFrameRate(scene.GetGlobalSettings().GetTimeMode()) if auto_set_fps else 25.0
    if not math.isfinite(fps) or fps <= 0:
        fps = scene.GetGlobalSettings().GetCustomFrameRate()
    if not math.isfinite(fps) or fps <= 0:
        raise ValueError("FBX scene has no valid frame rate.")
    channels = []
    for i in range(scene.GetSrcObjectCount(FbxCriteria.ObjectType(FbxNode.ClassId))):
        node = scene.GetSrcObject(FbxCriteria.ObjectType(FbxNode.ClassId), i)
        if not is_skeleton_node(node) or node.GetName() in ignored_bones:
            continue
        for transform, prop in (("translate", node.LclTranslation),
                                ("rotate", node.LclRotation), ("scale", node.LclScaling)):
            if transform == "scale" and not write_scale:
                continue
            if transform == "translate" and node.GetName() in location_ignored_bones:
                continue
            for axis in "XYZ":
                curve = prop.GetCurve(layer, axis)
                if curve and curve.KeyGetCount():
                    keys = graph_keys(curve, fps)
                    channels.append((node.GetName(), transform, axis, keys))
    if not channels:
        raise ValueError("No animated skeleton channels.")
    start = min(keys[0]["time"] for _, _, _, keys in channels)
    end = max(keys[-1]["time"] for _, _, _, keys in channels)
    # Validate everything before opening the destination.
    prepared = []
    for bone, transform, axis, keys in channels:
        if reverse_animation:
            keys = [dict(k, time=start+end-k["time"], **{"in": -k["out"], "out": -k["in"]})
                    for k in reversed(keys)]
        tolerance = rotation_linear_epsilon if transform == "rotate" else (
            0.0001 if transform == "translate" else 0.00001)
        if use_linear_reduction:
            keys = fit(keys, tolerance)
        prepared.append((bone, transform, axis, keys))
    # Integer .anim frame numbers retain the existing tool's frame-index semantics.
    unit = {24: "film", 25: "pal", 30: "ntsc", 48: "show", 50: "palf",
            60: "ntscf"}.get(fps, f"{fps:.9g}fps")
    from output_files import atomic_text
    with atomic_text(save_path) as f:
        f.write(MARKER + "\nanimVersion 1.1;\nmayaVersion 2025;\n")
        f.write(f"timeUnit {unit};\nlinearUnit cm;\nangularUnit deg;\n")
        f.write(f"startTime {start:.9g};\nendTime {end:.9g};\n")
        for bone, transform, axis, keys in prepared:
            channel = transform+axis
            f.write(f"anim {transform}.{channel} {channel} {bone} 0 0 "
                    f"{get_transform_key(transform, axis)};\n")
            f.write("animData {\n  input time;\n  output " +
                    ("angular" if transform == "rotate" else "linear") + ";\n")
            f.write("  weighted 0;\n  preInfinity constant;\n  postInfinity constant;\n  keys {\n")
            for k in keys:
                incoming, outgoing = math.degrees(math.atan(k["in"])), math.degrees(math.atan(k["out"]))
                f.write(f'    {k["time"]:.9g} {k["value"]:.9g} fixed fixed 0 0 0 '
                        f'{incoming:.12g} 1 {outgoing:.12g} 1;\n')
            f.write("  }\n}\n")
    return {"channels": len(channels), "source_keys": sum(len(c[3]) for c in channels),
            "export_keys": sum(len(c[3]) for c in prepared)}
