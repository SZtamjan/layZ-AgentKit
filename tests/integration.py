"""Run with Blender --background --factory-startup --python-exit-code 1 --python this.py."""
import json
from pathlib import Path
import shutil
import sys
import traceback
from unittest import mock
import bpy
from mathutils import Vector

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))
import layz_agentkit as kit
from layz_agentkit import model, storage, inspection, canvas

OUT = REPO / "artifacts" / "integration"
OUT.mkdir(parents=True, exist_ok=True)
RESULTS = []


def check(name, condition):
    if not condition:
        raise AssertionError(name)
    RESULTS.append(name)
    print("PASS:", name, flush=True)


def unwrap(result):
    assert result["ok"], json.dumps(result, ensure_ascii=False)
    json.dumps(result)
    return result["data"]


def run():
    kit.register()
    check("API discovery is JSON safe", len(unwrap(kit.api.describe())["operations"]) == 7)
    check("Unsaved import fails clearly", kit.api.export_board_preview(model.active_board().id)["error"]["code"] == "PROJECT_NOT_SAVED")
    bpy.ops.object.select_all(action='SELECT')
    bpy.ops.object.delete(use_global=False)
    bpy.ops.mesh.primitive_cube_add(size=1)
    cube = bpy.context.object
    cube.name = "FixtureCube"
    bpy.ops.wm.save_as_mainfile(filepath=str(OUT/"fixture.blend"))
    image = bpy.data.images.new("UserReference", width=64, height=32, alpha=True)
    image.pixels.foreach_set([.15,.5,.8,1] * (64*32))
    image.filepath_raw = str(OUT/"original.png")
    image.file_format = 'PNG'
    image.save()
    original_bytes = (OUT/"original.png").read_bytes()
    data = model.root()
    global_board = model.active_board()
    ref = storage.import_reference(global_board, OUT/"original.png")
    reference_id = ref.id
    check("Reference copy preserves original", (OUT/"original.png").read_bytes() == original_bytes and storage.absolute(ref.filepath).read_bytes() == original_bytes)
    check("Import preserves aspect ratio", abs(ref.width/ref.height-2)<1e-6)
    ref.keep = "Frame shape"
    ref.avoid = "Rust"
    ref.role = {'SHAPE','MOOD'}
    initial_revision = global_board.revision
    ref.description = "Keep the silhouette; avoid rust."
    check("Metadata edits increment board revision", global_board.revision > initial_revision)
    model.new_note(global_board, "Reference notes — kolor i kształt")
    board = model.new_board("Cube references")
    board_id = board.id
    parent = bpy.data.collections.new("ReferencesParent")
    child = bpy.data.collections.new("ReferencesChild")
    bpy.context.scene.collection.children.link(parent)
    parent.children.link(child)
    child.objects.link(cube)
    board.bindings.add().collection = parent
    direct = model.new_board("Direct object board")
    direct.bindings.add().object = cube
    cube.name = "RenamedCube"
    parent.name = "RenamedParent"
    context = unwrap(kit.api.get_context([cube.name]))
    check("Context includes global, parent and object boards after rename", len(context["boards"]) == 3)
    other = bpy.data.collections.new("OtherParent")
    bpy.context.scene.collection.children.link(other)
    other.children.link(child)
    multi = model.new_board("Other parent style")
    multi.bindings.add().collection = other
    check("Multiple collection parents are traversed", len(unwrap(kit.api.get_context([cube.name]))["boards"]) == 4)
    before = [(i.id,i.description,i.filepath) for i in global_board.items]
    feedback = unwrap(kit.api.add_feedback(global_board.id, text="Check the corner bevel", image_path=str(OUT/"original.png")))
    check("Agent feedback is append-only and labelled", feedback["item"]["author"] == "AGENT" and before == [(i.id,i.description,i.filepath) for i in global_board.items if i.author == "USER"])
    ctx = unwrap(kit.api.get_context([cube.name]))
    g = next(b for b in ctx["boards"] if b["scope"] == "PROJECT")
    check("User references and agent feedback are separate", len(g["user_references"]) == 2 and len(g["agent_feedback"]) == 1)
    check("Unknown targets fail", not kit.api.inspect_asset(["DoesNotExist"])["ok"])
    clean = unwrap(kit.api.inspect_asset([cube.name], triangle_limit=12))
    check("One metre cube is 12 triangles", clean["total_triangles"] == 12 and all(abs(d-1)<1e-6 for d in clean["dimensions_m"]))
    check("Triangle budget exceeded is reported", not unwrap(kit.api.inspect_asset([cube.name], triangle_limit=11))["within_triangle_limit"])
    bevel = cube.modifiers.new("Fixture bevel", 'BEVEL')
    bevel.width = .04
    bevel.segments = 1
    modified = unwrap(kit.api.inspect_asset([cube.name]))
    check("Evaluated mesh includes modifiers", modified["objects"][0]["triangles_before_modifiers"] == 12 and modified["total_triangles"] > 12)
    cube.modifiers.remove(bevel)
    bpy.ops.mesh.primitive_cube_add(size=2)
    volume = bpy.context.object
    volume.name = "FixtureVolume"
    check("Known fitting case", unwrap(kit.api.check_fit([cube.name], volume.name))["fits"])
    check("Margin can make fitting fail", not unwrap(kit.api.check_fit([cube.name], volume.name, .6))["fits"])
    cube.location.x = 2
    bpy.context.view_layer.update()
    check("Outside volume fails", not unwrap(kit.api.check_fit([cube.name], volume.name))["fits"])
    cube.location = (0,0,0)
    cube.rotation_euler.z = .4
    bpy.context.view_layer.update()
    check("Rotated geometry is evaluated", unwrap(kit.api.check_fit([cube.name], volume.name))["fits"])
    cube.rotation_euler.z = 0
    bpy.context.view_layer.update()
    missing = bpy.data.images.new("MissingTexture", width=2,height=2)
    missing.source = 'FILE'
    missing.filepath = str(OUT/"missing.png")
    material = bpy.data.materials.new("FixtureMaterial")
    material.use_nodes = True
    node = material.node_tree.nodes.new("ShaderNodeTexImage")
    node.image = missing
    noise = material.node_tree.nodes.new("ShaderNodeTexNoise")
    cube.data.materials.append(material)
    broken = unwrap(kit.api.inspect_asset([cube.name]))
    check("Missing textures and procedural textures are reported", "Missing texture images" in broken["objects"][0]["warnings"] and "Procedural textures need baking for Unity" in broken["objects"][0]["warnings"])
    node.image = image
    material.node_tree.nodes.remove(noise)
    material.node_tree.links.new(node.outputs['Color'],material.node_tree.nodes['Principled BSDF'].inputs['Base Color'])
    mesh = bpy.data.meshes.new("OpenMesh")
    mesh.from_pydata([(0,0,0),(1,0,0),(0,1,0)],[],[(0,1,2)])
    open_obj = bpy.data.objects.new("OpenFixture",mesh)
    bpy.context.scene.collection.objects.link(open_obj)
    uv = mesh.uv_layers.new()
    for loop in uv.data:
        loop.uv = (2,2)
    bad = unwrap(kit.api.inspect_asset([open_obj.name]))["objects"][0]
    check("Open geometry and invalid UV are informational", bad["boundary_edges"] == 3 and bad["uv_layers"][0]["coordinates_outside_0_1"] == 3 and bad["uv_layers"][0]["degenerate_uv_triangles"] == 1)
    board.bindings.add().object = open_obj
    bpy.data.objects.remove(open_obj, do_unlink=True)
    check("Deleted binding targets do not break context", kit.api.get_context([cube.name])["ok"])
    # Force globally unique frame layout before the board image test.
    storage.arrange(global_board)
    original_scene = bpy.context.scene
    original_count = len(bpy.data.scenes)
    original_matrices = {o.name: tuple(v for row in o.matrix_world for v in row) for o in bpy.context.scene.objects}
    board_result = unwrap(kit.api.export_board_preview(global_board.id, resolution=512))
    check("Board preview is PNG", Path(board_result["path"]).read_bytes().startswith(b'\x89PNG'))
    views = unwrap(kit.api.capture_views([cube.name], resolution=128))
    check("All six views rendered", len(views["views"]) == 6 and all(Path(p).is_file() for p in views["views"].values()))
    check("Rendering restores source scenes and objects", bpy.context.scene == original_scene and len(bpy.data.scenes) == original_count and original_matrices == {o.name: tuple(v for row in o.matrix_world for v in row) for o in bpy.context.scene.objects})
    package = unwrap(kit.api.export_asset([cube.name], destination=str(OUT/"exports"), preview_resolution=128))
    check("FBX independently reimports at correct scale", package["validation"]["ok"] and package["validation"]["triangles"] == 12)
    check("Texture packaged without moodboard images", len(list((Path(package['package'])/'textures').iterdir())) == 1)
    report = json.loads(Path(package['report']).read_text(encoding='utf-8'))
    check("Export writes report and Unity instructions", report['status'] == 'verified' and (Path(package['package'])/'README.txt').is_file())
    next_package = unwrap(kit.api.export_asset([cube.name], destination=str(OUT/"exports"), preview_resolution=128))
    check("Export versions never overwrite", next_package['package'] != package['package'] and Path(package['fbx']).is_file())
    # Multiple objects and off-centre origins must survive as a set.
    volume.data.materials.append(material)
    volume.location = (3,0,0)
    bpy.context.view_layer.update()
    multi_package = unwrap(kit.api.export_asset([cube.name,volume.name], destination=str(OUT/"exports"), name="MultiObject", preview_resolution=128))
    check("Multi-object export preserves layout and dimensions", multi_package['validation']['ok'] and multi_package['validation']['triangles'] == 24)
    volume.location = (0,0,0)
    bpy.context.view_layer.update()
    image.pack()
    packed_source = OUT/'original.png'
    backup = packed_source.with_suffix('.packed_backup')
    packed_source.rename(backup)
    try:
        packed_package = unwrap(kit.api.export_asset([cube.name], destination=str(OUT/"exports"), name="PackedTexture", preview_resolution=128))
        check("Packed textures export when the original file is absent", len(list((Path(packed_package['package'])/'textures').iterdir())) == 1)
    finally:
        backup.rename(packed_source)
    # Test physical scale when Blender units are centimetres.
    original_scene.unit_settings.scale_length = .01
    cube.scale = (100,100,100)
    bpy.context.view_layer.update()
    cm_package = unwrap(kit.api.export_asset([cube.name], destination=str(OUT/"exports"), name="CentimetreCube", preview_resolution=128))
    check("Unit conversion preserves one physical metre", all(abs(d-1)<1e-4 for d in cm_package['validation']['dimensions_m']))
    original_scene.unit_settings.scale_length = 1
    cube.scale = (1,1,1)
    bpy.context.view_layer.update()
    bpy.ops.wm.save_as_mainfile(filepath=str(OUT/"fixture_saved.blend"))
    check("Save As copies managed images to new folder", all(storage.absolute(i.filepath).is_file() and 'fixture_saved_agentkit' in i.filepath for i in global_board.items if i.kind == 'IMAGE'))
    check("Save As preserves old reference folder", (OUT/'fixture_agentkit'/'references').is_dir())
    saved_subdir = OUT/'save_as_subdir'
    saved_subdir.mkdir(exist_ok=True)
    bpy.ops.wm.save_as_mainfile(filepath=str(saved_subdir/'fixture_saved.blend'))
    check("Save As into another directory copies references", all(storage.absolute(i.filepath).is_file() and str(saved_subdir) in str(storage.absolute(i.filepath)) for i in global_board.items if i.kind == 'IMAGE'))
    with mock.patch.object(storage.shutil, 'copy2', side_effect=PermissionError('Simulated read-only destination')):
        storage.before_save(str(OUT/'read_only_destination'/'failed.blend'))
    check("Failed Save As preserves absolute source references", bool(model.root().storage_error) and all(not i.filepath.startswith('//') and Path(i.filepath).is_file() for i in global_board.items if i.kind == 'IMAGE'))
    storage.before_save(bpy.data.filepath)
    check("Reference migration can recover on the next save", not model.root().storage_error)
    saved_id = global_board.id
    bpy.ops.wm.open_mainfile(filepath=str(OUT/"fixture_saved.blend"))
    restored = model.board_by_id(saved_id)
    check("Stable board/item IDs survive reopen", any(i.id == reference_id for i in restored.items))
    check("Object bindings survive reopen", len(unwrap(kit.api.get_context(['RenamedCube']))['boards']) == 4)
    moved = OUT/'moved'
    moved.mkdir(exist_ok=True)
    shutil.copy2(OUT/'fixture_saved.blend', moved/'fixture_saved.blend')
    shutil.copytree(OUT/'fixture_saved_agentkit', moved/'fixture_saved_agentkit', dirs_exist_ok=True)
    bpy.ops.wm.open_mainfile(filepath=str(moved/'fixture_saved.blend'))
    restored = model.board_by_id(saved_id)
    check("Moving blend with its folder preserves references", all(storage.absolute(i.filepath).is_file() for i in restored.items if i.kind == 'IMAGE'))
    item = next(i for i in restored.items if i.kind == 'IMAGE' and i.author == 'USER')
    old_path = storage.absolute(item.filepath)
    old_path.rename(old_path.with_suffix('.hidden'))
    check("Missing reference is reported", unwrap(kit.api.get_context(['RenamedCube']))['warnings'])
    storage.relink_reference(item, OUT/'original.png')
    check("Relink copies into managed storage", storage.absolute(item.filepath).is_file() and str(moved) in str(storage.absolute(item.filepath)))
    kit.unregister()
    check("Handlers cleaned on unregister", canvas.DRAW_HANDLE is None and not canvas.SESSIONS and storage.before_save not in bpy.app.handlers.save_pre)
    kit.register()
    check("Extension can register again", kit.api.describe()['ok'])
    kit.unregister()


try:
    run()
except Exception:
    (OUT/'results.json').write_text(json.dumps({'passed': RESULTS,'error':traceback.format_exc()},indent=2),encoding='utf-8')
    raise
else:
    (OUT/'results.json').write_text(json.dumps({'passed':RESULTS,'count':len(RESULTS)},indent=2),encoding='utf-8')
    print(f"ALL {len(RESULTS)} CHECKS PASSED",flush=True)
