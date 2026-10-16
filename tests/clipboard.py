"""The surrounding STA PowerShell test owns and restores the OS clipboard."""
from pathlib import Path
import json
import sys
import bpy
root = Path(__file__).resolve().parents[1]
sys.path.insert(0,str(root))
import layz_agentkit as kit
from layz_agentkit import model, storage
kit.register()
out = root/'artifacts'/'clipboard'
out.mkdir(parents=True,exist_ok=True)
bpy.ops.wm.save_as_mainfile(filepath=str(out/'clipboard.blend'))
item = storage.paste_reference(model.active_board())
assert item.kind == 'IMAGE' and item.author == 'USER'
assert tuple(item.image.size) == (48,32),tuple(item.image.size)
assert storage.absolute(item.filepath).read_bytes().startswith(b'\x89PNG')
(out/'results.json').write_text(json.dumps({'ok':True,'dimensions':[48,32],'path':str(storage.absolute(item.filepath))},indent=2),encoding='utf-8')
kit.unregister()
