"""Executed inside the disposable Blender by the real existing MCP bridge."""
from pathlib import Path
import json
import layz_agentkit
kit = layz_agentkit.api

def read(response):
    assert response['ok'],response
    return response['data']

context = read(kit.get_context(['RenamedCube']))
board = next(b for b in context['boards'] if b['scope']=='PROJECT')
images = [r for r in board['user_references'] if r['kind']=='IMAGE']
assert images and all(Path(r['path']).is_file() for r in images)
preview = read(kit.export_board_preview(board['id'],resolution=1024))
views = read(kit.capture_views(['RenamedCube'],resolution=256,views=['perspective']))
feedback = read(kit.add_feedback(board['id'],text='MCP visual check: cube silhouette and scale verified.',image_path=views['views']['perspective']))
updated = read(kit.get_context(['RenamedCube']))
assert updated['revision']>context['revision']
delivery = read(kit.export_asset(['RenamedCube'],name='MCPVerifiedCube',preview_resolution=128))
result = {'ok':True,'context_boards':len(context['boards']),'user_images':images,
          'board_preview':preview['path'],'asset_preview':views['views']['perspective'],
          'agent_feedback_id':feedback['item']['id'],'revision_changed':True,
          'package':delivery['package'],'fbx_verified':delivery['validation']['ok']}
repo = Path(__file__).resolve().parents[1]
(repo/'artifacts'/'mcp-smoke.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
