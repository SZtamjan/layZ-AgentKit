# SPDX-License-Identifier: GPL-3.0-or-later
from contextlib import contextmanager
from pathlib import Path
import bmesh
import bpy
from mathutils import Vector
from .storage import KitError


def resolve_targets(targets=None):
    """Names, Object/Collection instances, or {'objects': [...], 'collections': [...]}.

    Empty object targets include their mesh descendants. Collection targets recurse.
    """
    result = []

    def add(value):
        if isinstance(value, bpy.types.Collection):
            for obj in value.all_objects:
                add(obj)
        elif isinstance(value, bpy.types.Object):
            if value.type == "MESH" and value not in result:
                result.append(value)
            elif value.type == "EMPTY":
                for obj in value.children_recursive:
                    if obj.type == "MESH" and obj not in result:
                        result.append(obj)
        elif isinstance(value, str):
            found = bpy.data.objects.get(value) or bpy.data.collections.get(value)
            if found is None:
                raise KitError("TARGET_NOT_FOUND", "Unknown object or collection: " + value)
            add(found)
        else:
            raise KitError("INVALID_TARGET", "Expected object/collection names or datablocks.")

    if targets is None:
        for obj in bpy.context.selected_objects:
            add(obj)
    elif isinstance(targets, dict):
        for name in targets.get("objects", []):
            obj = bpy.data.objects.get(name)
            if obj is None:
                raise KitError("TARGET_NOT_FOUND", "Unknown object: " + name)
            add(obj)
        for name in targets.get("collections", []):
            coll = bpy.data.collections.get(name)
            if coll is None:
                raise KitError("TARGET_NOT_FOUND", "Unknown collection: " + name)
            add(coll)
    elif isinstance(targets, (str, bpy.types.Object, bpy.types.Collection)):
        add(targets)
    else:
        for value in targets:
            add(value)
    if not result:
        raise KitError("NO_MESH_TARGETS", "Choose at least one mesh or a collection containing meshes.")
    return result


@contextmanager
def evaluated_mesh(obj):
    graph = bpy.context.evaluated_depsgraph_get()
    evaluated = obj.evaluated_get(graph)
    mesh = evaluated.to_mesh(preserve_all_data_layers=True, depsgraph=graph)
    try:
        yield evaluated, mesh
    finally:
        evaluated.to_mesh_clear()


def bounds(points):
    if not points:
        raise KitError("EMPTY_GEOMETRY", "The selected geometry has no vertices.")
    low = Vector(tuple(min(p[axis] for p in points) for axis in range(3)))
    high = Vector(tuple(max(p[axis] for p in points) for axis in range(3)))
    return low, high


def world_points(objects):
    points = []
    for obj in objects:
        with evaluated_mesh(obj) as (evaluated, mesh):
            points.extend(evaluated.matrix_world @ v.co for v in mesh.vertices)
    return points


def material_nodes(material, seen=None):
    seen = set() if seen is None else seen
    if not material or not material.use_nodes or not material.node_tree:
        return

    def visit(tree):
        if tree.as_pointer() in seen:
            return
        seen.add(tree.as_pointer())
        for node in tree.nodes:
            yield node
            if node.type == "GROUP" and node.node_tree:
                yield from visit(node.node_tree)
    yield from visit(material.node_tree)


def images_for_material(material):
    return list(dict.fromkeys(n.image for n in material_nodes(material) if n.type == "TEX_IMAGE" and n.image))


def material_report(material):
    if material is None:
        return {"name": None, "warnings": ["Empty material slot"]}
    procedural = any(n.bl_idname.startswith("ShaderNodeTex") and n.type != "TEX_IMAGE" for n in material_nodes(material))
    images = []
    for image in images_for_material(material):
        path = str(Path(bpy.path.abspath(image.filepath, library=image.library)).resolve()) if image.filepath else ""
        packed = bool(image.packed_file) or bool(image.packed_files)
        images.append({"name": image.name, "path": path, "packed": packed,
                       "source": image.source, "color_space": image.colorspace_settings.name,
                       "missing": not packed and image.source != "GENERATED" and not Path(path).is_file()})
    return {"name": material.name, "procedural_textures": procedural, "images": images,
            "warnings": ["Procedural textures require baking before Unity delivery"] if procedural else []}


