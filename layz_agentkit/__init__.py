# SPDX-License-Identifier: GPL-3.0-or-later
"""layZ AgentKit. The public agent interface is ``api``."""
bl_info = {
    "name": "layZ AgentKit", "author": "layZ", "version": (0, 1, 1),
    "blender": (5, 2, 0), "category": "3D View",
    "description": "Moodboards and asset tools for agents using an existing MCP bridge",
}

from . import model, storage, inspection, rendering, delivery, api, ui, canvas


def register():
    model.register()
    storage.register()
    ui.register()
    canvas.register()


def unregister():
    canvas.unregister()
    ui.unregister()
    storage.unregister()
    model.unregister()
