# SPDX-License-Identifier: GPL-3.0-or-later
"""Temporary rendering scenes: never change source scene lights or cameras."""
from contextlib import contextmanager
import math
from pathlib import Path
import textwrap
import bpy
from mathutils import Vector
from . import inspection, model, storage


@contextmanager
def temporary_scene(name="AgentKit Preview", resolution=1024):
    scene = bpy.data.scenes.new(name)
    resources = []
    try:
        scene.render.engine = "CYCLES"
        scene.cycles.device = "CPU"
        scene.cycles.samples = 32
        scene.cycles.use_denoising = True
        scene.render.resolution_x = resolution
        scene.render.resolution_y = resolution
        scene.render.resolution_percentage = 100
        scene.render.image_settings.file_format = "PNG"
        scene.render.image_settings.color_mode = "RGBA"
        scene.view_settings.view_transform = "Standard"
        scene.view_settings.look = "None"
        scene.view_settings.exposure = 0
        scene.view_settings.gamma = 1
        world = bpy.data.worlds.new("AgentKit temporary world")
        resources.append(world)
        world.use_nodes = True
        world.node_tree.nodes["Background"].inputs[0].default_value = (.08, .09, .12, 1)
        world.node_tree.nodes["Background"].inputs[1].default_value = .5
        scene.world = world
        camera = bpy.data.cameras.new("AgentKit temporary camera")
        resources.append(camera)
        obj = bpy.data.objects.new(camera.name, camera)
        scene.collection.objects.link(obj)
        scene.camera = obj
        yield scene, resources
    finally:
        for obj in list(scene.objects):
            bpy.data.objects.remove(obj, do_unlink=True)
        bpy.data.scenes.remove(scene)
        # Remove only the resources this session owns, never user datablocks.
        for data in reversed(resources):
            if isinstance(data, bpy.types.Mesh):
                bpy.data.meshes.remove(data)
            elif isinstance(data, bpy.types.Material):
                bpy.data.materials.remove(data)
            elif isinstance(data, bpy.types.Camera):
                bpy.data.cameras.remove(data)
            elif isinstance(data, bpy.types.Light):
                bpy.data.lights.remove(data)
            elif isinstance(data, bpy.types.World):
                bpy.data.worlds.remove(data)
            elif isinstance(data, bpy.types.Curve):
                bpy.data.curves.remove(data)


def render(scene, path):
    path = Path(path).resolve()
    path.parent.mkdir(parents=True, exist_ok=True)
    scene.render.filepath = str(path)
    bpy.ops.render.render(write_still=True, scene=scene.name)
    if not path.is_file():
        raise storage.KitError("RENDER_FAILED", "No preview was written: " + str(path))
    return str(path)


def emission_material(name, color, resources, image=None):
    mat = bpy.data.materials.new(name)
    resources.append(mat)
    mat.diffuse_color = color
    mat.use_nodes = True
    nodes, links = mat.node_tree.nodes, mat.node_tree.links
    nodes.clear()
    output = nodes.new("ShaderNodeOutputMaterial")
    emission = nodes.new("ShaderNodeEmission")
    emission.inputs["Color"].default_value = color
    if image:
        tex = nodes.new("ShaderNodeTexImage")
        tex.image = image
        links.new(tex.outputs["Color"], emission.inputs["Color"])
        mix = nodes.new("ShaderNodeMixShader")
        transparent = nodes.new("ShaderNodeBsdfTransparent")
        links.new(tex.outputs["Alpha"], mix.inputs[0])
        links.new(transparent.outputs[0], mix.inputs[1])
        links.new(emission.outputs[0], mix.inputs[2])
        links.new(mix.outputs[0], output.inputs["Surface"])
    else:
        links.new(emission.outputs[0], output.inputs["Surface"])
    return mat


