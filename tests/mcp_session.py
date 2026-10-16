"""Serve ONE test request through the installed Blender Lab bridge on port 9877.

This is a separate disposable Blender process, never the user's active scene.
"""
import importlib.util
import os
from pathlib import Path
import sys
import time
import bpy

repo = Path(__file__).resolve().parents[1]
sys.path.insert(0,str(repo))
import layz_agentkit
layz_agentkit.register()
bpy.ops.wm.open_mainfile(filepath=str(repo/'artifacts'/'integration'/'fixture_saved.blend'))
source = Path(os.environ['APPDATA'])/'Blender Foundation'/'Blender'/'5.2'/'extensions'/'lab_blender_org'/'mcp'
spec = importlib.util.spec_from_file_location('agentkit_test_bridge',source/'__init__.py',submodule_search_locations=[str(source)])
module = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = module
spec.loader.exec_module(module)
from agentkit_test_bridge import mcp_to_blender_server as server
server.start('127.0.0.1',9877)
deadline = time.monotonic()+120
try:
    while time.monotonic()<deadline:
        if server.poll_blocking(timeout=.5):
            break
    else:
        raise TimeoutError('No MCP test client connected')
finally:
    server.stop()
layz_agentkit.unregister()
