"""Exercise actual Blender modal events and undo in a separate UI process.

blender --enable-event-simulate --python tests/interactive.py
The supplied startup script exits this TEST process when finished.
"""
import json
from pathlib import Path
import sys
import traceback
import bpy
import addon_utils
for installed in list(bpy.context.preferences.addons.keys()):
    if installed.rsplit('.', 1)[-1] == 'layz_agentkit':
        addon_utils.disable(installed, default_set=False)
bpy.context.preferences.view.show_splash = False

REPO = Path(__file__).resolve().parents[1]
OUT = REPO/'artifacts'/'interactive'
OUT.mkdir(parents=True, exist_ok=True)
sys.path.insert(0,str(REPO))
import layz_agentkit as kit
from layz_agentkit import model, storage, canvas

checks = []
steps = []
window = None
area = None
reference_id = None
pointer = (0,0)
draw_errors = []
draw_calls = []
original_scene_objects = None

# Capture failures in actual Blender draw callbacks. The old test initialized
# metadata before ever opening the panel and missed the first-use failure.
original_panel_draw = kit.ui.PanelContents.draw
original_canvas_draw = canvas.draw


def audited_panel_draw(self, context):
    try:
        original_panel_draw(self, context)
        draw_calls.append(self.bl_idname)
    except Exception:
        draw_errors.append(traceback.format_exc())
        raise


def audited_canvas_draw():
    try:
        original_canvas_draw()
    except Exception:
        draw_errors.append(traceback.format_exc())
        raise


kit.ui.PanelContents.draw = audited_panel_draw
canvas.draw = audited_canvas_draw


def check(name, value):
    assert value, name
    checks.append(name)
    print('PASS UI:',name,flush=True)


def mouse(kind, value, x, y, **kwargs):
    global pointer
    pointer = (int(x),int(y))
    window.event_simulate(type=kind,value=value,x=int(x),y=int(y),**kwargs)


def key(kind, ctrl=False, shift=False):
    window.event_simulate(type=kind,value='PRESS',x=pointer[0],y=pointer[1],ctrl=ctrl,shift=shift)
    window.event_simulate(type=kind,value='RELEASE',x=pointer[0],y=pointer[1],ctrl=ctrl,shift=shift)


def region():
    return next(r for r in area.regions if r.type=='WINDOW')


def entry_position():
    item = next(i for i in model.active_board().items if i.id == reference_id)
    view = canvas.state(area)
    reg = region()
    return reg.x+view.pan[0]+(item.x+item.width*.45)*view.zoom, reg.y+view.pan[1]+(item.y+item.height*.5)*view.zoom


def bootstrap_fresh_panel():
    global window, area, original_scene_objects
    kit.register()
    window = bpy.context.window_manager.windows[0]
    area = next(a for a in window.screen.areas if a.type=='VIEW_3D')
    original_scene_objects = [o.name for o in bpy.context.scene.objects]
    assert model.root(create=False) is None
    with bpy.context.temp_override(window=window,area=area):
        bpy.ops.wm.call_panel(name='LAZ_PT_view',keep_open=True)


def verify_fresh_panel():
    check('Fresh sidebar draws without errors',bool(draw_calls) and not draw_errors)
    check('Drawing a fresh sidebar does not create metadata',model.root(create=False) is None)
    with bpy.context.temp_override(window=window):
        bpy.ops.screen.screenshot(filepath=str(OUT/'fresh-panel.png'))
    key('ESC')


def bootstrap_empty_container():
    # Reproduce the user's saved file: metadata ID exists but has no boards.
    container = bpy.data.collections.new(model.DATA_NAME)
    container.use_fake_user = True
    with bpy.context.temp_override(window=window,area=area):
        bpy.ops.wm.call_panel(name='LAZ_PT_view',keep_open=True)


def verify_empty_container():
    check('Sidebar handles an existing empty metadata container',not draw_errors and len(model.root(create=False).boards)==0)
    key('ESC')


def open_first_board():
    with bpy.context.temp_override(window=window,area=area):
        bpy.ops.layz_agentkit.open_moodboard('INVOKE_DEFAULT')


def verify_first_board():
    check('Open Moodboard initializes Project style outside draw',model.active_board(create=False).title=='Project style')
    check('First opening preserves scene objects',[o.name for o in bpy.context.scene.objects]==original_scene_objects)
    canvas.stop_view(area.as_pointer())
    area.type='VIEW_3D'


def setup():
    global reference_id
    bpy.ops.wm.save_as_mainfile(filepath=str(OUT/'interactive.blend'))
    board = model.active_board()
    image = storage.import_reference(board, REPO/'artifacts'/'integration'/'original.png')
    reference_id = image.id
    image.title = 'Shape reference'
    image.keep = 'Frame silhouette'
    model.new_note(board,'User notes: preserve shape; use clean painted metal.')
    # Saving stores absolute image paths; cache rebuilding used to try to
    # rewrite them from inside draw(). Exercise this common user sequence.
    bpy.ops.wm.save_as_mainfile(filepath=str(OUT/'interactive.blend'))
    storage.THUMBNAILS.clear()
    with bpy.context.temp_override(window=window,area=area):
        bpy.ops.layz_agentkit.open_moodboard('INVOKE_DEFAULT')


