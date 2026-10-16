# SPDX-License-Identifier: GPL-3.0-or-later
import json
from pathlib import Path
import bpy
from bpy.props import CollectionProperty, EnumProperty, IntProperty, StringProperty
from bpy_extras.io_utils import ImportHelper
from . import model, storage, api, canvas

LAST_RESULT = {}


def show_result(operator, result):
    global LAST_RESULT
    LAST_RESULT = result
    text = bpy.data.texts.get("AgentKit Last Report.json") or bpy.data.texts.new("AgentKit Last Report.json")
    text.clear()
    text.write(json.dumps(result, ensure_ascii=False, indent=2))
    if result.get("ok"):
        operator.report({'INFO'}, "AgentKit complete — see Last Report")
    else:
        operator.report({'ERROR'}, result.get("error", {}).get("message", "Operation failed")[:500])


class LAZ_OT_import(bpy.types.Operator, ImportHelper):
    bl_idname = "layz_agentkit.import_images"
    bl_label = "Add References"
    bl_options = {'REGISTER', 'UNDO'}
    filter_glob: StringProperty(default="*.png;*.jpg;*.jpeg;*.webp", options={'HIDDEN'})
    directory: StringProperty(subtype='DIR_PATH')
    files: CollectionProperty(type=bpy.types.OperatorFileListElement)
    relink: bpy.props.BoolProperty(default=False, options={'HIDDEN'})

    def execute(self, context):
        board = model.active_board()
        try:
            if self.relink:
                if not board.items:
                    return {'CANCELLED'}
                item = board.items[min(board.active_item, len(board.items)-1)]
                storage.relink_reference(item, self.filepath)
            else:
                paths = [str(Path(self.directory)/f.name) for f in self.files] or [self.filepath]
                failures = []
                for path in paths:
                    try:
                        storage.import_reference(board, path)
                    except (storage.KitError, OSError, RuntimeError) as exc:
                        failures.append(str(exc))
                storage.arrange(board)
                if failures:
                    self.report({'ERROR'}, "; ".join(failures)[:1000])
                    return {'FINISHED'}  # Keep successfully imported entries undoable.
        except (storage.KitError, OSError, RuntimeError) as exc:
            self.report({'ERROR'}, str(exc))
            return {'CANCELLED'}
        return {'FINISHED'}


class LAZ_FH_images(bpy.types.FileHandler):
    bl_idname = "LAZ_FH_images"
    bl_label = "Moodboard References"
    bl_import_operator = "layz_agentkit.import_images"
    bl_file_extensions = ".png;.jpg;.jpeg;.webp"

    @classmethod
    def poll_drop(cls, context):
        return context.area is not None and context.area.type == 'IMAGE_EDITOR' and canvas.state(context.area) is not None


class LAZ_OT_action(bpy.types.Operator):
    bl_idname = "layz_agentkit.board_action"
    bl_label = "Moodboard Action"
    bl_options = {'REGISTER', 'UNDO'}
    action: StringProperty()
    index: IntProperty(default=0)

    def execute(self, context):
        board = model.active_board()
        data = model.root()
        try:
            if self.action == "NEW_BOARD":
                model.new_board()
            elif self.action == "REMOVE_BOARD":
                if board.global_board:
                    raise ValueError("The Project style board cannot be removed.")
                data.boards.remove(data.active_board)
                data.active_board = max(0, data.active_board-1)
                data.revision += 1
            elif self.action == "ADD_NOTE":
                model.new_note(board)
            elif self.action == "PASTE":
                storage.paste_reference(board)
                storage.arrange(board)
            elif self.action == "ARRANGE":
                storage.arrange(board)
            elif self.action == "REMOVE_ITEMS":
                ids = {i.id for i in canvas.selected_items(board)}
                for index in reversed(range(len(board.items))):
                    if board.items[index].id in ids:
                        board.items.remove(index)
                board.active_item = min(board.active_item, max(0,len(board.items)-1))
                model.changed(board, context)
                view = canvas.state()
                if view:
                    view.selected.clear()
            elif self.action in {"FRONT", "BACK"}:
                ids = {i.id for i in canvas.selected_items(board)}
                selected = [i.id for i in board.items if i.id in ids]
                if self.action == "BACK":
                    selected.reverse()
                for item_id in selected:
                    index = next(i for i,item in enumerate(board.items) if item.id == item_id)
                    board.items.move(index, len(board.items)-1 if self.action == "FRONT" else 0)
                model.changed(board, context)
            elif self.action in {"BIND_OBJECT", "BIND_COLLECTION"}:
                if board.global_board:
                    raise ValueError("Project style already applies to all assets. Create an asset board to assign targets.")
                if self.action == "BIND_OBJECT":
                    target = data.bind_object or context.active_object
                    if target is None:
                        raise ValueError("Choose an object to bind.")
                    if not any(b.object == target for b in board.bindings):
                        board.bindings.add().object = target
                else:
                    if data.bind_collection is None:
                        raise ValueError("Choose a collection to bind.")
                    if not any(b.collection == data.bind_collection for b in board.bindings):
                        board.bindings.add().collection = data.bind_collection
            elif self.action == "UNBIND":
                board.bindings.remove(self.index)
                model.changed(board, context)
            elif self.action == "COPY_INSTRUCTIONS":
                context.window_manager.clipboard = api.instructions()
                self.report({'INFO'}, "Agent instructions copied. Paste into your agent's chat.")
            elif self.action == "CLOSE_BOARD":
                if context.area:
                    canvas.stop_view(context.area.as_pointer())
            elif self.action == "FRAME":
                view = canvas.state()
                region = next((r for r in context.area.regions if r.type == 'WINDOW'), None) if context.area else None
                if view and region:
                    canvas.fit_view(view, board, region)
            elif self.action == "SHOW_REPORT":
                text = bpy.data.texts.get("AgentKit Last Report.json")
                if text and context.area:
                    canvas.stop_view(context.area.as_pointer())
                    context.area.type = 'TEXT_EDITOR'
                    context.area.spaces.active.text = text
        except (storage.KitError, OSError, ValueError, RuntimeError) as exc:
            self.report({'ERROR'}, str(exc))
            return {'CANCELLED'}
        return {'FINISHED'}


