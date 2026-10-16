# SPDX-License-Identifier: GPL-3.0-or-later
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import bpy
from bpy.app.handlers import persistent
from . import model

EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp"}
THUMBNAILS = {}


class KitError(RuntimeError):
    def __init__(self, code, message):
        self.code = code
        super().__init__(message)


def project_root():
    if not bpy.data.filepath:
        raise KitError("PROJECT_NOT_SAVED", "Save the .blend file before importing references or writing outputs.")
    blend = Path(bpy.data.filepath)
    return blend.parent / (blend.stem + "_agentkit")


def absolute(path):
    return Path(bpy.path.abspath(path)).resolve()


def managed_relative(path, blend_filepath=None):
    base = Path(blend_filepath or bpy.data.filepath).parent
    return "//" + os.path.relpath(Path(path).resolve(), base).replace("\\", "/")


def ensure_storage():
    data = model.root()
    if data.storage_error:
        raise KitError("STORAGE_MIGRATION_FAILED", data.storage_error)
    path = project_root()
    (path / "references").mkdir(parents=True, exist_ok=True)
    data.managed_root = str(path)
    data.saved_filepath = bpy.data.filepath
    return path


def image_for(item):
    path = absolute(item.filepath)
    if not path.is_file():
        return None
    if item.image is not None:
        if item.image.filepath != item.filepath:
            item.image.filepath = item.filepath
            item.image.reload()
        return item.image
    try:
        image = bpy.data.images.load(str(path), check_existing=True)
        image.filepath = item.filepath
        item.image = image
        return image
    except RuntimeError:
        return None


def thumbnail_for(item, max_size=512):
    """Rebuildable GPU-sized previews; originals remain the agent's reference."""
    source = absolute(item.filepath)
    if not source.is_file():
        return None
    key = (str(source), source.stat().st_mtime_ns, max_size)
    if key in THUMBNAILS:
        try:
            if THUMBNAILS[key].name in bpy.data.images:
                return THUMBNAILS[key]
        except ReferenceError:
            pass
    original = image_for(item)
    if original is None:
        return None
    try:
        folder = project_root()/".cache"/"thumbnails"
        folder.mkdir(parents=True, exist_ok=True)
        destination = folder/f"{item.id}_{key[1]}_{max_size}.png"
        if not destination.exists():
            preview = original.copy()
            try:
                w,h = original.size
                factor = min(1, max_size/max(w,h))
                preview.scale(max(1,round(w*factor)), max(1,round(h*factor)))
                preview.filepath_raw = str(destination)
                preview.file_format = 'PNG'
                preview.save()
            finally:
                bpy.data.images.remove(preview)
        thumbnail = bpy.data.images.load(str(destination), check_existing=True)
        THUMBNAILS[key] = thumbnail
        return thumbnail
    except (OSError, RuntimeError, ValueError):
        return original


def import_reference(board, filepath, author="USER", title=""):
    source = Path(filepath).resolve()
    if not source.is_file():
        raise KitError("REFERENCE_NOT_FOUND", str(source))
    if source.suffix.lower() not in EXTENSIONS:
        raise KitError("UNSUPPORTED_IMAGE", "Use PNG, JPEG or WebP images.")
    folder = ensure_storage() / "references"
    item_id = model.uid()
    destination = folder / (item_id + source.suffix.lower())
    shutil.copy2(source, destination)
    try:
        image = bpy.data.images.load(str(destination), check_existing=False)
        if not image.size[0] or not image.size[1]:
            raise ValueError("The image could not be decoded.")
    except Exception as exc:
        destination.unlink(missing_ok=True)
        raise KitError("INVALID_IMAGE", str(exc)) from exc
    position = model.next_x(board)
    item = board.items.add()
    item.id = item_id
    item.kind = "IMAGE"
    item.author = author
    item.title = title or source.stem
    item.filepath = managed_relative(destination)
    image.filepath = item.filepath
    item.image = image
    item.width = 320
    item.height = max(20, 320 * image.size[1] / image.size[0])
    item.x = position
    board.active_item = len(board.items) - 1
    model.changed(board, None)
    return item


def relink_reference(item, filepath):
    # Import a managed copy, never point at a user's external original.
    source = Path(filepath).resolve()
    if source.suffix.lower() not in EXTENSIONS or not source.is_file():
        raise KitError("INVALID_IMAGE", "Choose an existing PNG, JPEG or WebP image.")
    destination = ensure_storage() / "references" / (model.uid() + source.suffix.lower())
    shutil.copy2(source, destination)
    try:
        image = bpy.data.images.load(str(destination), check_existing=False)
        if not image.size[0]:
            raise ValueError("Invalid image")
    except Exception:
        destination.unlink(missing_ok=True)
        raise
    item.filepath = managed_relative(destination)
    image.filepath = item.filepath
    item.image = image
    model.changed(item, None)


