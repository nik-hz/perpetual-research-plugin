# Sigil — Format Specification

> Hash-anchored provenance comments for source code, with drift detection.

This document defines the sigil format: the in-source comment grammar, the body-normalization rules used for hashing, the sidecar index JSON shape, and the drift-status state machine. It is implementation-agnostic — any tool that conforms to this spec can read sigils written by another conforming tool.

The reference implementation is the [sigil](README.md) Claude Code plugin in this repository. Other implementations (other agent harnesses, IDE integrations, CI tools) may also write and read sigils as long as they follow this spec.

---

## 1. Goal

When AI agents and humans both edit a codebase, neither `git blame` nor commit history can cheaply answer:

- Which functions has any agent touched?
- Has a human modified an agent-touched function since?
- When and by what agent run was a function last edited?

Sigils are function-level provenance comments anchored to content hashes. Drift between the recorded hash and the current normalized body hash indicates an edit that bypassed the sigil-aware tooling.

---

## 2. The sigil format

A single-line comment immediately above a function, class, or method definition:

```python
# @sig 7a3f2d8c | role: filter_short_completions | by: claude-code-abc12345 | at: 2026-04-29T14:32:00Z
def filter_short_completions(samples, min_len=20):
    ...
```

Grammar (informal):

```
sigil      := comment_prefix " @sig " hash " | role: " role " | by: " agent_id " | at: " timestamp
hash       := 8 hex chars (lowercase)
role       := UTF-8 text up to 200 chars, no pipe characters
agent_id   := UTF-8 text up to 80 chars, no pipe characters
timestamp  := ISO 8601 UTC, second precision (e.g. `2026-04-29T14:32:00Z`)
```

Comment prefix is language-specific:

| language | prefix |
| --- | --- |
| Python, Bash, Ruby | `#` |
| C, C++, Java, Go, Rust, JS, TS | `//` |
| HTML, XML | `<!-- … -->` |
| Lisp, Clojure | `;` |

Field conventions:

- **`role`** — short human-readable label. The reference implementation defaults to the function's own name on auto-insert; users may refine it. Existing roles are preserved across re-stamps.
- **`agent_id`** — free-form identifier. The reference implementation uses `claude-code-<short_session_id>`. Other implementations should pick a stable, distinguishable prefix (`opencode-…`, `human-<initials>`, etc.).
- **`timestamp`** — UTC, second precision. Always written with the trailing `Z`.

---

## 3. Body normalization & hashing

The hash is the first 8 hex chars of `SHA-256(normalize(body))`. Normalization is applied in this order:

1. Strip the sigil comment line itself if present in the input.
2. For each line: strip leading whitespace, then strip trailing whitespace.
3. For each line: collapse internal runs of whitespace to single spaces.
4. Strip blank lines from the beginning and end of the body. Internal blank lines are preserved.
5. Encode UTF-8.

The normalization is intentionally aggressive: whitespace-only edits should not trigger drift.

**What counts as the "body":**

- The function's `def`/signature line is included (renaming or signature-changes cause drift).
- The indented block under it is included.
- Decorators are **excluded** — `@cache` toggles do not trigger drift. Document this where it matters.
- Docstrings are **included** — editing a docstring causes drift.

**Why 8 hex chars (32 bits):** short enough to be readable in source, consistent with git's short-hash convention. Within a project, symbols are disambiguated by `<file_path>::<dotted_symbol>`, not by hash alone, so collisions in the short hash are tolerable.

---

## 4. Symbol IDs

Symbol identifiers take the form `<relative_file_path>::<dotted_symbol_path>`:

- `data/filters.py::filter_short_completions`
- `data/filters.py::DataFilter`
- `data/filters.py::DataFilter.apply`
- `src/data/filters.ts::filterShortCompletions`

The dotted path follows the language's natural scoping. For overloaded methods or generic instances, append a disambiguator (`::method@1`, `::method@2`) by definition order.

---

## 5. Sidecar index

A JSON file at `<project_root>/.sigil/index.json`:

```json
{
  "version": "0.1",
  "project_root": "/abs/path/to/project",
  "last_full_scan": "2026-04-29T14:30:00Z",
  "symbols": {
    "data/filters.py::filter_short_completions": {
      "file": "data/filters.py",
      "language": "python",
      "line_range": [42, 67],
      "body_hash": "7a3f2d8c",
      "sigil_present": true,
      "sigil_hash": "7a3f2d8c",
      "sigil_role": "filter_short_completions",
      "sigil_agent": "claude-code-abc12345",
      "sigil_timestamp": "2026-04-29T14:32:00Z"
    }
  }
}
```

Field semantics:

- `body_hash` — the current normalized hash, as of the last refresh. Refreshed lazily by tools that perform drift checks.
- `sigil_*` fields — populated only when an in-source sigil exists. `sigil_present: false` means the symbol is *tracked* (snapshotted on first sight) but never stamped.

The sidecar is **derivable** from source — deleting it and re-scanning reconstructs everything except the recorded `sigil_*` fields, which only exist on functions that have been stamped. The sidecar enables fast queries ("all agent-touched functions", "all drift") without re-parsing the codebase. It should be committed to git so provenance survives clones.

---

## 6. Drift state machine

For each tracked symbol, drift status is derived by comparing `body_hash` (current parsed hash) and `sigil_hash` (the hash recorded in the in-source comment):

| status | condition |
| --- | --- |
| `synced` | sigil present, `sigil_hash == body_hash` |
| `drifted` | sigil present, `sigil_hash != body_hash` |
| `unmanaged` | no sigil present (function snapshotted but never stamped) |
| `orphaned` | sigil present, but no current symbol matches (function deleted or renamed) |

Drift is binary: the spec does not classify *what* changed or *whether* the change is meaningful. That's a higher-level concern.

Implications:

- Whitespace-only edits don't cause drift (normalization handles them).
- Renames cause drift, because identifier names are part of the body.
- Adding a comment inside the body causes drift — comments are line content.
- Decorator changes don't cause drift (decorators are excluded from the hash).

---

## 7. Limitations and non-goals

- **Function-level only.** Sigils above modules, classes-as-symbols, or top-level constants are out of scope for v0.1.
- **Decorators excluded** from the hash.
- **No semantic equivalence.** A rename is a new symbol from sigil's perspective.
- **No cryptographic signatures.** The hash detects *change*, not *authorship authenticity*.
- **No history.** The sidecar records the *current* state per symbol. A separate event log could be layered on top.

---

## 8. Open questions

- **Schema versioning at the comment level.** Should each sigil carry a schema version, or is the sidecar's top-level `version` enough? Currently the latter.
- **Opt-out marker.** Should there be a `# @sig:skip` comment to mark a function as deliberately unmanaged? Not in v0.1; defer until use cases surface.
- **Cross-file symbol references** (call graph) — out of scope. Higher-level navigation indexes can be built on top of the sidecar.
