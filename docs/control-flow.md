# Control flow

How data moves through `bin/sig` on each entry point.

## Path 1 — auto-stamping (`sig hook post-tool`)

Triggered by Claude Code's PostToolUse hook on `Edit` / `Write` / `MultiEdit`.

```
Claude Code  ──stdin JSON──▶  sig hook post-tool
                                   │
                                   ▼
              { tool_name, tool_input.file_path, cwd, session_id }
                                   │
              guard: skip if not Edit/Write/MultiEdit, not .py, file missing
                                   │
                                   ▼
                       find_project_root(cwd)             walks up for .git or .sigil/
                                   │
                                   ▼
                       update_for_file(root, file, agent_id)
                                   │
                       parse_python_file(file)            libcst → list of FunctionRecord
                                   │
            ┌──────────────────────┼──────────────────────┐
            ▼                      ▼                      ▼
       symbol unseen           hash unchanged          hash differs
       → snapshot to sidecar   → no-op                 → stamp + sidecar update
       (sigil_present=False)                           (sigil_present=True)
                                   │
                                   ▼
                       write_sigils(file, targets)        libcst transform → atomic write
                                   │
                                   ▼
                       sidecar.save()                     atomic write of .sigil/index.json
                                   │
                                   ▼
                              exit 0
```

Hook errors never block the agent — they log to stderr and exit 0.

## Path 2 — drift surfacing (`sig hook session-start`)

Triggered by Claude Code's SessionStart hook when the agent boots.

```
Claude Code  ──stdin JSON──▶  sig hook session-start
                                   │
                                   ▼
                       find_project_root(cwd)
                                   │
                       no .sigil/index.json? → exit 0 (silent)
                                   │
                                   ▼
                       Sidecar(root)                     load index
                                   │
                                   ▼
                       refresh_sidecar(root, sidecar)    re-parse every tracked file,
                                                         update body_hash per symbol
                                   │
                                   ▼
                       drift_status(record) == "drifted" filter
                                   │
                       no drift? → exit 0 (silent)
                                   │
                                   ▼
                       emit { hookSpecificOutput: { additionalContext: ... } } on stdout
                                   │
                              exit 0
```

The output is consumed by Claude Code as system context for the model.

## Path 3 — user-driven CLI

| command | flow |
| --- | --- |
| `sig init` | walk `.py` files under root, parse each, snapshot every symbol seen for the first time. Touches sidecar; never inserts in-source comments. |
| `sig list [--drifted]` | load sidecar → `refresh_sidecar` → print each symbol with `drift_status`. |
| `sig drift` | load sidecar → `refresh_sidecar` → print drifted symbols. Exit 1 if any drift, 0 otherwise. |
| `sig show <id>` | load sidecar → dump JSON record for one symbol. |

## State

Two stores:

1. **In-source breadcrumbs** — `# @sig …` comments above functions. Single source of truth for *who stamped what when*.
2. **Sidecar** — `<project>/.sigil/index.json`. Cache of (a) every tracked symbol's last-known body hash, (b) the parsed contents of in-source breadcrumbs. Derivable from source modulo the sigil_* fields, which only exist on stamped functions. Should be committed to git.

## Drift state machine

Computed by `drift_status(record)`:

| state | condition |
| --- | --- |
| `synced` | sigil_present, sigil_hash == body_hash |
| `drifted` | sigil_present, sigil_hash != body_hash |
| `unmanaged` | no sigil_present (snapshotted but never stamped) |
| `orphaned` | sigil_present, but no current symbol matches (function deleted/renamed) |

`body_hash` in the sidecar is stale until `refresh_sidecar` runs; CLI commands and the SessionStart hook always refresh first.
