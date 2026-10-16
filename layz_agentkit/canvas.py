# SPDX-License-Identifier: GPL-3.0-or-later
"""An opt-in Image Editor canvas. Runtime view state is never scene geometry."""
from dataclasses import dataclass, field
import textwrap
import bpy
import blf
import gpu
from gpu_extras.batch import batch_for_shader
from bpy.app.handlers import persistent
from . import model, storage

SESSIONS = {}
DRAW_HANDLE = None


@dataclass
class View:
    area: object
    window: object
    zoom: float = 1.0
    pan: list = field(default_factory=lambda: [60., 100.])
    selected: set = field(default_factory=set)
    board_id: str = ""
    active_id: str = ""
    mode: str = ""
    start: tuple = (0,0)
    current: tuple = (0,0)
    originals: dict = field(default_factory=dict)
    selection_before: set = field(default_factory=set)
    timer: object = None
    moved: bool = False


def state(area=None):
    area = area or bpy.context.area
    return SESSIONS.get(area.as_pointer()) if area else None


def selected_items(board):
    view = state()
    ids = view.selected if view else set()
    items = [i for i in board.items if i.id in ids]
    if not items and board.items:
        index = min(max(board.active_item,0), len(board.items)-1)
        items = [board.items[index]]
    return items


def shown(board):
    data = model.root()
    return [i for i in board.items if data.show_agent or i.author == "USER"]


def fit_view(view, board, region):
    items = shown(board)
    if not items:
        view.pan = [60., 100.]
        view.zoom = 1
        return
    lowx = min(i.x for i in items)-24
    lowy = min(i.y for i in items)-45
    w = max(i.x+i.width for i in items)-lowx+24
    h = max(i.y+i.height for i in items)-lowy+24
    view.zoom = min(4, max(.02, min((region.width-80)/w, (region.height-90)/h)))
    view.pan = [(region.width-w*view.zoom)/2-lowx*view.zoom,
                (region.height-h*view.zoom)/2-lowy*view.zoom]


def rect(x, y, w, h, color):
    shader = gpu.shader.from_builtin("UNIFORM_COLOR")
    batch = batch_for_shader(shader, 'TRI_FAN', {"pos": [(x,y),(x+w,y),(x+w,y+h),(x,y+h)]})
    shader.bind()
    shader.uniform_float("color", color)
    batch.draw(shader)


def label(text, x, y, size=12, color=(.85,.89,.95,1)):
    # UI panels also use font 0 and leave clipping enabled between redraws.
    blf.disable(0, blf.CLIPPING)
    blf.disable(0, blf.ROTATION)
    blf.size(0, size)
    blf.color(0, *color)
    blf.position(0, x, y, 0)
    blf.draw(0, text)