def inspect(targets=None, triangle_limit=None):
    objects = resolve_targets(targets)
    if triangle_limit is not None and triangle_limit < 0:
        raise KitError("INVALID_LIMIT", "Triangle limit cannot be negative.")
    scale = bpy.context.scene.unit_settings.scale_length
    reports = []
    total = 0
    for obj in objects:
        obj.data.calc_loop_triangles()
        with evaluated_mesh(obj) as (evaluated, mesh):
            mesh.calc_loop_triangles()
            triangle_count = len(mesh.loop_triangles)
            total += triangle_count
            points = [evaluated.matrix_world @ v.co for v in mesh.vertices]
            lo, hi = bounds(points) if points else (Vector(), Vector())
            bm = bmesh.new()
            try:
                bm.from_mesh(mesh)
                boundary = sum(e.is_boundary for e in bm.edges)
                nonmanifold = sum(not e.is_manifold for e in bm.edges)
                loose = sum(e.is_wire for e in bm.edges)
            finally:
                bm.free()
            uv_reports = []
            for layer in mesh.uv_layers:
                outside = sum(not (0 <= loop.uv.x <= 1 and 0 <= loop.uv.y <= 1) for loop in layer.data)
                degenerate = 0
                for tri in mesh.loop_triangles:
                    a, b, c = (layer.data[i].uv for i in tri.loops)
                    area = abs((b.x-a.x)*(c.y-a.y) - (b.y-a.y)*(c.x-a.x)) / 2
                    degenerate += area < 1e-12
                uv_reports.append({"name": layer.name, "coordinates_outside_0_1": outside,
                                   "degenerate_uv_triangles": degenerate})
            materials = [material_report(m) for m in mesh.materials]
            warnings = []
            if not mesh.uv_layers:
                warnings.append("No UV layers")
            if boundary:
                warnings.append("Open boundaries can be intentional")
            if nonmanifold:
                warnings.append("Non-manifold edges can be intentional; review the geometry")
            if evaluated.matrix_world.determinant() < 0:
                warnings.append("Negative world transform determinant; review winding after export")
            if any(i["missing"] for m in materials for i in m.get("images", [])):
                warnings.append("Missing texture images")
            if any(m.get("procedural_textures") for m in materials):
                warnings.append("Procedural textures need baking for Unity")
            reports.append({
                "name": obj.name, "triangles_before_modifiers": len(obj.data.loop_triangles),
                "triangles_after_modifiers": triangle_count, "vertices": len(mesh.vertices),
                "dimensions_m": list((hi-lo)*scale), "world_bounds_m": [list(lo*scale), list(hi*scale)],
                "location": list(obj.location), "rotation_euler": list(obj.rotation_euler),
                "scale": list(obj.scale), "origin_world_m": list(obj.matrix_world.translation*scale),
                "degenerate_triangles": sum(t.area < 1e-12 for t in mesh.loop_triangles),
                "boundary_edges": boundary, "nonmanifold_edges": nonmanifold, "loose_edges": loose,
                "uv_layers": uv_reports, "materials": materials,
                "material_face_counts": {str(i): sum(p.material_index == i for p in mesh.polygons) for i in range(len(mesh.materials))},
                "warnings": warnings,
            })
    lo, hi = bounds(world_points(objects))
    return {"objects": reports, "total_triangles": total, "dimensions_m": list((hi-lo)*scale),
            "world_bounds_m": [list(lo*scale), list(hi*scale)], "triangle_limit": triangle_limit,
            "within_triangle_limit": triangle_limit is None or total <= triangle_limit,
            "warnings": ["Triangle limit exceeded"] if triangle_limit is not None and total > triangle_limit else []}


def fit(targets, volume, margin_m=0.0):
    objects = resolve_targets(targets)
    container = bpy.data.objects.get(volume) if isinstance(volume, str) else volume
    if container is None or container.type != "MESH":
        raise KitError("INVALID_VOLUME", "The fitting volume must be a mesh object.")
    if margin_m < 0:
        raise KitError("INVALID_MARGIN", "Margin must be zero or positive.")
    matrix = container.matrix_world
    if abs(matrix.determinant()) < 1e-12:
        raise KitError("SINGULAR_VOLUME", "The fitting volume has a zero scale axis.")
    inverse = matrix.inverted()
    lo, hi = bounds([inverse @ p for p in world_points(objects)])
    with evaluated_mesh(container) as (_, mesh):
        volume_lo, volume_hi = bounds([v.co.copy() for v in mesh.vertices])
    scale = bpy.context.scene.unit_settings.scale_length
    clearances = []
    for axis in range(3):
        # World distance between the planes x_i = constant, including sheared parents.
        meters_per_unit = scale / inverse.to_3x3().row[axis].length
        clearances.append([(lo[axis]-volume_lo[axis])*meters_per_unit,
                           (volume_hi[axis]-hi[axis])*meters_per_unit])
    return {"method": "Containment of evaluated asset vertices inside the volume's local bounding box; no collision test",
            "volume": container.name, "targets": [o.name for o in objects], "margin_m": margin_m,
            "clearance_m": dict(zip(("x", "y", "z"), clearances)),
            "fits": all(c >= margin_m-1e-7 for pair in clearances for c in pair)}
