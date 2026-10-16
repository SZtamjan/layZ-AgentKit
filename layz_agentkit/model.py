# SPDX-License-Identifier: GPL-3.0-or-later
"""File-wide, undoable RNA data in a retained, unlinked Collection datablock.

Text datablocks have editor-specific undo, so they cannot anchor canvas edits.
"""
import uuid
import bpy
from bpy.props import (
    BoolProperty, CollectionProperty, EnumProperty, FloatProperty, IntProperty,
    PointerProperty, StringProperty,
)

DATA_NAME = ".layz_agentkit_data"


def uid():
    return uuid.uuid4().hex


def changed(self, context):
    data = getattr(self.id_data, "layz_agentkit", None)
    if data is None:
        return
    data.revision += 1
    for board in data.boards:
        if self == board or any(self == i for i in board.items) or any(self == b for b in board.bindings):
            board.revision += 1
            break


class LAZBinding(bpy.types.PropertyGroup):
    object: PointerProperty(type=bpy.types.Object, update=changed)
    collection: PointerProperty(type=bpy.types.Collection, update=changed)


class LAZItem(bpy.types.PropertyGroup):
    id: StringProperty()
    kind: EnumProperty(items=[("IMAGE", "Image", ""), ("NOTE", "Note", "")])
    author: EnumProperty(items=[("USER", "User", ""), ("AGENT", "Agent", "")])
    title: StringProperty(name="Title", update=changed)
    description: StringProperty(name="Description / note", update=changed)
    role: EnumProperty(name="Reference for", options={"ENUM_FLAG"}, items=[
        ("SHAPE", "Shape", "", 1), ("MATERIAL", "Material", "", 2),
        ("COLOR", "Color", "", 4), ("MOOD", "Mood", "", 8),
    ], update=changed)
    keep: StringProperty(name="Keep", update=changed)
    avoid: StringProperty(name="Avoid", update=changed)
    filepath: StringProperty()
    image: PointerProperty(type=bpy.types.Image)
    group: StringProperty(name="Group", update=changed)
    x: FloatProperty(update=changed)
    y: FloatProperty(update=changed)
    width: FloatProperty(default=320, min=20, max=30000, update=changed)
    height: FloatProperty(default=240, min=20, max=30000, update=changed)


class LAZBoard(bpy.types.PropertyGroup):
    id: StringProperty()
    title: StringProperty(name="Board name", default="Asset references", update=changed)
    global_board: BoolProperty()
    revision: IntProperty(default=1)
    items: CollectionProperty(type=LAZItem)
    bindings: CollectionProperty(type=LAZBinding)
    active_item: IntProperty(default=0)


class LAZData(bpy.types.PropertyGroup):
    schema_version: IntProperty(default=1)
    revision: IntProperty(default=1)
    boards: CollectionProperty(type=LAZBoard)
    active_board: IntProperty(default=0)
    show_agent: BoolProperty(name="Show agent feedback", default=True)
    managed_root: StringProperty()
    saved_filepath: StringProperty()
    storage_error: StringProperty()
    bind_object: PointerProperty(name="Object", type=bpy.types.Object)
    bind_collection: PointerProperty(name="Collection", type=bpy.types.Collection)
    triangle_limit: IntProperty(name="Triangle budget (0 = none)", default=2000, min=0)
    fit_volume: PointerProperty(name="Fitting volume", type=bpy.types.Object)
    fit_margin: FloatProperty(name="Margin (metres)", default=0, min=0, precision=4)
    export_dir: StringProperty(name="Export folder", subtype="DIR_PATH")
    material_mode: EnumProperty(name="Preview material", items=[("NEUTRAL", "Neutral", ""), ("MATERIAL", "Existing materials", "")])
    preview_resolution: IntProperty(name="Preview resolution", default=768, min=64, max=4096)


CLASSES = (LAZBinding, LAZItem, LAZBoard, LAZData)


def root(create=True):
    container = bpy.data.collections.get(DATA_NAME)
    if container is None:
        if not create:
            return None
        container = bpy.data.collections.new(DATA_NAME)
        container.use_fake_user = True
    data = container.layz_agentkit
    if create and not any(b.global_board for b in data.boards):
        board = data.boards.add()
        board.id = uid()
        board.global_board = True
        board.title = "Project style"
    return data


def active_board(create=True):
    data = root(create=create)
    if data is None or not data.boards:
        return None
    return data.boards[min(max(data.active_board, 0), len(data.boards) - 1)]


def board_by_id(board_id):
    data = root()
    board = next((b for b in data.boards if b.id == board_id), None)
    if board is None:
        raise ValueError("Unknown board: " + str(board_id))
    return board


def new_board(title="Asset references"):
    data = root()
    board = data.boards.add()
    board.id = uid()
    board.title = title
    data.active_board = len(data.boards) - 1
    return board


def new_note(board, text="New note", author="USER"):
    position = next_x(board)
    item = board.items.add()
    item.id = uid()
    item.kind = "NOTE"
    item.author = author
    item.title = "Agent note" if author == "AGENT" else "Note"
    item.description = text
    item.x = position
    item.width, item.height = 300, 180
    board.active_item = len(board.items) - 1
    changed(board, None)
    return item


def next_x(board):
    return max((i.x + i.width + 24 for i in board.items), default=0)


def relevant_boards(objects):
    data = root()
    collections = set()
    for obj in objects:
        collections.update(obj.users_collection)
    # Objects can belong to several collections, and collections to several parents.
    while True:
        parents = {c for c in bpy.data.collections if any(child in collections for child in c.children)}
        before = len(collections)
        collections.update(parents)
        if len(collections) == before:
            break
    return [b for b in data.boards if b.global_board or any(
        (binding.object is not None and binding.object in objects)
        or (binding.collection is not None and binding.collection in collections)
        for binding in b.bindings
    )]


def register():
    for cls in CLASSES:
        bpy.utils.register_class(cls)
    bpy.types.Collection.layz_agentkit = PointerProperty(type=LAZData)


def unregister():
    if hasattr(bpy.types.Collection, "layz_agentkit"):
        del bpy.types.Collection.layz_agentkit
    for cls in reversed(CLASSES):
        bpy.utils.unregister_class(cls)
