---
description: List functions whose recorded sigil hash no longer matches the current body
---

Run `sig drift` from the current project root and report any drifted symbols.

For each drifted symbol, show:
- The symbol id (`<file>::<symbol>`)
- The recorded sigil (hash, agent, timestamp)
- The current body hash

If nothing is drifted, say so in one line.
