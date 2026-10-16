# layZ AgentKit 0.1.0

Free, open-source tools for AI agents working in Blender: visual reference boards, model inspection, consistent previews and verified static asset export to Unity.

## Download and install

Download **`layz_agentkit-0.1.0.zip`** from **Assets** below. Keep it zipped. GitHub's automatic **Source code** archives are not the installable extension package.

In Blender open **Edit → Preferences → Get Extensions → menu → Install from Disk**, select the ZIP and enable **layZ AgentKit**. Open the **N sidebar → AgentKit → Open Moodboard**. Save your `.blend` before adding references.

Use **Copy Agent Instructions** to tell your agent how to read the board through your existing Blender MCP connection. A model provider or MCP server is not bundled.

## Included

- Image/notes moodboard with groups, object/collection assignments and Windows clipboard paste.
- Agent API with reference context, revisions and separately marked feedback.
- Geometry/UV/texture diagnostics, six preview views and box-fitting checks.
- Versioned FBX packages with existing textures, preview, report and independent Blender reimport validation.

**Requirements:** Windows and Blender 5.2 or newer. Tested on Blender **5.2.2 LTS**. Unity is optional; sample exports were checked in **Unity 6000.3.23f1**. No additional Python packages are needed.

**Verification:** 42 Blender integration checks, 9 interactive UI/Undo checks, Windows clipboard import, a full existing-MCP round trip and 9 Unity import assertions. Package metadata is validated by Blender's extension validator. `SHA256SUMS.txt` provides the ZIP checksum.

**First-release scope:** static meshes; no rig/animation support, exact collision testing, procedural texture baking or automatic Unity materials.

**License:** GPL-3.0-or-later. Free to use; no payment or credits in your games/models are requested. Redistribution of the extension code remains subject to GPL requirements.

See the [README](https://github.com/SZtamjan/layZ-AgentKit#readme) for full installation, controls, Unity import and API examples.
