"""Install the reviewed ZIP in the user's running Blender via its existing bridge."""
from pathlib import Path
import importlib
import json
import tomllib
import bpy

repo = Path(__file__).resolve().parents[1]
version = tomllib.loads((repo/'layz_agentkit'/'blender_manifest.toml').read_text(encoding='utf-8'))['version']
archive = repo/'dist'/f'layz_agentkit-{version}.zip'
before = {'filepath':bpy.data.filepath, 'objects':[o.name for o in bpy.context.scene.objects],
          'matrices':{o.name:[list(row) for row in o.matrix_world] for o in bpy.context.scene.objects}}
package = next((name for name in bpy.context.preferences.addons.keys() if name.rsplit('.',1)[-1]=='layz_agentkit'), None)
current_version = importlib.import_module(package).api.describe()['data']['version'] if package else None
status = {'ALREADY_ENABLED'} if current_version == version else bpy.ops.extensions.package_install_files(filepath=str(archive),repo='user_default',enable_on_install=True)
package = next(name for name in bpy.context.preferences.addons.keys() if name.rsplit('.',1)[-1]=='layz_agentkit')
kit = importlib.import_module(package).api
description = kit.describe()
assert description['data']['version'] == version, description
targets = [o.name for o in bpy.context.selected_objects if o.type == 'MESH']
inspection = kit.inspect_asset(targets,triangle_limit=2000) if targets else None
assert description['ok'] and (inspection is None or inspection['ok']),(description,inspection)
after = {'filepath':bpy.data.filepath, 'objects':[o.name for o in bpy.context.scene.objects],
         'matrices':{o.name:[list(row) for row in o.matrix_world] for o in bpy.context.scene.objects}}
assert before == after, 'Installation or inspection changed source geometry'
bpy.ops.wm.save_userpref()
result = {'installed':list(status),'package':package,'name':description['data']['name'],
          'version':description['data']['version'],'api_version':description['api_version'],
          'triangles':inspection['data']['total_triangles'] if inspection else None,
          'within_budget':inspection['data']['within_triangle_limit'] if inspection else None,
          'source_scene_preserved':before==after,'blend_saved':bool(bpy.data.filepath)}
(repo/'artifacts'/'live-install.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
