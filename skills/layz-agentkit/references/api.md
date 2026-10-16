# AgentKit API 1.0 reference

These examples run inside Blender after the discovery/import prefix in `SKILL.md`, in the same execution. All calls return `{"ok": true, "api_version": "1.0", "data": ...}` or `{"ok": false, "api_version": "1.0", "error": {"code": ..., "message": ..., "details": ...}}`.

Use installed `kit.describe()` as the source of truth if the version differs. Targets accept object names, lists of names, or `{"objects": [...], "collections": [...]}`; omitted targets use selected objects. Empty-object targets include mesh descendants. Collections recurse, and duplicate meshes are deduplicated.

## Read the board

```python
result = kit.get_context(targets={"objects": ["Shelf"]})
```

`data` contains `revision`, `blend_file`, resolved `targets`, `boards` and `warnings`. Each board has an `id`, `title`, `revision`, `scope` (`PROJECT`/`ASSET`), bindings, `user_references` and separate `agent_feedback`.

Each entry includes `id`, `short_id`, `kind` (`IMAGE`/`NOTE`), `author`, `title`, `description`, `roles`, `keep`, `avoid`, `group`, absolute image `path` (or null), `missing`, position and size. `get_context` returns metadata; it does not return image pixels.

Use a returned board ID for an overview:

```python
result = kit.export_board_preview(
    board_id=board_id, resolution=1600, include_agent=False,
)
```

This writes a labelled PNG and returns `path`, board ID/revision and item IDs. Match short labels to full IDs in context. It requires a saved project even if an explicit `filepath` is supplied. Read context for full text and original image paths; the overview may be too small for details.

## Inspect and view

```python
result = kit.inspect_asset(targets=["Shelf"], triangle_limit=2000)
```

Read `total_triangles`, `dimensions_m`, `within_triangle_limit`, top-level warnings and each `objects` report. Per-object fields include pre/post-modifier counts, bounds, transforms, origin, degenerate geometry, boundary/non-manifold edges, UV diagnostics, material face counts and image/procedural-texture warnings. A budget violation does not make the envelope `ok: false`.

```python
result = kit.capture_views(
    targets=["Shelf"], resolution=768,
    material_mode="NEUTRAL", views=["front", "perspective"],
)
```

`data.views` maps view names to absolute PNG paths. Supported names: `front`, `back`, `left`, `right`, `top`, `perspective`; omit `views` for all six. Modes: `NEUTRAL` or `MATERIAL`. `destination` is an optional output directory. Capture uses temporary scenes and preserves the user's cameras/lights.

```python
result = kit.check_fit(targets=["Box"], volume="ShelfOpening", margin_m=0.01)
```

The volume must be a mesh object; use a box representing usable space rather than the entire shelf's outer bounds. Read `fits`, per-axis `clearance_m` pairs and the reported method. A failed fit returns a successful API envelope with `fits: false`.

## Append feedback

```python
result = kit.add_feedback(
    board_id=board_id, title="Silhouette check",
    text="The top rail is now closer to the shape reference.",
    image_path=preview_path,
)
```

Supply text, an image, or both. Image feedback copies the file into managed references and requires a saved project; text-only feedback can be created in an unsaved session. Read the returned entry ID/revision before deciding whether a retry would duplicate feedback. There is no public API for editing or deleting existing user references.

## Export static meshes

```python
result = kit.export_asset(
    targets={"collections": ["ShelfAsset"]},
    destination=output_directory, name="WarehouseShelf",
    triangle_limit=2000, preview_resolution=512,
)
```

`data` includes `package`, `fbx`, `report`, neutral `preview`, independent Blender `validation` and warnings. Existing packages are retained and each export creates a new versioned directory.

The package contains evaluated/triangulated mesh copies, existing material image textures, preview, reports, reimport log and Unity instructions. Pivots, relative placement and physical scale are preserved. Ordinary moodboard references are not delivered as asset textures.

Export requires Object Mode. Review the inspection report as well as `validation.ok`: geometric reimport success can coexist with missing texture/procedural-material warnings or an exceeded triangle budget. Open the preview before reporting a visual result.

## Failure handling

- `PROJECT_NOT_SAVED`: references/default output need a project location. Capture/export can use an explicit authorized destination. Board preview cannot bypass this with `filepath`.
- `TARGET_NOT_FOUND` / `NO_MESH_TARGETS`: resolve the user's actual names/selection; do not substitute unrelated objects.
- `OBJECT_MODE_REQUIRED`: switch modes only when consistent with the work and preserve pending edits.
- `STORAGE_MIGRATION_FAILED`: retain the references and report the storage issue; do not delete originals or rewrite paths speculatively.
- `FBX_VALIDATION_FAILED`: `error.details` includes the retained package and diagnostic report. Inspect these before a new export. Successful reimport still does not verify Unity.
- Other failures: use the returned message and actual runtime state to choose a targeted check. Refresh context after a potentially partial feedback operation.