class LAZ_OT_group(bpy.types.Operator):
    bl_idname = "layz_agentkit.group_items"
    bl_label = "Group Selected Entries"
    bl_options = {'REGISTER', 'UNDO'}
    name: StringProperty(name="Group name", default="References", description="Leave empty to ungroup")

    def invoke(self, context, event):
        return context.window_manager.invoke_props_dialog(self)

    def execute(self, context):
        for item in canvas.selected_items(model.active_board()):
            item.group = self.name
        return {'FINISHED'}


class LAZ_OT_tool(bpy.types.Operator):
    bl_idname = "layz_agentkit.run_tool"
    bl_label = "Run AgentKit Tool"
    tool: EnumProperty(items=[(i,i.title(),"") for i in ("INSPECT","VIEWS","FIT","EXPORT","BOARD_PREVIEW","CONTEXT")])

    def execute(self, context):
        data = model.root()
        kwargs = {"triangle_limit": data.triangle_limit or None}
        if self.tool == "INSPECT":
            result = api.inspect_asset(**kwargs)
        elif self.tool == "VIEWS":
            result = api.capture_views(resolution=data.preview_resolution, material_mode=data.material_mode)
        elif self.tool == "FIT":
            result = api.check_fit(None, data.fit_volume.name if data.fit_volume else "", data.fit_margin)
        elif self.tool == "EXPORT":
            destination = str(storage.absolute(data.export_dir)) if data.export_dir else None
            result = api.export_asset(destination=destination, **kwargs)
        elif self.tool == "BOARD_PREVIEW":
            result = api.export_board_preview(model.active_board().id, include_agent=data.show_agent)
        else:
            result = api.get_context()
        show_result(self, result)
        return {'FINISHED'} if result.get("ok") else {'CANCELLED'}


class LAZ_UL_boards(bpy.types.UIList):
    def draw_item(self, context, layout, data, item, icon, active_data, active_propname, index):
        layout.label(text=item.title, icon='WORLD' if item.global_board else 'OUTLINER_COLLECTION')


class LAZ_UL_items(bpy.types.UIList):
    def draw_item(self, context, layout, data, item, icon, active_data, active_propname, index):
        layout.label(text=("[Agent] " if item.author == 'AGENT' else "") + item.title,
                     icon='IMAGE_DATA' if item.kind == 'IMAGE' else 'TEXT')


def action(layout, text, value, icon='NONE'):
    operator = layout.operator("layz_agentkit.board_action", text=text, icon=icon)
    operator.action = value
    return operator


