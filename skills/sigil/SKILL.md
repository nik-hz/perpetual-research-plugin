---
name: sigil
description: Read and reason about hash-anchored provenance comments (`# @sig ...` / `// @sig ...`) above functions in Python, TypeScript/JavaScript, Go, and Rust. Use when investigating who last touched code, distinguishing agent-edited from human-edited functions, or refining a sigil's role label.
---

# Sigil skill

Functions in projects using this plugin carry provenance comments like:

```python
# @sig 7a3f2d8c | role: filter_short_completions | by: claude-code-abc12345 | at: 2026-04-29T14:32:00Z
def filter_short_completions(samples, min_len=20):
    ...
```

```typescript
// @sig 3b1e9a4f | role: filterShortCompletions | by: claude-code-abc12345 | at: 2026-04-29T14:32:00Z
function filterShortCompletions(samples: string[], minLen = 20): string[] {
    ...
}
```

## Field meanings

- `7a3f2d8c` — first 8 hex of the function body's normalized SHA-256 at the time of the recorded edit. If the current body's hash differs, the function is **drifted** (someone edited it without re-stamping).
- `role` — short label for what the function does. Defaults to the function name on auto-insert; may be refined later.
- `by` — agent identifier. `claude-code-<short_session_id>` for edits made through this harness.
- `at` — UTC timestamp of the recorded edit.

Sidecar lives at `<project_root>/.sigil/index.json`.

## When to use this signal

- User asks "who last touched X" → check the sigil on the function.
- User reports a bug in a function whose sigil is **drifted** → mention the drift before debugging; their post-agent edits may be the cause.
- About to edit a function whose role label is just the function name → consider refining the role to something more descriptive in the same edit (the hook will preserve a human-set role across re-stamps).

## Don't

- Don't manually rewrite the hash in a sigil. It's recomputed on every edit by the hook.
- Don't strip sigils to "tidy up." They're load-bearing provenance.
- Don't treat absence of a sigil as "agent-untouched." It might mean "tracked-but-unstamped" — the function was snapshotted at `sig init` time and hasn't been edited since.
