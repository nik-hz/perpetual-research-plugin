<p align="center">
  <img src="assets/banner.svg" alt="sigil" width="100%"/>
</p>

# sigil

> Hash-anchored provenance comments for code edited by AI agents.

**Status:** v0.1 — Python only, Claude Code only. The on-disk format is harness- and language-agnostic ([SPEC.md](SPEC.md)); more adapters are on the [roadmap](#roadmap).

Plugin that automatically tags and indexes codebases as code agents work on them, building a useful representation and indexing capability. This skill lets agents find their way around dirs without needing humans to force them to use a structure, letting them learn on their own what they find important, what notes and fun facts they find.

When Claude Code edits a Python function, **sigil** stamps a small comment above it:

```python
# @sig 7a3f2d8c | role: filter_short_completions | by: claude-code-abc12345 | at: 2026-04-29T14:32:00Z
def filter_short_completions(samples, min_len=20):
    ...
```

That comment records *who* edited the function, *when*, and a content hash of the body. If a human later modifies the function without re-stamping, the hash mismatches — and on the next session start, sigil tells the agent: *"this function has changed since you last touched it."*

---

## Why?

`git blame` answers "who last touched this line" at the commit level. Sigil answers a different question:

- Which functions has *any* agent touched?
- When you start a new session, has any agent-authored code drifted under you?
- Is the function in front of you something the agent shaped, or something a human revised after?

When humans and AI agents share a codebase, that signal is hard to recover from commits alone — agents tend to batch unrelated edits, and review burden grows with commit churn. Sigil gives you function-level provenance you can audit in seconds.

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

### Pick one

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

To remove later: `/plugin uninstall sigil@nik-hz`, and optionally `/plugin marketplace remove nik-hz` to drop the marketplace registration.

---

## Use

In a Python project with a `.git` at its root:

```sh
sig init
```

That snapshots every existing function into `.sigil/index.json` without inserting any comments — your source stays clean. Commit `.sigil/` so provenance survives clones.

From here, ask Claude Code to edit a function. A `# @sig …` line appears above the def. Modify a stamped function yourself without re-stamping; on the next session start, Claude is told about the drift.

### 30-second verify

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
| `sig init`             | snapshot every `.py` file in the project into the sidecar; doesn't insert any in-source comments |
| `sig list [--drifted]` | list tracked symbols with drift status                                                           |
| `sig drift`            | print drifted symbols, exit `1` if any drift, `0` otherwise                                      |
| `sig show <symbol_id>` | dump the full sidecar record for one symbol as JSON                                              |

`<symbol_id>` is `<rel_path>::<dotted.symbol>` — for example, `data/filters.py::DataFilter.apply`.

The `bin/sig` script also exposes `sig hook post-tool` and `sig hook session-start`. Those are for Claude Code's hook system to call; you shouldn't run them directly.

---

## Tracking scope

**Tracked**
- Top-level Python functions
- Class methods (including dunders)

**Not tracked (yet)**
- Module-level constants
- Class definitions themselves (only the methods within them)
- Decorators (a `@cache` toggle won't trigger drift)
- TypeScript / Rust / Go (Python only in v0.1)
- Concurrent edits across processes (no file-level lock yet)

Full list: [SPEC.md §7](SPEC.md#7-limitations-and-non-goals).

---

## Roadmap

- [ ] TypeScript support (tree-sitter)
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