class PanelContents:
    def draw(self, context):
        layout = self.layout
        # draw() is read-only in Blender. A fresh file can have no data (or a
        # retained but empty container); initialize only from an operator.
        row = layout.row(align=True)
        row.operator("layz_agentkit.open_moodboard", icon='IMAGE')
        if canvas.state(context.area):
            action(row, "", "CLOSE_BOARD", 'X')
        action(layout, "Copy Agent Instructions", "COPY_INSTRUCTIONS", 'COPYDOWN')
        data = model.root(create=False)
        board = model.active_board(create=False)
        if data is None or board is None or not any(b.global_board for b in data.boards):
            layout.label(text="Open a moodboard to start.", icon='INFO')
            layout.label(text="Save .blend before importing references.")
            return
        layout.template_list("LAZ_UL_boards", "", data, "boards", data, "active_board", rows=3)
        row = layout.row(align=True)
        action(row, "New board", "NEW_BOARD", 'ADD')
        if not board.global_board:
            action(row, "Remove", "REMOVE_BOARD", 'REMOVE')
        layout.prop(board, "title")
        if not board.global_board:
            box = layout.box()
            box.prop(data, "bind_object")
            action(box, "Assign object / active object", "BIND_OBJECT")
            box.prop(data, "bind_collection")
            action(box, "Assign collection", "BIND_COLLECTION")
            for index, binding in enumerate(board.bindings):
                row = box.row(align=True)
                row.label(text=binding.object.name if binding.object else (binding.collection.name if binding.collection else "Missing target"))
                action(row, "", "UNBIND", 'X').index = index
        row = layout.row(align=True)
        row.operator("layz_agentkit.import_images", text="Add images", icon='FILE_IMAGE')
        action(row, "Paste", "PASTE", 'PASTEDOWN')
        row = layout.row(align=True)
        action(row, "Note", "ADD_NOTE", 'TEXT')
        action(row, "Arrange", "ARRANGE", 'ALIGN_JUSTIFY')
        action(row, "Frame", "FRAME", 'VIEWZOOM')
        layout.prop(data, "show_agent")
        layout.template_list("LAZ_UL_items", "", board, "items", board, "active_item", rows=3)
        if board.items:
            item = board.items[min(max(board.active_item,0),len(board.items)-1)]
            box = layout.box()
            box.label(text=item.author.title()+" · "+item.id[:8])
            box.prop(item, "title")
            box.prop(item, "description")
            if item.kind == 'IMAGE':
                box.prop(item, "role")
                box.prop(item, "keep")
                box.prop(item, "avoid")
                if not storage.absolute(item.filepath).is_file():
                    box.label(text="Missing image", icon='ERROR')
                box.operator("layz_agentkit.import_images", text="Relink image").relink = True
            box.prop(item, "group")
            row = box.row(align=True)
            row.prop(item, "x")
            row.prop(item, "y")
            box.operator("layz_agentkit.group_items", text="Group selection")
            row = box.row(align=True)
            action(row, "To front", "FRONT")
            action(row, "To back", "BACK")
            action(box, "Remove selected entries", "REMOVE_ITEMS", 'TRASH')
        box = layout.box()
        box.label(text="Agent context")
        row = box.row(align=True)
        row.operator("layz_agentkit.run_tool", text="Read context").tool = 'CONTEXT'
        row.operator("layz_agentkit.run_tool", text="Board PNG").tool = 'BOARD_PREVIEW'
        box.label(text=f"Board revision: {board.revision}")
        if data.storage_error:
            box.label(text="Reference storage needs attention", icon='ERROR')
        box = layout.box()
        box.label(text="Selected meshes · Asset tools")
        box.prop(data, "triangle_limit")
        box.operator("layz_agentkit.run_tool", text="Inspect selected", icon='VIEWZOOM').tool = 'INSPECT'
        box.prop(data, "material_mode")
        box.prop(data, "preview_resolution")
        box.operator("layz_agentkit.run_tool", text="Capture six views", icon='RENDER_STILL').tool = 'VIEWS'
        box.prop(data, "fit_volume")
        box.prop(data, "fit_margin")
        box.operator("layz_agentkit.run_tool", text="Check box fit").tool = 'FIT'
        box.prop(data, "export_dir")
        box.operator("layz_agentkit.run_tool", text="Export verified Unity package", icon='EXPORT').tool = 'EXPORT'
        action(layout, "Show Last Report", "SHOW_REPORT", 'TEXT')
        layout.label(text="Save .blend before importing references.")


class LAZ_PT_view(PanelContents, bpy.types.Panel):
    bl_label = "layZ AgentKit"
    bl_idname = "LAZ_PT_view"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = "AgentKit"


class LAZ_PT_image(PanelContents, bpy.types.Panel):
    bl_label = "layZ AgentKit"
    bl_idname = "LAZ_PT_image"
    bl_space_type = 'IMAGE_EDITOR'
    bl_region_type = 'UI'
    bl_category = "AgentKit"


CLASSES = (LAZ_OT_import, LAZ_FH_images, LAZ_OT_action, LAZ_OT_group, LAZ_OT_tool,
           LAZ_UL_boards, LAZ_UL_items, LAZ_PT_view, LAZ_PT_image)


def register():
    for cls in CLASSES:
        bpy.utils.register_class(cls)


def unregister():
    for cls in reversed(CLASSES):
        bpy.utils.unregister_class(cls)