def paste_reference(board):
    if os.name != "nt":
        raise KitError("CLIPBOARD_UNSUPPORTED", "Image paste in v1 requires Windows.")
    ensure_storage()
    # Windows' .NET clipboard decoder handles DIB/DIBV5 and transparency. No pip dependency.
    script = """Add-Type -AssemblyName System.Windows.Forms
Add-Type -AssemblyName System.Drawing
if (-not [System.Windows.Forms.Clipboard]::ContainsImage()) { throw 'Clipboard does not contain an image' }
$image = [System.Windows.Forms.Clipboard]::GetImage()
try { $image.Save($env:LAYZ_AGENTKIT_CLIPBOARD, [System.Drawing.Imaging.ImageFormat]::Png) }
finally { $image.Dispose() }
"""
    with tempfile.TemporaryDirectory(prefix="layz_clipboard_") as temp:
        path = Path(temp) / "clipboard.png"
        env = dict(os.environ, LAYZ_AGENTKIT_CLIPBOARD=str(path))
        try:
            result = subprocess.run(
                ["powershell.exe", "-NoProfile", "-NonInteractive", "-STA", "-Command", script],
                capture_output=True, timeout=20, env=env, creationflags=subprocess.CREATE_NO_WINDOW,
            )
        except (OSError, subprocess.TimeoutExpired) as exc:
            raise KitError("CLIPBOARD_FAILED", str(exc)) from exc
        if result.returncode or not path.exists():
            raise KitError("CLIPBOARD_FAILED", result.stderr.decode(errors="replace")[-1500:])
        return import_reference(board, path, title="Clipboard reference")


def arrange(board, columns=4):
    x = y = row_height = 0
    for index, item in enumerate(board.items):
        if index and index % columns == 0:
            x = 0
            y -= row_height + 64
            row_height = 0
        item.x, item.y = x, y
        x += item.width + 32
        row_height = max(row_height, item.height)


@persistent
def before_save(filepath, *_):
    data = model.root(create=False)
    # Blender 5.2 passes the DESTINATION as the first handler argument. Its
    # bpy.data.filepath still points to the OLD file until save completes.
    filepath = filepath if isinstance(filepath, str) else bpy.data.filepath
    if data is None or not filepath:
        return
    new_blend = Path(filepath)
    new_root = new_blend.parent / (new_blend.stem + "_agentkit")
    old_root = Path(data.managed_root) if data.managed_root else new_root
    old_blend = Path(data.saved_filepath) if data.saved_filepath else new_blend
    original_paths = [
        (item, old_blend.parent/item.filepath[2:] if item.filepath.startswith("//") else Path(item.filepath))
        for board in data.boards for item in board.items if item.kind == "IMAGE" and item.filepath
    ]
    try:
        migrations = []
        for item, source in original_paths:
            try:
                relative = source.relative_to(old_root)
            except ValueError:
                relative = Path("references") / source.name
            destination = new_root / relative
            if source.resolve() != destination.resolve() and source.is_file():
                destination.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(source, destination)
            migrations.append((item, destination))
        for item, destination in migrations:
            item.filepath = managed_relative(destination, filepath)
            if item.image:
                # Avoid a second remap from the old blend directory by Blender.
                # item.filepath is the canonical, blend-relative value.
                item.image.filepath = str(destination)
        data.managed_root = str(new_root)
        data.saved_filepath = filepath
        data.storage_error = ""
    except OSError as exc:
        # A failed copy must not reinterpret old relative paths against the new
        # directory. Preserve absolute originals so a later save can retry.
        for item, source in original_paths:
            item.filepath = str(source)
            if item.image:
                item.image.filepath = str(source)
        data.storage_error = "Reference migration failed: " + str(exc)
        print("layZ AgentKit:", data.storage_error)


@persistent
def after_load(_):
    THUMBNAILS.clear()
    data = model.root(create=False)
    if data is not None and bpy.data.filepath:
        # References are relative: moving the .blend and its folder needs no rewrite.
        data.managed_root = str(project_root())
        data.saved_filepath = bpy.data.filepath
        for board in data.boards:
            for item in board.items:
                if item.image and item.filepath:
                    item.image.filepath = item.filepath


def register():
    bpy.app.handlers.save_pre.append(before_save)
    bpy.app.handlers.load_post.append(after_load)


def unregister():
    THUMBNAILS.clear()
    for handlers, fn in ((bpy.app.handlers.save_pre, before_save), (bpy.app.handlers.load_post, after_load)):
        if fn in handlers:
            handlers.remove(fn)