def plane(scene, resources, name, x, y, w, h, z, material):
    mesh = bpy.data.meshes.new(name)
    resources.append(mesh)
    mesh.from_pydata([(x,y,z), (x+w,y,z), (x+w,y+h,z), (x,y+h,z)], [], [(0,1,2,3)])
    uv = mesh.uv_layers.new()
    for loop, coord in zip(uv.data, ((0,0),(1,0),(1,1),(0,1))):
        loop.uv = coord
    mesh.materials.append(material)
    obj = bpy.data.objects.new(name, mesh)
    scene.collection.objects.link(obj)
    return obj


def text_object(scene, resources, text, x, y, size, z, material):
    curve = bpy.data.curves.new("AgentKit label", "FONT")
    resources.append(curve)
    curve.body = text
    curve.size = size
    curve.space_line = 1.2
    obj = bpy.data.objects.new("AgentKit label", curve)
    scene.collection.objects.link(obj)
    obj.location = (x,y,z)
    curve.materials.append(material)


def board_preview(board_id, filepath=None, resolution=1600, include_agent=True):
    board = model.board_by_id(board_id)
    folder = storage.ensure_storage() / "previews"
    destination = Path(filepath) if filepath else folder / ("board_" + board.id + ".png")
    items = [i for i in board.items if include_agent or i.author == "USER"]
    if not items:
        raise storage.KitError("EMPTY_BOARD", "Add an image or a note before exporting the board.")
    xmin = min(i.x for i in items)-32
    xmax = max(i.x+i.width for i in items)+32
    ymin = min(i.y-70 for i in items)-32
    ymax = max(i.y+i.height for i in items)+90
    width, height = xmax-xmin, ymax-ymin
    with temporary_scene("AgentKit board", resolution) as (scene, resources):
        scene.cycles.samples = 1
        scene.cycles.use_denoising = False
        scene.render.resolution_x = resolution if width >= height else max(128, round(resolution*width/height))
        scene.render.resolution_y = resolution if height >= width else max(128, round(resolution*height/width))
        camera = scene.camera
        camera.location = ((xmin+xmax)/2, (ymin+ymax)/2, len(items)+20)
        camera.rotation_euler = (0,0,0)
        camera.data.type = "ORTHO"
        camera.data.ortho_scale = max(width, height*scene.render.resolution_x/scene.render.resolution_y)
        dark = emission_material("Board background", (.025,.03,.045,1), resources)
        card = emission_material("Note background", (.10,.13,.18,1), resources)
        ink = emission_material("Labels", (.85,.9,1,1), resources)
        plane(scene, resources, "Board", xmin, ymin, width, height, -1, dark)
        group_mat = emission_material("Group frame", (.055,.075,.11,1), resources)
        for group in sorted({i.group for i in items if i.group}):
            members = [i for i in items if i.group == group]
            lx, ly = min(i.x for i in members)-12, min(i.y for i in members)-36
            hx, hy = max(i.x+i.width for i in members)+12, max(i.y+i.height for i in members)+30
            plane(scene, resources, "Group", lx, ly, hx-lx, hy-ly, -.5, group_mat)
            text_object(scene, resources, group, lx+6, hy-18, 14, -.4, ink)
        text_object(scene, resources, board.title, xmin+16, ymax-40, 24, .1, ink)
        for index, item in enumerate(items):
            z = index*.01
            image = storage.image_for(item) if item.kind == "IMAGE" else None
            mat = emission_material("Reference", (1,1,1,1), resources, image) if image else card
            plane(scene, resources, "Reference " + item.id, item.x, item.y, item.width, item.height, z, mat)
            if item.kind == "NOTE" or image is None:
                text = item.description if item.kind == "NOTE" else "Missing image — relink in AgentKit"
                wrap = max(12, int(item.width/9))
                rows = max(1, int(item.height/20)-1)
                lines = [line for paragraph in text.splitlines() for line in (textwrap.wrap(paragraph, wrap) or [""])]
                text_object(scene, resources, "\n".join(lines[:rows]), item.x+10, item.y+item.height-24, 14, z+.002, ink)
            label = f"[{item.id[:8]}] {item.title} ({item.author.title()})"
            text_object(scene, resources, label[:100], item.x, item.y-22, 13, z+.002, ink)
        path = render(scene, destination)
    return {"board_id": board.id, "revision": board.revision, "path": path,
            "item_ids": [i.id for i in items], "warnings": ["Use get_context for full descriptions and original image paths."]}


