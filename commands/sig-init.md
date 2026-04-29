---
description: Initialize sigil tracking for the current project by snapshotting all Python functions
---

Run `${CLAUDE_PLUGIN_ROOT}/bin/sig init` from the current project root and report the result.

This snapshots all Python functions into `.sigil/index.json` without inserting any in-source comments. It is safe to re-run — only new (untracked) symbols are added.

After running, tell the user:
- How many symbols were snapshotted
- That `.sigil/index.json` should be committed to version control
- That auto-stamping is already active via the plugin hooks
