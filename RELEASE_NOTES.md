# layZ AgentKit 0.1.1

Fixes the empty AgentKit panel encountered when opening the extension for the first time. The panel now always shows **Open Moodboard**, and initialization happens when you click it. Thumbnail preparation also runs outside drawing callbacks, so references continue to display after saving.

## Install or update

Download **`layz_agentkit-0.1.1.zip`** from **Assets** below and leave it zipped. In Blender choose **Edit → Preferences → Get Extensions → menu → Install from Disk**, select the ZIP and enable **layZ AgentKit**. Existing users can install over 0.1.0. Your project boards and reference folders remain separate from the installed extension.

Press **N → AgentKit → Open Moodboard**. Save your `.blend`, then use **Add images** or **Paste / Ctrl+V**. See the [README](https://github.com/SZtamjan/layZ-AgentKit#readme) for board controls, agent integration and Unity import instructions.

**Verification:** 42 Blender integration checks and 17 interactive checks, including actual panel drawing before initialization, an empty metadata container, Undo/Redo, and thumbnails after saving. The package is checked against source and validated by Blender's extension validator. Tested with Blender 5.2.2 LTS on Windows.

The optional [agent skill](https://github.com/SZtamjan/layZ-AgentKit/tree/main/skills/layz-agentkit) is available separately in the repository. API 1.0 remains compatible.

**License:** GPL-3.0-or-later. Free to use; no payment or credits in your games/models are requested. Redistribution of the extension code remains subject to GPL requirements.
