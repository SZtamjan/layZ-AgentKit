# SPDX-License-Identifier: GPL-3.0-or-later
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import bmesh
import bpy
from . import inspection, rendering, storage


def safe_name(name):
    name = re.sub(r"[^\w.-]+", "_", name).strip(". _")[:70] or "Asset"
    if name.upper().split(".")[0] in {"CON", "PRN", "AUX", "NUL", *("COM"+str(i) for i in range(1,10)), *("LPT"+str(i) for i in range(1,10))}:
        name = "Asset_" + name
    return name


def package_folder(base, name):
    base.mkdir(parents=True, exist_ok=True)
    for number in range(1, 100000):
        path = base / f"{name}_v{number:03d}"
        try:
            path.mkdir()
            return path
        except FileExistsError:
            continue
    raise storage.KitError("VERSION_LIMIT", "No available package version")


def run_validation(fbx, package, expected):
    output = package/"reimport.json"
    executable = Path(bpy.app.binary_path)
    if not executable.is_file():
        return {"ok": False, "error": "Blender executable not found for independent reimport"}
    args = [str(executable), "--background", "--factory-startup", "--threads", "2", "--python-exit-code", "1",
            "--python", str(Path(__file__).with_name("validate_fbx.py")), "--", str(fbx), str(output)]
    try:
        proc = subprocess.run(args, capture_output=True, timeout=180,
                              creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0)
        (package/"reimport.log").write_bytes(proc.stdout + b"\n" + proc.stderr)
        if proc.returncode or not output.is_file():
            return {"ok": False, "error": "Independent reimport failed; see reimport.log", "returncode": proc.returncode}
        data = json.loads(output.read_text(encoding="utf-8"))
    except (OSError, subprocess.TimeoutExpired, ValueError) as exc:
        return {"ok": False, "error": str(exc)}
    if data.get("ok"):
        data["triangles_match"] = data["triangles"] == expected["total_triangles"]
        data["dimensions_match"] = all(abs(a-b) <= max(.0001, abs(b)*.0001) for a,b in zip(data["dimensions_m"], expected["dimensions_m"]))
        data["ok"] = data["triangles_match"] and data["dimensions_match"]
    return data


