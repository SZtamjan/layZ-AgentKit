# SPDX-License-Identifier: GPL-3.0-or-later
"""Run only in a clean Blender child process; does not load the user's .blend."""
import json
from pathlib import Path
import sys
import traceback
import bpy
from mathutils import Vector


def main():
    filename, output = sys.argv[sys.argv.index("--")+1:]
    try:
        bpy.ops.object.select_all(action="SELECT")
        bpy.ops.object.delete(use_global=False)
        # Support the native importer when available and the bundled legacy importer.
        try:
            bpy.ops.wm.fbx_import.get_rna_type()
        except (AttributeError, RuntimeError, KeyError):
            bpy.ops.import_scene.fbx(filepath=filename)
        else:
            bpy.ops.wm.fbx_import(filepath=filename)
        objects = [o for o in bpy.context.scene.objects if o.type == "MESH"]
        points = []
        triangles = 0
        for obj in objects:
            obj.data.calc_loop_triangles()
            triangles += len(obj.data.loop_triangles)
            points.extend(obj.matrix_world @ v.co for v in obj.data.vertices)
        if not points:
            raise RuntimeError("Reimported FBX contains no mesh vertices")
        low = Vector(tuple(min(p[a] for p in points) for a in range(3)))
        high = Vector(tuple(max(p[a] for p in points) for a in range(3)))
        data = {"ok": True, "objects": [o.name for o in objects], "triangles": triangles,
                "dimensions_m": list((high-low)*bpy.context.scene.unit_settings.scale_length)}
    except Exception:
        data = {"ok": False, "error": traceback.format_exc()}
    Path(output).write_text(json.dumps(data, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
