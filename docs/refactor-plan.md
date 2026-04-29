# Refactor plan: monofile → package

Status: **deferred**. Ship v0.1 as-is. Pull this trigger when one of the conditions below is met.

## Why

`bin/sig` is currently a single PEP 723 self-bootstrapping script (~484 lines). That's defensible for v0.1 — zero install ceremony, drops into a Claude Code plugin trivially, readable top-to-bottom — but it has known limits:

- **Testing is awkward.** You can't `from sigil import compute_hash` to unit-test the normalization function. The fragile-bit-I-can't-change-without-breaking-everything (per [SPEC.md §3](../SPEC.md#3-body-normalization--hashing)) deserves a real test battery.
- **No layer isolation.** Pure logic, libcst parsing, sidecar I/O, CLI, hook handlers all in one file. Mocking is harder, refactoring touches more, blast radius is wider.
- **Library is unreusable.** Anyone wanting `compute_hash` from another tool (or a Rust port) has to reimplement. The format is portable per SPEC.md, but the reference implementation isn't usable as a library.
- **Doesn't scale to v0.2.** Adding tree-sitter for TS, `sig watch`, or an opencode bridge will each add 100–200 LOC. Past 1k LOC in one file gets uncomfortable.

## Trigger

Refactor when **either** happens:

1. The first non-Python language adapter is added (TypeScript via tree-sitter is the next planned target).
2. The first real test is written.

Either pushes hard against the monofile.

## Target layout

```
sigil/
├── pyproject.toml                # packaging metadata for `pip install -e .`
├── bin/sig                       # thin shim with PEP 723 metadata; calls sigil.cli:main
├── src/sigil/
│   ├── __init__.py               # re-exports the public API (compute_hash, parse_sigil_line, ...)
│   ├── format.py                 # normalize_body, compute_hash, parse_sigil_line, format_sigil_line
│   ├── languages/
│   │   ├── __init__.py
│   │   ├── base.py               # LanguageAdapter Protocol (parse, insert, update, remove)
│   │   └── python.py             # libcst implementation (_Visitor, _Updater, parse_python_file, write_sigils)
│   ├── sidecar.py                # Sidecar class, refresh_sidecar
│   ├── store.py                  # update_for_file, drift_status, project_root resolution
│   ├── cli.py                    # click commands (init, list, drift, show)
│   └── hook.py                   # claude_post_tool, claude_session_start
└── tests/
    ├── conftest.py
    ├── test_format.py            # battery of normalize_body cases (highest priority)
    ├── test_python_adapter.py    # round-trip insert/update/remove on synthetic files
    └── test_sidecar.py           # atomic write, refresh, drift state
```

## What stays the same

- **Public CLI interface** — `sig init`, `sig list`, `sig drift`, `sig show`, `sig hook post-tool`, `sig hook session-start`. Same flags, same output, same exit codes.
- **Hook contract with Claude Code** — same JSON in/out, same `${CLAUDE_PLUGIN_ROOT}/bin/sig hook ...` paths in `hooks/hooks.json`.
- **On-disk format** — sigil comment grammar and sidecar JSON shape unchanged. SPEC.md doesn't move.
- **PEP 723 self-bootstrap experience** — `bin/sig` still runs under `uv run` with no separate install. The shim's inline metadata stays; it just imports from the package.

## Migration steps

1. **Create `pyproject.toml`** declaring `name = "sigil"`, `dependencies = ["libcst", "click"]`, `[project.scripts] sig = "sigil.cli:main"`. Use hatchling or setuptools; doesn't matter much.

2. **Move code into `src/sigil/` modules** by section, no behavior changes:
   - `format.py` ← lines 35–71 of bin/sig (regex, helpers, parse/format)
   - `languages/python.py` ← lines 90–198 (`_Visitor`, `_Updater`, `parse_python_file`, `write_sigils`)
   - `languages/base.py` ← new file declaring the adapter Protocol; document what TS will need to implement
   - `sidecar.py` ← lines 204–251 (Sidecar class + refresh_sidecar)
   - `store.py` ← lines 257–315 (update_for_file, drift_status, find_project_root, is_ignored)
   - `cli.py` ← lines 321–393 (the click group + init/list/drift/show)
   - `hook.py` ← lines 396–479 (the two hook subcommands; export them as functions cli.py wraps)
   - `__init__.py` ← re-export `compute_hash`, `normalize_body`, `parse_sigil_line`, `format_sigil_line`, `Sidecar`, `update_for_file`, `drift_status`. These are the documented library API.

3. **Replace `bin/sig`** with a shim:

   ```python
   #!/usr/bin/env -S uv run --script
   # /// script
   # requires-python = ">=3.10"
   # dependencies = ["libcst>=1.1", "click>=8.0"]
   # ///
   from sigil.cli import main
   if __name__ == "__main__":
       main()
   ```

   Keep `chmod +x bin/sig`.

4. **Verify the smoke test still passes** — the recipe at the bottom of README.md:
   - `sig init` snapshots without inserting comments
   - PostToolUse hook stamps only changed functions
   - `sig drift` exits 1 on drift
   - `sig hook session-start` emits valid `additionalContext` JSON

5. **Wire pytest** — `pytest`, `pytest-cov` as dev deps in `pyproject.toml [project.optional-dependencies] dev`. Run via `uv run --extra dev pytest`.

6. **Write `test_format.py` first** — this is the fragile contract per SPEC.md §3. A battery of `normalize_body` input/output pairs (whitespace, comments, blank lines, Unicode, decorators, docstrings).

7. **Smoke-test the plugin in a real Claude Code session** (`claude --plugin-dir .`) before tagging v0.2.

## Risk areas

- **PEP 723 + package coexistence.** The `uv run` self-bootstrap on `bin/sig` resolves deps for the script itself; if `sigil.cli` has `import` lines for something not in the inline metadata, bootstrap fails. Keep inline deps in sync with `pyproject.toml`.
- **Atomic-write file lock invariant.** `write_sigils` does `tmp → os.replace`. Make sure that survives the move; refactor shouldn't reorder the write/save sequence in `update_for_file`.
- **Module import vs script execution.** Anyone calling `bin/sig` directly today bypasses Python's import system; after refactor they go through it. Make sure `bin/sig` is still on PYTHONPATH for the package import (PEP 723 + a sibling `src/sigil/` may need a `pyproject.toml [tool.uv] sources = { sigil = { workspace = true } }` or similar — verify before tagging).

## Non-goals for the refactor

- Don't change the hash function or normalization rules. Anything that perturbs hash output invalidates every existing sigil.
- Don't change CLI flags or output formats. Existing hook configurations and CI scripts shouldn't need updates.
- Don't ship to PyPI in the same PR. Refactor first, validate locally, ship to PyPI as a follow-up if/when relevant.

## After the refactor

The package layout enables the things the monofile blocks:

- **TypeScript adapter** (`languages/typescript.py`) implementing the same Protocol.
- **`sig watch` mode** (a new CLI command) for harness-agnostic auto-stamping on file save — the portability play.
- **`sigil` as a real Python library** other tools can import.
- **Real tests with coverage gates in CI.**
