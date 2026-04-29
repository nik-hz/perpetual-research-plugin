# sigil

> Hash-anchored provenance comments for code edited by AI agents.

When Claude Code edits a Python function, **sigil** stamps a small comment above it:

```python
# @sig 7a3f2d8c | role: filter_short_completions | by: claude-code-abc12345 | at: 2026-04-29T14:32:00Z
def filter_short_completions(samples, min_len=20):
    ...
```

That comment records *who* edited the function, *when*, and a content hash of the body. If a human later modifies the function without re-stamping, the hash mismatches — and on the next session start, sigil tells the agent: *"this function has changed since you last touched it."*

---

## What problem does this solve?

`git blame` answers "who last touched this line" at the commit level. Sigil answers a different question:

- Which functions has any agent touched?
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

## Quick start

Requires `uv` and Python 3.10+ on PATH.

Install via Claude Code's plugin system:

```text
/plugin marketplace add nik-hz/sigil
/plugin install sigil@nik-hz
```

Or run it directly without installing:

```sh
claude --plugin-dir /path/to/sigil
```

In your project, snapshot existing functions so the hook has a baseline:

```sh
cd your-python-project
sig init
```

That's it. Now ask Claude Code to edit a Python function — a `# @sig …` line appears above the def. Edit one yourself without re-stamping; on the next session start the agent gets told.

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

The format itself is implementation-agnostic — see [SPEC.md](SPEC.md) for the comment grammar, normalization rules, sidecar JSON shape, and drift state machine.

---

## CLI reference

| command | purpose |
| --- | --- |
| `sig init` | snapshot every `.py` file in the project into the sidecar; doesn't insert any in-source comments |
| `sig list [--drifted]` | list tracked symbols with drift status |
| `sig drift` | print drifted symbols, exit `1` if any drift, `0` otherwise |
| `sig show <symbol_id>` | dump the full sidecar record for one symbol as JSON |

`<symbol_id>` is `<rel_path>::<dotted.symbol>` — for example, `data/filters.py::DataFilter.apply`.

The `bin/sig` script also exposes `sig hook post-tool` and `sig hook session-start`. Those are for Claude Code's hook system to call; you shouldn't run them directly.

---

## What's tracked

- Top-level Python functions
- Class methods (including dunders)
- Sidecar at `<project>/.sigil/index.json` — commit this to git so provenance survives clones

## What's not tracked (yet)

- Module-level constants
- Class definitions themselves (only the methods within them)
- Decorators (a `@cache` toggle won't trigger drift)
- TypeScript / Rust / Go (Python only in v0.1)
- Concurrent edits across processes (no file-level lock yet)

See [SPEC.md §7](SPEC.md#7-limitations-and-non-goals) for the full list.

---

## Layout

```
.claude-plugin/
  plugin.json          plugin manifest read by Claude Code
  marketplace.json     marketplace manifest for /plugin install
bin/sig                CLI entry point (PEP 723, runs under `uv`)
hooks/hooks.json       PostToolUse + SessionStart hook config
commands/              auto-discovered slash commands (/sig-drift, /sig-list)
skills/sigil/SKILL.md  auto-discovered skill: how to read sigils
SPEC.md                format spec (implementation-agnostic)
README.md              you are here
```

---

## Roadmap

- [ ] TypeScript support (tree-sitter)
- [ ] Cross-process locking on the sidecar
- [ ] `sig update <symbol>` for refining role labels from inside the agent
- [ ] Append-only event log alongside the sidecar
- [ ] Opt-out comment marker (`# @sig:skip`)
- [ ] Plugin support for opencode

---

## Why "sigil"?

A sigil is a mark — a small inscribed sign. The plugin scribes them above functions when an agent passes through.

---

## Contributing

Issues and PRs welcome. The format spec is the contract; implementations may vary, but anything that writes sigils should be byte-for-byte interoperable with the reference implementation.

## License

[MIT](LICENSE).
