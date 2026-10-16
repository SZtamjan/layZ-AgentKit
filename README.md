# layZ AgentKit

A free, open-source Blender extension that helps AI agents understand your visual references, inspect models, and deliver static assets for Unity.

**[Download the latest release](https://github.com/SZtamjan/layZ-AgentKit/releases/latest)** · **[Report an issue](https://github.com/SZtamjan/layZ-AgentKit/issues)** · [License](LICENSE)

Put images and notes on a moodboard inside Blender. Your agent reads the references through your existing Python/MCP connection, checks its work using repeatable views and measurements, and exports a versioned FBX package with textures and a validation report.

## What it does

- **Moodboards:** free placement of images and notes, groups, clipboard paste, project-wide style and references assigned to objects or collections.
- **Agent communication:** reference descriptions, Keep/Avoid guidance, stable IDs, revisions and separately marked agent feedback.
- **Model inspection:** triangle budgets, evaluated geometry, dimensions, transforms, UV and texture diagnostics.
- **Visual checks:** six consistent model views and a bounding-box fit check.
- **Unity delivery:** FBX, existing image textures, preview and report, with a separate Blender process verifying the exported geometry and scale.

Version **0.1.1** is intended for **static meshes**. It has been tested with **Blender 5.2.2 LTS on Windows**; sample FBX packages were also imported and checked in **Unity 6000.3.23f1**.

## Requirements

| Requirement | Details |
| --- | --- |
| Operating system | Windows; clipboard support uses Windows PowerShell/.NET |
| Blender | 5.2 or newer; the verified version is 5.2.2 LTS |
| Agent integration | An existing MCP/Python execution connection to Blender; the agent must be able to read local images |
| Unity | Optional; not required to use the moodboard or inspect/export models |

There are no additional Python packages, AI API keys or paid services required by this extension. Set up your agent and its Blender MCP connection separately.

## Install and start

1. Open **[Releases](https://github.com/SZtamjan/layZ-AgentKit/releases/latest)** and expand **Assets**. Download **`layz_agentkit-0.1.1.zip`**. Leave it zipped. The automatic **Source code (zip/tar.gz)** downloads are the repository source, not the installable extension.
2. In Blender choose **Edit → Preferences → Get Extensions → menu in the upper-right → Install from Disk**. Select the downloaded ZIP and enable **layZ AgentKit**. If it is installed but disabled, enable it under **Preferences → Add-ons**.
3. Open the 3D View sidebar with **N**, then the **AgentKit** tab.
4. Save your `.blend` before adding images. Split the editor first if you want the model beside the board, then click **Open Moodboard**.
5. In the Image Editor sidebar, choose **AgentKit** to access boards and descriptions.
6. Click **Copy Agent Instructions** and paste into your agent's chat. Keep using your existing Blender MCP connection.

**First task:** add an image to **Project style**, create an asset board, assign your selected model, and add any Keep/Avoid guidance. Ask the agent to read the AgentKit context for that model before working. You can also run inspection and exports yourself from the sidebar.

**Updating:** download the newer extension ZIP from Releases and use **Install from Disk** again. Keep your `.blend` and its `_agentkit` reference folder together; these are your project data, separate from the installed extension.

### Exporting and importing into Unity

1. Select the mesh objects to deliver. Use **Inspect selected** and review **Show Last Report**.
2. Optionally choose an export folder; otherwise the package goes into the current project's `_agentkit/exports` folder.
3. Click **Export verified Unity package**. Every export gets a new numbered folder.
4. Copy that package's **FBX and `textures` folder together** into your Unity project's `Assets` directory.
5. Set up materials for your render pipeline. Check texture color spaces, normal maps and packed channels. Blender procedural materials are not automatically converted.

### Common questions

- **No AgentKit tab:** check that the extension is enabled, put the pointer over a 3D View or Image Editor, press **N**, and select **AgentKit** in the sidebar.
- **AgentKit panel is empty:** update to 0.1.1 or newer. Version 0.1.0 could fail to initialize a board while drawing the panel.
- **Adding references asks for a saved project:** save the `.blend` first so the extension knows where to keep managed reference copies.
- **The agent cannot see the board:** paste **Copy Agent Instructions** into its chat. It must call the API and open the returned image paths; the board is not automatically sent to the chat.
- **Missing images after moving a project:** move the matching `_agentkit` folder alongside the `.blend`, or use **Relink image** in the sidebar.
- **Paste fails:** copy an actual bitmap or screenshot to the Windows clipboard. A URL or copied text alone is not an image.
- **The ZIP fails to install:** use the extension ZIP from the Release's **Assets**, not GitHub's source archive, and check your Blender version.

The extension runs locally. It does not connect to an AI provider, create a chat, download references or execute text found in references.

## Optional agent skill

The repository includes a **[layz-agentkit skill](skills/layz-agentkit/SKILL.md)** for agents using the installed add-on. It covers reading the right boards, opening reference images, checking models and previews, appending feedback and verifying a requested export. It supports add-on 0.1.x / API 1.0 through your existing connection.

Copy the **entire `skills/layz-agentkit` folder** from this repository into one of Codex's skill locations:

- `<your-project>/.agents/skills/layz-agentkit` for one project;
- `~/.agents/skills/layz-agentkit` for all projects (Windows: `%USERPROFILE%\.agents\skills\layz-agentkit`).

Codex normally detects the new skill automatically; restart it if it does not appear. Invoke **`$layz-agentkit`** in Codex CLI/IDE, or select the skill from the skill picker in the desktop app. Example request: "Use layz-agentkit to inspect the selected shelf against its moodboard and prepare a Unity export under 2,000 triangles."

Other agents that support `SKILL.md` can use the same folder in their own skill location. Install the Blender extension separately; a skill supplies workflow instructions and does not install the add-on or connect MCP. See [OpenAI's skill documentation](https://learn.chatgpt.com/docs/build-skills) for discovery and invocation details.

## Working with references

**Project style** applies to every asset in the file. Create additional boards and assign objects or collections for more specific references. Nested collections and multiple collection memberships are supported; renaming targets preserves their bindings. Every board and entry has a stable ID and revision.

Add PNG, JPEG or WebP images through **Add images**, by dropping files onto an active moodboard, or with **Paste / Ctrl+V**. Images are copied into `//<blend-name>_agentkit/references/`; originals stay untouched. A board can also contain notes and named groups. Titles, roles, Keep and Avoid fields are optional.

Canvas controls:

| Control | Action |
| --- | --- |
| Left drag | Select and move an entry |
| Shift-click | Add/remove an entry from the selection |
| Drag empty space | Box selection |
| Drag the upper-right handle | Scale the selection, preserving image aspect ratios |
| Double-click a grouped entry | Select its group |
| Middle drag / mouse wheel | Pan / zoom around the pointer |
| Home | Frame visible entries |
| A / Ctrl+G | Select all / name a group (empty name ungroups) |
| Delete | Remove selected entries from the board |
| Ctrl+Z / Ctrl+Shift+Z | Undo / Redo |
| Esc | Cancel a drag or close the canvas |

Use the sidebar for descriptions, grouping, layer order, relinking and board assignment. Removing an entry does not delete its managed file. Agent feedback is marked separately and can be hidden. The public agent API only appends feedback; the user can edit every entry.

Board metadata and bindings live in a retained, unlinked Collection datablock named `.layz_agentkit_data`, so they share the file and support Blender Undo without adding scene objects. Do not delete that datablock. Images remain external; **move the `.blend` together with its corresponding `_agentkit` folder**. Save As copies managed images to the new location and keeps the old files. The `.cache` directory only contains rebuildable thumbnails.

## Agent API

Discover the installed extension without assuming its repository name:

```python
import importlib
import bpy

package = next(name for name in bpy.context.preferences.addons.keys()
               if name.rsplit('.', 1)[-1] == 'layz_agentkit')
kit = importlib.import_module(package).api
result = kit.describe()
```

Every result contains `ok`, `api_version`, and either `data` or `error`. Check `ok` before reading `data`. All returned filesystem paths are absolute. Targets may be object names, lists of names, or `{"objects": [...], "collections": [...]}`. Omitting targets uses the current selection. Empty-object targets include their mesh descendants.

```python
context_response = kit.get_context(targets=["Shelf"])
if not context_response["ok"]:
    raise RuntimeError(context_response["error"]["message"])
board_id = context_response["data"]["boards"][0]["id"]

result = kit.get_context(targets=["Shelf"])
result = kit.export_board_preview(board_id, include_agent=False)
result = kit.add_feedback(board_id, text="Check the bevel", image_path="C:/output/front.png")
result = kit.inspect_asset(["Shelf"], triangle_limit=2000)
result = kit.capture_views(["Shelf"], material_mode="NEUTRAL")
result = kit.check_fit(["Box"], volume="ShelfOpening", margin_m=0.01)
result = kit.export_asset(["Shelf"], destination="C:/delivery", name="Shelf")
```

Read images with your agent's image-reading tool; a JSON path alone is not visual evidence. `get_context` keeps user references and agent feedback separate and reports missing images. It returns project style and all applicable asset boards without combining conflicting instructions. Refresh context before major changes and delivery. References do not automatically enter the agent's conversation, and there are no automatic chat notifications.

## Inspection and delivery

Inspection reports evaluated geometry, original/evaluated triangle counts, dimensions in metres, transforms, origin, degenerate triangles, boundary/non-manifold edges, UV issues, material assignments and missing/procedural textures. Open surfaces and UV outside 0–1 may be intentional. Inspection does not fix or rewrite geometry.

The fitting test checks evaluated vertices against the fitting object's **local bounding box**, including rotation and a margin in metres. It is not a collision test or a free-space test inside arbitrary geometry.

Six PNG views use temporary scenes, cameras and lighting. Neutral material is the default; existing materials can be selected. Cycles renders on the CPU for predictable availability. Source cameras, lights, selection and geometry are preserved.

Each export creates a new `Name_v001`, `Name_v002`, … directory containing:

- FBX with evaluated, triangulated mesh copies, existing pivots and relative placement;
- material image textures, excluding moodboard references unless deliberately used by a material;
- a neutral perspective preview;
- `report.json`, `reimport.json`, `reimport.log` and Unity import instructions.

The exporter uses -Z forward / Y up and preserves physical units. A separate clean Blender process reimports the FBX and compares geometry, triangle count and dimensions. Failed validation returns `ok: false` and retains the package for diagnosis. This is independent Blender validation, not an automatic Unity test on every export.

Procedural materials are reported, not baked. UDIM, image-sequence/movie textures, rigs, animation, exact collision tests and automatic Unity materials are outside v1. Review texture color spaces, normal maps and packed channels when preparing Unity materials.

## Development and verification

The runtime uses Blender's bundled Python, GPU and rendering APIs. Windows clipboard import uses a hidden STA Windows PowerShell/.NET process; no pip dependencies are required.

```powershell
# Run from a cloned source repository. Replace this with your Blender executable.
$blender = 'C:\Program Files\Blender Foundation\Blender 5.2\blender.exe'
python tools/build.py
& $blender --command extension validate .\dist\layz_agentkit-0.1.1.zip
& $blender --background --factory-startup --threads 4 --python-exit-code 1 --python tests/integration.py
& $blender --enable-event-simulate --threads 4 --python tests/interactive.py
```

Run the integration test before the interactive and MCP tests; they reuse its fixtures. Test outputs belong under ignored `artifacts/`. The interactive test exits its Blender process, so run it in its own instance. The optional `tests/clipboard.ps1 -Blender <path>` test briefly substitutes a bitmap and restores all captured clipboard formats in `finally`. `tools/prepare_unity_validation.py` prepares an isolated Unity project; run Unity with `-batchmode -nographics -projectPath <that-project> -executeMethod AgentKitValidation.Run -quit`.

`tests/live_probe.py` and `tests/live_install.py` are opt-in helpers for an existing Blender bridge, not part of the automated test suite. The install helper installs/enables the ZIP, inspects selected meshes when present, and saves Blender preferences; it does not save the open scene.

The build script packages only the extension source, README and license. It writes `dist/layz_agentkit-<version>.zip` and `dist/SHA256SUMS.txt`, with normalized text and fixed ZIP metadata for reproducible builds. Run `python tools/check_release.py` to check package contents, source parity, Python syntax, license headers, local paths, CRCs and checksum. Build artifacts, reference images, `.blend` files, local reports, Unity test projects and Python caches are excluded from Git. The extension ZIP is distributed through **Releases → Assets**.

## License and credits

**Free and open source under [GNU GPL v3.0 or later](LICENSE).** No payment, donation, attribution in a game, or credit in the models you create is requested by this project. Commercial use of your own models is welcome.

Redistributing or modifying the extension itself must follow the GPL, including preserving applicable license/copyright notices and providing the required source. This is an open-source license, not a public-domain dedication. Your own models, renders and other artwork do not become GPL simply because you used this tool. Third-party references and textures keep their own rights and licenses. See the [Blender license explanation](https://www.blender.org/about/license/) and [GNU FAQ about program output](https://www.gnu.org/licenses/gpl-faq.html#GPLOutput).