def verify_saved_image_draw():
    check('Images draw after Save and deferred cache rebuild',not draw_errors and bool(storage.THUMBNAILS))


def start_move():
    global old_x
    board = model.active_board()
    old_x = next(i.x for i in board.items if i.id==reference_id)
    x,y = entry_position()
    mouse('MOUSEMOVE','NOTHING',x,y)
    mouse('LEFTMOUSE','PRESS',x,y)
    # Move above the adjacent note, so its higher z-order doesn't cover the
    # image's scale handle in the next test.
    mouse('MOUSEMOVE','NOTHING',x+80,y+120)
    mouse('LEFTMOUSE','RELEASE',x+80,y+120)


def verify_move():
    item = next(i for i in model.active_board().items if i.id==reference_id)
    check('Dragging moves an actual reference',item.x > old_x+10)
    x,y = entry_position()
    mouse('MOUSEMOVE','NOTHING',x,y)
    key('Z',ctrl=True)


def verify_undo():
    item = next(i for i in model.active_board().items if i.id==reference_id)
    check('Native Undo restores reference position',abs(item.x-old_x)<.01)
    key('Z',ctrl=True,shift=True)


def verify_redo():
    item = next(i for i in model.active_board().items if i.id==reference_id)
    check('Native Redo restores moved reference',item.x>old_x+10)
    view = canvas.state(area)
    reg = region()
    x = reg.x+view.pan[0]+(item.x+item.width)*view.zoom
    y = reg.y+view.pan[1]+(item.y+item.height)*view.zoom
    global original_ratio, original_width
    original_ratio, original_width = item.width/item.height,item.width
    mouse('MOUSEMOVE','NOTHING',x,y)
    mouse('LEFTMOUSE','PRESS',x,y)
    mouse('MOUSEMOVE','NOTHING',x+45,y+25)
    mouse('LEFTMOUSE','RELEASE',x+45,y+25)


def verify_scale():
    item = next(i for i in model.active_board().items if i.id==reference_id)
    check('Corner scaling preserves image aspect ratio',item.width>original_width and abs(item.width/item.height-original_ratio)<1e-5)
    # Exercise multiple selection, grouping and z-order through real UI operators.
    view = canvas.state(area)
    view.selected = {i.id for i in model.active_board().items}
    with bpy.context.temp_override(window=window,area=area):
        bpy.ops.layz_agentkit.group_items(name='Silhouette')
        bpy.ops.layz_agentkit.board_action(action='FRONT')
    check('Multi-selection grouping works',all(i.group=='Silhouette' for i in model.active_board().items))
    area.spaces.active.show_region_ui = True
    area.tag_redraw()


def screenshot():
    with bpy.context.temp_override(window=window):
        bpy.ops.screen.screenshot(filepath=str(OUT/'moodboard.png'))
    check('Canvas screenshot written',(OUT/'moodboard.png').is_file())
    with bpy.context.temp_override(window=window,area=area):
        bpy.ops.wm.call_panel(name='LAZ_PT_image',keep_open=True)


def screenshot_panel():
    with bpy.context.temp_override(window=window):
        bpy.ops.screen.screenshot(filepath=str(OUT/'panel.png'))
    key('ESC')


def close_editor():
    area.type='VIEW_3D'


def verify_closed():
    check('Changing editor stops modal session',not canvas.SESSIONS)
    with bpy.context.temp_override(window=window,area=area):
        bpy.ops.layz_agentkit.open_moodboard('INVOKE_DEFAULT')


def verify_unregister():
    check('Canvas can reopen',bool(canvas.SESSIONS))
    kit.unregister()


def finish():
    check('Unregister removes sessions and drawing handler',not canvas.SESSIONS and canvas.DRAW_HANDLE is None)
    check('All actual panel and canvas draws completed without errors',not draw_errors)
    check('Unregister removes pending thumbnail timer',not bpy.app.timers.is_registered(storage.prepare_pending_thumbnails))
    (OUT/'results.json').write_text(json.dumps({'passed':checks,'count':len(checks)},indent=2),encoding='utf-8')
    bpy.ops.wm.quit_blender()


steps = [bootstrap_fresh_panel,verify_fresh_panel,bootstrap_empty_container,verify_empty_container,open_first_board,verify_first_board,
         setup,verify_saved_image_draw,start_move,verify_move,verify_undo,verify_redo,verify_scale,screenshot,screenshot_panel,
         close_editor,verify_closed,verify_unregister,finish]


def tick():
    if not steps:
        return None
    try:
        steps.pop(0)()
    except Exception:
        try:
            bpy.ops.screen.screenshot(filepath=str(OUT/'failed.png'))
        except Exception:
            pass
        (OUT/'results.json').write_text(json.dumps({'passed':checks,'error':traceback.format_exc()},indent=2),encoding='utf-8')
        traceback.print_exc()
        bpy.ops.wm.quit_blender()
        return None
    return .65


bpy.app.timers.register(tick,first_interval=1.5)