def export(targets=None, destination=None, name=None, triangle_limit=None, preview_resolution=512):
    objects = inspection.resolve_targets(targets)
    if bpy.context.mode != "OBJECT":
        raise storage.KitError("OBJECT_MODE_REQUIRED", "Switch to Object Mode before exporting.")
    report = inspection.inspect(objects, triangle_limit)
    base = Path(destination).resolve() if destination else storage.ensure_storage()/"exports"
    name = safe_name(name or (objects[0].name if len(objects) == 1 else "AssetSet"))
    package = package_folder(base, name)
    fbx = package/(name+".fbx")
    textures = package/"textures"
    textures.mkdir()
    image_map, material_map, cloned_images, cloned_groups, warnings = {}, {}, [], [], []
    source_scene = bpy.context.scene

    def copy_image(image):
        if image in image_map:
            return image_map[image]
        if image.source not in {"FILE", "GENERATED"}:
            warnings.append(f"Unsupported texture source {image.source}: {image.name}; bake it before Unity import")
            image_map[image] = None
            return None
        original_path = Path(bpy.path.abspath(image.filepath, library=image.library)) if image.filepath else None
        index = len(image_map)+1
        suffixes = {"PNG": ".png", "JPEG": ".jpg", "OPEN_EXR": ".exr", "HDR": ".hdr", "TIFF": ".tif", "TARGA": ".tga", "BMP": ".bmp"}
        suffix = original_path.suffix if original_path and original_path.suffix else suffixes.get(image.file_format,".png")
        destination = textures/(f"{index:03d}_"+safe_name(Path(image.name).stem)+suffix)
        if image.packed_file:
            destination.write_bytes(bytes(image.packed_file.data))
        elif image.source == "FILE" and original_path and original_path.is_file():
            shutil.copy2(original_path, destination)
        elif image.source == "GENERATED":
            destination = destination.with_suffix(".png")
            temp_image = image.copy()
            try:
                temp_image.filepath_raw = str(destination)
                temp_image.file_format = "PNG"
                temp_image.save()
            finally:
                bpy.data.images.remove(temp_image)
        else:
            warnings.append("Missing texture: " + image.name)
            image_map[image] = None
            return None
        copied = bpy.data.images.load(str(destination), check_existing=False)
        copied.colorspace_settings.name = image.colorspace_settings.name
        copied.alpha_mode = image.alpha_mode
        cloned_images.append(copied)
        image_map[image] = copied
        return copied

    def retarget_tree(tree):
        for node in tree.nodes:
            if node.type == "TEX_IMAGE" and node.image:
                node.image = copy_image(node.image)
            elif node.type == "GROUP" and node.node_tree:
                group = node.node_tree.copy()
                cloned_groups.append(group)
                node.node_tree = group
                retarget_tree(group)

    try:
        with rendering.temporary_scene("AgentKit export", 64) as (scene, resources):
            scene.unit_settings.system = "METRIC"
            scene.unit_settings.scale_length = source_scene.unit_settings.scale_length
            graph = bpy.context.evaluated_depsgraph_get()
            copies = []
            for original in objects:
                evaluated = original.evaluated_get(graph)
                mesh = bpy.data.meshes.new_from_object(evaluated, preserve_all_data_layers=True, depsgraph=graph)
                resources.append(mesh)
                bm = bmesh.new()
                try:
                    bm.from_mesh(mesh)
                    bmesh.ops.triangulate(bm, faces=list(bm.faces))
                    bm.to_mesh(mesh)
                finally:
                    bm.free()
                for slot, material in enumerate(list(mesh.materials)):
                    if material is None:
                        continue
                    if material not in material_map:
                        copied = material.copy()
                        resources.append(copied)
                        if copied.use_nodes:
                            retarget_tree(copied.node_tree)
                        material_map[material] = copied
                    mesh.materials[slot] = material_map[material]
                obj = bpy.data.objects.new(original.name+"_export", mesh)
                scene.collection.objects.link(obj)
                obj.matrix_world = evaluated.matrix_world.copy()
                copies.append(obj)
            layer = scene.view_layers[0]
            layer.update()
            with bpy.context.temp_override(scene=scene, view_layer=layer,
                                           selected_objects=copies, selected_editable_objects=copies,
                                           active_object=copies[0], object=copies[0]):
                for obj in scene.objects:
                    obj.select_set(obj in copies, view_layer=layer)
                layer.objects.active = copies[0]
                bpy.ops.export_scene.fbx(
                    filepath=str(fbx), use_selection=True, object_types={"MESH"},
                    axis_forward="-Z", axis_up="Y", global_scale=1.0,
                    apply_unit_scale=True, apply_scale_options="FBX_SCALE_UNITS",
                    use_mesh_modifiers=False, add_leaf_bones=False, bake_anim=False,
                    path_mode="RELATIVE", embed_textures=False,
                )
        preview = rendering.capture(objects, destination=package/"previews", resolution=preview_resolution, views=["perspective"])
        validation = run_validation(fbx, package, report)
        report.update({"validation": validation, "delivery_warnings": warnings,
                       "preview": preview, "fbx": str(fbx), "package": str(package),
                       "status": "verified" if validation.get("ok") else "validation_failed"})
        (package/"report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
        (package/"README.txt").write_text(
            "layZ AgentKit - static Unity asset\n\n"
            "Import the FBX and textures folder into Unity together. Physical units are metres; axes are +Y up / -Z forward at FBX export.\n"
            "Existing pivots and relative transforms are preserved. No rig, animation or collider is included.\n"
            "Create Unity materials for your render pipeline and assign the supplied textures. Check sRGB, normal map and channel packing settings.\n"
            "Procedural Blender nodes are not baked or translated to Unity. See report.json for missing textures and other warnings.\n"
            "The preview uses a neutral material. Moodboard references are not part of this asset package.\n"
            "Validation is an independent Blender FBX reimport, not a Unity import test.\n"
            f"Validation: {report['status']}\n", encoding="utf-8")
        if not validation.get("ok"):
            error = storage.KitError("FBX_VALIDATION_FAILED", "Package retained for review: " + str(package))
            error.details = report
            raise error
        return {"package": str(package), "fbx": str(fbx), "report": str(package/"report.json"),
                "preview": preview["views"]["perspective"], "validation": validation,
                "warnings": warnings + report["warnings"] + [w for obj in report["objects"] for w in obj["warnings"]]}
    except Exception as exc:
        (package/"export_error.txt").write_text(str(exc), encoding="utf-8")
        raise
    finally:
        for group in cloned_groups:
            bpy.data.node_groups.remove(group)
        for image in cloned_images:
            bpy.data.images.remove(image)