def capture(targets=None, destination=None, resolution=768, material_mode="NEUTRAL", views=None):
    objects = inspection.resolve_targets(targets)
    if material_mode not in {"NEUTRAL", "MATERIAL"}:
        raise storage.KitError("INVALID_MODE", "Use NEUTRAL or MATERIAL.")
    if not 64 <= resolution <= 4096:
        raise storage.KitError("INVALID_RESOLUTION", "Resolution must be between 64 and 4096.")
    folder = Path(destination).resolve() if destination else storage.ensure_storage()/"previews"/model.uid()[:12]
    directions = {"front": (0,-1,0), "back": (0,1,0), "left": (-1,0,0),
                  "right": (1,0,0), "top": (0,0,1), "perspective": (1,-1,.75)}
    requested = list(directions) if views is None else list(views)
    if not requested or any(v not in directions for v in requested):
        raise storage.KitError("INVALID_VIEW", "Choose front, back, left, right, top or perspective.")
    points = inspection.world_points(objects)
    low, high = inspection.bounds(points)
    center = (low+high)/2
    radius = max((p-center).length for p in points) or .5
    paths = {}
    with temporary_scene(resolution=resolution) as (scene, resources):
        neutral = bpy.data.materials.new("AgentKit neutral")
        resources.append(neutral)
        neutral.use_nodes = True
        neutral.node_tree.nodes["Principled BSDF"].inputs["Base Color"].default_value = (.42,.48,.56,1)
        neutral.node_tree.nodes["Principled BSDF"].inputs["Roughness"].default_value = .65
        graph = bpy.context.evaluated_depsgraph_get()
        for original in objects:
            evaluated = original.evaluated_get(graph)
            mesh = bpy.data.meshes.new_from_object(evaluated, preserve_all_data_layers=True, depsgraph=graph)
            resources.append(mesh)
            copy = bpy.data.objects.new("Preview " + original.name, mesh)
            copy.matrix_world = evaluated.matrix_world.copy()
            scene.collection.objects.link(copy)
            if material_mode == "NEUTRAL":
                mesh.materials.clear()
                mesh.materials.append(neutral)
                for face in mesh.polygons:
                    face.material_index = 0
        for direction, power, size in (((-2,-3,4), 220, 3), ((3,-1,1), 100, 4), ((0,3,3), 160, 3)):
            lamp = bpy.data.lights.new("AgentKit softbox", "AREA")
            resources.append(lamp)
            lamp.energy = power * radius**2
            lamp.shape = "DISK"
            lamp.size = size*radius
            light = bpy.data.objects.new(lamp.name, lamp)
            scene.collection.objects.link(light)
            light.location = center + Vector(direction)*radius
            light.rotation_euler = (center-light.location).to_track_quat('-Z','Y').to_euler()
        for name in requested:
            camera = scene.camera
            direction = Vector(directions[name]).normalized()
            camera.location = center + direction*radius*4
            camera.rotation_euler = (center-camera.location).to_track_quat('-Z','Y').to_euler()
            camera.data.type = "PERSP" if name == "perspective" else "ORTHO"
            camera.data.lens = 48
            camera.data.ortho_scale = radius*2.35
            camera.data.clip_start = max(.00001, radius*.001)
            camera.data.clip_end = radius*100+10
            paths[name] = render(scene, folder/(name+".png"))
    return {"targets": [o.name for o in objects], "material_mode": material_mode,
            "resolution": resolution, "views": paths}