def draw():
    area = bpy.context.area
    if not area or area.type != 'IMAGE_EDITOR':
        return
    view = state(area)
    if view is None:
        return
    board = model.active_board()
    region = bpy.context.region
    if board is None:
        return
    if view.board_id != board.id:
        view.board_id = board.id
        view.selected.clear()
        view.active_id = ""
        fit_view(view, board, region)
    if board.items:
        active = board.items[min(max(board.active_item,0),len(board.items)-1)].id
        if active != view.active_id and not view.mode:
            view.active_id = active
            view.selected = {active}
    gpu.state.blend_set('ALPHA')
    try:
        rect(0, 0, region.width, region.height, (.035,.045,.065,1))
        items = shown(board)
        # Group frames are derived from member positions, never separate mesh objects.
        for group in sorted({i.group for i in items if i.group}):
            members = [i for i in items if i.group == group]
            lx = min(i.x for i in members)-12
            ly = min(i.y for i in members)-36
            hx = max(i.x+i.width for i in members)+12
            hy = max(i.y+i.height for i in members)+30
            x,y = lx*view.zoom+view.pan[0], ly*view.zoom+view.pan[1]
            rect(x,y,(hx-lx)*view.zoom,(hy-ly)*view.zoom,(.11,.17,.24,.7))
            label(group, x+5, hy*view.zoom+view.pan[1]-18, 12)
        for item in items:
            x,y = item.x*view.zoom+view.pan[0], item.y*view.zoom+view.pan[1]
            w,h = item.width*view.zoom, item.height*view.zoom
            if x+w < 0 or y+h < 0 or x > region.width or y > region.height:
                continue
            selected = item.id in view.selected
            border = (.26,.65,1,1) if selected else ((.7,.48,.93,1) if item.author == "AGENT" else (.23,.28,.35,1))
            rect(x-3,y-3,w+6,h+6,border)
            rect(x,y,w,h,(.095,.12,.17,1))
            image = storage.thumbnail_for(item) if item.kind == "IMAGE" else None
            if image:
                try:
                    texture = gpu.texture.from_image(image)
                    shader = gpu.shader.from_builtin("IMAGE_SCENE_LINEAR_TO_REC709_SRGB")
                    batch = batch_for_shader(shader, 'TRI_FAN', {
                        "pos": [(x,y),(x+w,y),(x+w,y+h),(x,y+h)],
                        "texCoord": [(0,0),(1,0),(1,1),(0,1)],
                    })
                    shader.bind()
                    shader.uniform_sampler("image", texture)
                    batch.draw(shader)
                except (ValueError, RuntimeError):
                    label("Image unavailable — Relink", x+8, y+h/2)
            else:
                text = item.description if item.kind == "NOTE" else "Missing image — Relink in the sidebar"
                lines = [line for p in text.splitlines() for line in (textwrap.wrap(p, max(8,int(w/7.5))) or [""])]
                for row, line in enumerate(lines[:max(0,int(h/18)-1)]):
                    label(line, x+8, y+h-22-row*18)
            title = ("Agent · " if item.author == "AGENT" else "") + item.title + " [" + item.id[:8] + "]"
            label(title[:max(5,int(w/7))], x, y-19, 11)
            if selected:
                rect(x+w-5,y+h-5,10,10,(.35,.75,1,1))
        if view.mode == "BOX":
            x0,y0 = view.start
            x1,y1 = view.current
            rect(min(x0,x1),min(y0,y1),abs(x1-x0),abs(y1-y0),(.2,.55,1,.2))
        rect(0,0,region.width,30,(.025,.03,.045,.95))
        label("Drag: move  ·  Corner: scale  ·  Shift: multi-select  ·  Drag empty: box  ·  MMB: pan  ·  Wheel: zoom  ·  Home: frame  ·  Esc: close", 12, 10, 11)
        label(board.title, 14, region.height-26, 16)
    finally:
        gpu.state.blend_set('NONE')


def stop_view(key, wm=None):
    view = SESSIONS.pop(key, None)
    if view and view.timer:
        try:
            (wm or bpy.context.window_manager).event_timer_remove(view.timer)
        except (ValueError, ReferenceError):
            pass
    if view:
        try:
            view.area.tag_redraw()
        except ReferenceError:
            pass


