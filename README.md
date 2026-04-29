<p align="center">
  <img src="assets/banner.svg" alt="sigil" width="100%"/>
</p>

# sigil

> Hash-anchored provenance comments for code edited by AI agents.

**Status:** v0.2 — Python, TypeScript/JavaScript, Go, and Rust. Claude Code only. The on-disk format is harness- and language-agnostic ([SPEC.md](SPEC.md)); more adapters are on the [roadmap](#roadmap).

Plugin that automatically tags and indexes codebases as code agents work on them, building a useful representation and indexing capability. This skill lets agents find their way around dirs without needing humans to force them to use a structure, letting them learn on their own what they find important, what notes and fun facts they find.

When Claude Code edits a function, **sigil** stamps a small comment above it:

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

That comment records *who* edited the function, *when*, and a content hash of the body. If a human later modifies the function without re-stamping, the hash mismatches — and on the next session start, sigil tells the agent: *"this function has changed since you last touched it."*

---

## Quickstart

Run this directly in the Claude Code terminal to activate sigil in your project — updates with `/plugin update sigil@nik-hz`:

```text
/plugin marketplace add nik-hz/sigil
/plugin install sigil@nik-hz
```

That wires up the auto-stamping hook. For local development, optional CLI access (`sig drift`, `sig list`, etc.), and other install paths, see [Install](#install) below.

---

## Why?

`git blame` answers "who last touched this line" at the commit level. Sigil answers a different question:

- Which functions has *any* agent touched?
- When you start a new session, has any agent-authored code drifted under you?
- Is the function in front of you something the agent shaped, or something a human revised after?

Sigil keeps track of more finegrained edits within the codebase to help agents navigate.

---

## Features

- **Auto-stamping.** A `PostToolUse` hook fires on Claude Code's `Edit` / `Write` / `MultiEdit` and updates sigils only on functions whose bodies actually changed.
- **Drift detection.** `sig drift` flags functions where the in-source hash no longer matches the current body. Exits non-zero, so it slots straight into CI.
- **Session-start surfacing.** When Claude Code boots in a sigil-tracked project, drifted functions are surfaced as `additionalContext` to the model — the agent gets a heads-up before debugging code that's shifted under it.
- **Self-bootstrapping.** The bundled `sig` CLI uses [`uv`](https://docs.astral.sh/uv/) PEP 723 metadata. No `pip install`, no virtualenv to manage.
- **Function-level granularity.** Tracks top-level functions and class methods individually, not whole files.
- **Whitespace-tolerant.** Reformatting, indent shifts, and blank-line edits don't trigger drift.

---

## Install

### Requirements

- [`uv`](https://docs.astral.sh/uv/) on PATH — the bundled `sig` CLI uses PEP 723 inline metadata; `uv` resolves its deps on first run.
  ```sh
  curl -LsSf https://astral.sh/uv/install.sh | sh
  ```
- Python 3.10+
- [Claude Code](https://claude.com/claude-code)

### Options

**A. From GitHub** — recommended for normal use. Survives machine moves; updates with `/plugin update sigil@nik-hz`.

```text
/plugin marketplace add nik-hz/sigil
/plugin install sigil@nik-hz
```

**B. From a local clone** — when you're hacking on the plugin itself.

```sh
git clone https://github.com/nik-hz/sigil ~/code/sigil
```

```text
/plugin marketplace add ~/code/sigil
/plugin install sigil@nik-hz
```

**C. Per-session, no install** — fastest iteration loop. Plugin is active for that session only; code changes picked up next launch.

```sh
claude --plugin-dir /path/to/sigil
```

### Updating

```text
/plugin update sigil@nik-hz
```

This pulls the latest version from the GitHub marketplace. After updating, run `/reload-plugins` or start a new session for changes to take effect.

If you installed from a local clone (option B), pull the latest changes instead:

```sh
cd ~/code/sigil && git pull
```

Local-clone changes are picked up on the next Claude Code session. For per-session installs (option C), just point `--plugin-dir` at the updated checkout.

### Uninstalling

```text
/plugin uninstall sigil@nik-hz
```

Optionally remove the marketplace registration too:

```text
/plugin marketplace remove nik-hz
```

This removes the plugin and hooks. Your `.sigil/` directory and any `# @sig` comments in source files are left untouched — they're inert without the plugin.

### `sig` on your shell PATH (optional)

The plugin's hooks invoke the bundled `sig` automatically — no PATH setup is required for stamping or drift surfacing to work. If you also want to run `sig init`, `sig drift`, or `sig list` from your shell, point PATH at the bundled binary:

```sh
git clone https://github.com/nik-hz/sigil ~/code/sigil    # if you don't already have a clone
export PATH="$HOME/code/sigil/bin:$PATH"                  # add to your shell rc to persist
```

Or alias it: `alias sig="$HOME/code/sigil/bin/sig"`.

---

## Use

### 1. Initialize tracking

In any project with a `.git` root, run inside Claude Code:

```
/sig-init
```

Or from your shell (requires `sig` on PATH — see [Install](#install)):

```sh
sig init
```

This snapshots every function in supported languages (`.py`, `.ts`, `.tsx`, `.js`, `.jsx`, `.go`, `.rs`) into `.sigil/index.json` without touching your source. Commit the `.sigil/` directory so provenance survives clones.

### 2. Work normally

Edit code with Claude Code as usual. The plugin handles everything automatically:

- **On every edit** — the `PostToolUse` hook fires, parses the changed file, and stamps any function whose body changed with a `# @sig …` comment.
- **On session start** — the `SessionStart` hook re-parses all tracked files and tells the agent about any functions that have drifted since the last stamp.

You don't need to run any commands. The plugin is silent when nothing has changed.

### 3. Understand what gets stamped

When Claude edits a function, a comment like this appears above it:

```python
# @sig 7a3f2d8c | role: filter_short_completions | by: claude-code-abc12345 | at: 2026-04-29T14:32:00Z
def filter_short_completions(samples, min_len=20):
    ...
```

| field | meaning |
| ----- | ------- |
| `7a3f2d8c` | First 8 hex of the function body's normalized SHA-256 at the time of the edit |
| `role` | Short label for what the function does (defaults to function name, can be refined) |
| `by` | Agent identifier (`claude-code-<session_id>`) |
| `at` | UTC timestamp of the edit |

Functions without a `# @sig` comment are **tracked but unstamped** — they were snapshotted at `sig init` time and haven't been agent-edited since.

### 4. Detect drift

If a human edits a stamped function without re-stamping, the body hash will no longer match the recorded hash. This is **drift**.

Check for drift inside Claude Code:

```
/sig-drift
```

Or from your shell:

```sh
sig drift        # exit 0 = synced, exit 1 = drift detected
```

On the next Claude Code session start, drifted functions are automatically surfaced to the agent so it knows what changed under it.

### 5. Browse tracked symbols

List all tracked functions and their status:

```
/sig-list
```

Or from your shell:

```sh
sig list             # all tracked symbols
sig list --drifted   # only drifted ones
sig show data/filters.py::DataFilter.apply   # full sidecar record as JSON
```

### 6. Investigate provenance

Use the `/sigil` skill inside Claude Code to reason about sigil comments. Useful for:

- **"Who last touched this function?"** — check the `by` and `at` fields in the sigil.
- **"Is this function drifted?"** — if the current body hash differs from the sigil hash, someone edited it after the agent without re-stamping.
- **"Was this written by an agent or a human?"** — a sigil means an agent wrote this version; drift means a human revised it afterward; no sigil means it predates agent involvement (or was snapshotted but never agent-edited).

### Quick demo

```sh
mkdir /tmp/sigil-demo && cd /tmp/sigil-demo && git init -q
cat > demo.py <<'PY'
def add(a, b):
    return a + b
PY
sig init                                  # snapshots demo.py::add
```

Open Claude Code in `/tmp/sigil-demo`, ask "extend `add` to handle strings". After it writes:

```sh
cat demo.py                               # @sig comment now above add
sig drift                                 # exit 0 — synced
sed -i 's/return /return  /' demo.py     # simulate human edit
sig drift                                 # exit 1 — drift detected
```

---

## How it works

```
Claude Code edits app.py    →    PostToolUse hook fires
                                       │
                                       ▼
                            sig parses app.py with libcst
                                       │
              ┌────────────────────────┼────────────────────────┐
              ▼                        ▼                        ▼
   body hash matches sidecar    body hash differs      new function (no record)
   → no change                  → stamp sigil above    → snapshot to sidecar
                                  the def, update         (don't insert comment yet)
                                  sidecar
```

On `SessionStart`, sigil re-parses every tracked file, compares each function's current normalized hash to its recorded sigil hash, and emits any drift to the model as `additionalContext`. If nothing has drifted, the hook is silent.

For a deeper walk-through, see [docs/control-flow.md](docs/control-flow.md). The on-disk format is in [SPEC.md](SPEC.md).

---

## CLI reference

| command                | purpose                                                                                          |
| ---------------------- | ------------------------------------------------------------------------------------------------ |
| `sig init`             | snapshot every supported source file (`.py`, `.ts`, `.tsx`, `.js`, `.jsx`, `.go`, `.rs`) into the sidecar; doesn't insert any in-source comments |
| `sig list [--drifted]` | list tracked symbols with drift status                                                           |
| `sig drift`            | print drifted symbols, exit `1` if any drift, `0` otherwise                                      |
| `sig show <symbol_id>` | dump the full sidecar record for one symbol as JSON                                              |

`<symbol_id>` is `<rel_path>::<dotted.symbol>` — for example, `data/filters.py::DataFilter.apply`.

The `bin/sig` script also exposes `sig hook post-tool` and `sig hook session-start`. Those are for Claude Code's hook system to call; you shouldn't run them directly.

---

## Tracking scope

**Tracked**
- Python: top-level functions, class methods (via libcst)
- TypeScript/JavaScript: function declarations, method definitions, named arrow functions (via tree-sitter)
- Go: function declarations, method declarations with receiver types (via tree-sitter)
- Rust: function items, impl methods (via tree-sitter)

**Not tracked (yet)**
- Module-level constants
- Class definitions themselves (only the methods within them)
- Decorators (a `@cache` toggle won't trigger drift)
- Concurrent edits across processes (no file-level lock yet)

Full list: [SPEC.md §7](SPEC.md#7-limitations-and-non-goals).

---

## Troubleshooting

**Plugin loads but hooks don't fire**
Run `/reload-plugins` and check the output includes `2 hooks`. If not, verify the plugin is enabled: `/plugin` should show `sigil@nik-hz` as active. Check `.claude/settings.local.json` isn't overriding with `"sigil@nik-hz": false`.

**`sig` command not found**
The hooks don't need `sig` on your PATH — they use the bundled binary. If you want to run `sig` from your shell, see [sig on your PATH](#sig-on-your-shell-path-optional).

**`uv` not found**
The `sig` script requires [`uv`](https://docs.astral.sh/uv/). Install it:
```sh
curl -LsSf https://astral.sh/uv/install.sh | sh
```

**0 symbols snapshotted on `sig init`**
Sigil tracks `.py`, `.ts`, `.tsx`, `.js`, `.jsx`, `.go`, and `.rs` files. Make sure you're running from a directory that contains supported source files. Also check that the project root has a `.git` directory — sigil uses it to locate the project boundary.

**Sigils aren't appearing after edits**
Sigils are only stamped on functions whose bodies actually changed. Whitespace-only edits, decorator changes, and comment-only edits are intentionally ignored (see [SPEC.md §3](SPEC.md)).

---

## Roadmap

- [x] TypeScript/JavaScript support (tree-sitter)
- [x] Go support (tree-sitter)
- [x] Rust support (tree-sitter)
- [x] Package refactor (`bin/sig` → `src/sigil/`)
- [ ] `sig watch` — harness-agnostic stamping via filesystem watcher
- [ ] Cross-process locking on the sidecar
- [ ] `sig update <symbol>` for refining role labels from inside the agent
- [ ] Append-only event log alongside the sidecar
- [ ] Opt-out comment marker (`# @sig:skip`)
- [ ] Plugin support for opencode

---

## Contributing

PRs welcome. See [CONTRIBUTING.md](CONTRIBUTING.md) for what makes a good PR and local development setup. The format spec is the contract — anything that writes sigils should be byte-for-byte interoperable with the reference implementation. Inbound contributions are MIT-licensed (`inbound = outbound`); no CLA required.

---

## License

[MIT](LICENSE) © 2026 nik-hz.

---

*A sigil is a mark — a small inscribed sign. The plugin scribes them above functions when an agent passes through.*
