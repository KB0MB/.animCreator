"""Non-destructive FBX -> old/new .anim fixtures and SDK reference samples."""
import csv
import importlib.util
import json
import os
from pathlib import Path
import sys
import time
import types
from fbx import FbxAnimLayer, FbxAnimStack, FbxCriteria, FbxNode, FbxTime
from FBX_import import load_fbx_animations
from animExport import export_single_animation, is_skeleton_node
from graphExport import graph_keys, evaluate


def main():
    root, output, old_path = map(Path, sys.argv[1:4])
    output.mkdir(parents=True, exist_ok=True)
    old = types.ModuleType("legacy_anim_export")
    exec(compile(old_path.read_text(encoding="cp1252"), str(old_path), "exec"), old.__dict__)
    metrics_path = output/"export-metrics.json"
    rows = json.loads(metrics_path.read_text()) if metrics_path.exists() else []
    groups = sys.argv[4:] or ["W/W.fbx", "V/V.fbx", "R/R.fbx"]
    for relative in groups:
        print("Loading", relative, flush=True)
        animations, bones, scene, manager = load_fbx_animations(str(root/relative))
        fps = FbxTime.GetFrameRate(scene.GetGlobalSettings().GetTimeMode())
        chosen = sorted(set(round(i*(len(animations)-1)/5) for i in range(min(6, len(animations)))))
        for index in chosen:
            original, name = animations[index]
            started = time.time()
            print("Exporting", name, flush=True)
            legacy = output/(name+".legacy.anim")
            modern = output/(name+".anim")
            old.export_single_animation(original, str(legacy), scene, write_scale=False)
            result = export_single_animation(original, str(modern), scene, write_scale=False,
                                             use_cubic_curves=True)
            stack = next(scene.GetSrcObject(FbxCriteria.ObjectType(FbxAnimStack.ClassId), i)
                         for i in range(scene.GetSrcObjectCount(FbxCriteria.ObjectType(FbxAnimStack.ClassId)))
                         if scene.GetSrcObject(FbxCriteria.ObjectType(FbxAnimStack.ClassId), i).GetName() == original)
            layer = stack.GetMember(FbxAnimLayer.ClassId, 0)
            channels = []
            for i in range(scene.GetSrcObjectCount(FbxCriteria.ObjectType(FbxNode.ClassId))):
                node = scene.GetSrcObject(FbxCriteria.ObjectType(FbxNode.ClassId), i)
                if not is_skeleton_node(node):
                    continue
                for transform, prop, first_index in (("rotate", node.LclRotation, 3),
                                                     ("translate", node.LclTranslation, 6)):
                    for axis_index, axis in enumerate("XYZ"):
                        curve = prop.GetCurve(layer, axis)
                        if curve and curve.KeyGetCount():
                            channels.append((node.GetName(), first_index+axis_index, curve,
                                             graph_keys(curve, fps)))
            start = min(c[3][0]["time"] for c in channels)
            with (output/(name+".reference.tsv")).open("w", newline="") as file:
                writer = csv.writer(file, delimiter="\t")
                for bone, index, curve, keys in channels:
                    times = {k["time"] for k in keys}
                    for a, b in zip(keys, keys[1:]):
                        for fraction in (0.125, 0.25, 0.5, 0.75, 0.875):
                            times.add(a["time"]+(b["time"]-a["time"])*fraction)
                    for frame in sorted(times):
                        t = FbxTime()
                        t.SetSecondDouble(frame/fps)
                        writer.writerow([bone, index, frame-start, evaluate(curve, t)])
            rows = [r for r in rows if r["name"] != name]
            rows.append(dict(name=name, fbx=relative, seconds=time.time()-started, **result))
            (output/"export-metrics.json").write_text(json.dumps(rows, indent=2))
            print(rows[-1], flush=True)
        manager.Destroy()


if __name__ == "__main__":
    main()