class LAZ_OT_canvas(bpy.types.Operator):
    bl_idname = "layz_agentkit.open_moodboard"
    bl_label = "Open Moodboard"
    bl_description = "Use this area as a moodboard; split an area first to keep your 3D view beside it"
    resume: bpy.props.BoolProperty(default=False, options={'HIDDEN','SKIP_SAVE'})

    def invoke(self, context, event):
        if not context.area:
            return {'CANCELLED'}
        if context.area.type != 'IMAGE_EDITOR':
            context.area.type = 'IMAGE_EDITOR'
        key = context.area.as_pointer()
        if key in SESSIONS:
            return {'FINISHED'}
        model.root()
        view = View(context.area, context.window)
        SESSIONS[key] = view
        self.key = key
        view.timer = context.window_manager.event_timer_add(.2, window=context.window)
        if not self.resume:
            bpy.ops.ed.undo_push(message="Open layZ Moodboard")
        context.window_manager.modal_handler_add(self)
        context.area.tag_redraw()
        return {'RUNNING_MODAL'}

    def modal(self, context, event):
        view = SESSIONS.get(self.key)
        if view is None:
            return {'CANCELLED'}
        try:
            valid = any(a.as_pointer() == self.key and a.type == 'IMAGE_EDITOR' for a in view.window.screen.areas)
        except ReferenceError:
            valid = False
        if not valid:
            stop_view(self.key, context.window_manager)
            return {'CANCELLED'}
        if event.type == 'TIMER':
            view.area.tag_redraw()
            return {'PASS_THROUGH'}
        region = next((r for r in view.area.regions if r.type == 'WINDOW'), None)
        if not region:
            return {'PASS_THROUGH'}
        mx,my = event.mouse_x-region.x, event.mouse_y-region.y
        inside = 0 <= mx < region.width and 30 < my < region.height
        if not inside and not view.mode:
            return {'PASS_THROUGH'}
        board = model.active_board()
        if board is None:
            return {'PASS_THROUGH'}
        # A board switch/undo invalidates runtime item references: store only UUIDs.
        bx,by = (mx-view.pan[0])/view.zoom, (my-view.pan[1])/view.zoom
        if event.type == 'Z' and event.ctrl and event.value == 'PRESS':
            # Blender disables global Undo while a modal operator is running.
            # End this handler first, undo on the next tick, then resume the
            # canvas without creating a fresh undo step (which would lose Redo).
            window, area = view.window, view.area
            saved_zoom, saved_pan = view.zoom, list(view.pan)
            redo = event.shift
            stop_view(self.key, context.window_manager)

            def apply_undo():
                if DRAW_HANDLE is None:
                    return None
                try:
                    reg = next(r for r in area.regions if r.type == 'WINDOW')
                    with bpy.context.temp_override(window=window, area=area, region=reg):
                        operator = bpy.ops.ed.redo if redo else bpy.ops.ed.undo
                        if operator.poll():
                            operator()
                        bpy.ops.layz_agentkit.open_moodboard('INVOKE_DEFAULT', resume=True)
                        resumed = state(area)
                        if resumed:
                            resumed.board_id = model.active_board().id
                            resumed.zoom, resumed.pan = saved_zoom, saved_pan
                except (RuntimeError, ReferenceError, StopIteration) as exc:
                    print("layZ AgentKit Undo:", exc)
                return None

            bpy.app.timers.register(apply_undo, first_interval=.01)
            return {'CANCELLED'}
        elif event.type == 'ESC' and event.value == 'PRESS':
            if view.mode:
                for item in board.items:
                    if item.id in view.originals:
                        item.x,item.y,item.width,item.height = view.originals[item.id]
                view.mode = ""
            else:
                stop_view(self.key, context.window_manager)
                return {'CANCELLED'}
        elif event.type in {'WHEELUPMOUSE','WHEELDOWNMOUSE'}:
            factor = 1.15 if event.type == 'WHEELUPMOUSE' else 1/1.15
            view.zoom = max(.01, min(10,view.zoom*factor))
            view.pan = [mx-bx*view.zoom, my-by*view.zoom]
        elif event.type == 'HOME' and event.value == 'PRESS':
            fit_view(view, board, region)
        elif event.type == 'MIDDLEMOUSE':
            if event.value == 'PRESS':
                view.mode, view.start = "PAN", (mx,my)
                view.originals = {"pan": tuple(view.pan)}
            elif event.value == 'RELEASE':
                view.mode = ""
        elif event.type == 'LEFTMOUSE' and event.value in {'PRESS','DOUBLE_CLICK'}:
            hit = next((i for i in reversed(shown(board)) if i.x-6/view.zoom <= bx <= i.x+i.width+6/view.zoom and i.y-6/view.zoom <= by <= i.y+i.height+6/view.zoom), None)
            view.start, view.current, view.moved = (mx,my), (mx,my), False
            if hit:
                if event.value == 'DOUBLE_CLICK' and hit.group:
                    view.selected = {i.id for i in shown(board) if i.group == hit.group}
                elif event.shift:
                    view.selected.symmetric_difference_update({hit.id})
                elif hit.id not in view.selected:
                    view.selected = {hit.id}
                view.active_id = hit.id
                board.active_item = next(i for i,v in enumerate(board.items) if v.id == hit.id)
                corner = abs(bx-hit.x-hit.width)*view.zoom <= 10 and abs(by-hit.y-hit.height)*view.zoom <= 10
                view.mode = "SCALE" if corner else "MOVE"
                view.originals = {i.id: (i.x,i.y,i.width,i.height) for i in board.items if i.id in view.selected}
            else:
                view.selection_before = set(view.selected) if event.shift else set()
                view.selected = set(view.selection_before)
                view.mode = "BOX"
                view.originals = {}
        elif event.type == 'MOUSEMOVE' and view.mode:
            dx,dy = (mx-view.start[0])/view.zoom, (my-view.start[1])/view.zoom
            view.current = (mx,my)
            view.moved = view.moved or abs(mx-view.start[0])+abs(my-view.start[1]) > 2
            if view.mode == "PAN":
                view.pan = [view.originals['pan'][0]+mx-view.start[0],view.originals['pan'][1]+my-view.start[1]]
            elif view.mode == "MOVE":
                for item in board.items:
                    if item.id in view.originals:
                        original = view.originals[item.id]
                        item.x,item.y = original[0]+dx,original[1]+dy
            elif view.mode == "SCALE" and view.originals:
                values = list(view.originals.values())
                x0,y0 = min(v[0] for v in values), min(v[1] for v in values)
                width = max(v[0]+v[2] for v in values)-x0
                height = max(v[1]+v[3] for v in values)-y0
                factor = max(max(20/min(v[2],v[3]) for v in values),1+(dx*width+dy*height)/(width*width+height*height))
                for item in board.items:
                    if item.id in view.originals:
                        x,y,w,h = view.originals[item.id]
                        item.x,item.y = x0+(x-x0)*factor,y0+(y-y0)*factor
                        item.width,item.height = w*factor,h*factor
        elif event.type == 'LEFTMOUSE' and event.value == 'RELEASE' and view.mode:
            if view.mode == 'BOX':
                x0,x1 = sorted(((view.start[0]-view.pan[0])/view.zoom,bx))
                y0,y1 = sorted(((view.start[1]-view.pan[1])/view.zoom,by))
                view.selected = view.selection_before | {i.id for i in shown(board) if i.x <= x1 and i.x+i.width >= x0 and i.y <= y1 and i.y+i.height >= y0}
            elif view.mode in {'MOVE','SCALE'} and view.moved:
                bpy.ops.ed.undo_push(message="Move / scale moodboard entries")
            view.mode = ""
            view.originals.clear()
        elif event.type == 'A' and event.value == 'PRESS' and not event.ctrl:
            view.selected = {i.id for i in shown(board)}
        elif event.type in {'DEL','X'} and event.value == 'PRESS':
            bpy.ops.layz_agentkit.board_action(action="REMOVE_ITEMS")
        elif event.type == 'V' and event.ctrl and event.value == 'PRESS':
            bpy.ops.layz_agentkit.board_action(action="PASTE")
        elif event.type == 'G' and event.ctrl and event.value == 'PRESS':
            bpy.ops.layz_agentkit.group_items('INVOKE_DEFAULT')
        else:
            return {'PASS_THROUGH'}
        view.area.tag_redraw()
        return {'RUNNING_MODAL'}


@persistent
def reset_views(_):
    for key in list(SESSIONS):
        stop_view(key)


def register():
    global DRAW_HANDLE
    bpy.utils.register_class(LAZ_OT_canvas)
    DRAW_HANDLE = bpy.types.SpaceImageEditor.draw_handler_add(draw, (), 'WINDOW', 'POST_PIXEL')
    bpy.app.handlers.load_pre.append(reset_views)


def unregister():
    global DRAW_HANDLE
    reset_views(None)
    if reset_views in bpy.app.handlers.load_pre:
        bpy.app.handlers.load_pre.remove(reset_views)
    if DRAW_HANDLE is not None:
        bpy.types.SpaceImageEditor.draw_handler_remove(DRAW_HANDLE, 'WINDOW')
        DRAW_HANDLE = None
    bpy.utils.unregister_class(LAZ_OT_canvas)
