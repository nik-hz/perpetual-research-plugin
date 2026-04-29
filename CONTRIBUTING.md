# Contributing to Perpetual

## Development Setup

```bash
git clone <repo-url>
cd perpetual-research-agent
pip install -e .
```

### Running Tests

```bash
python -m pytest tests/
```

### Code Style

- Python 3.8 compatible (no `match`, no `TaskGroup`, no `slots=True`)
- `from __future__ import annotations` in every module
- Type comments (`# type: (str) -> bool`) for function signatures when needed for 3.8 compat
- No ORM — direct sqlite3 with explicit locking
- No `eval()` — guard expressions use a Lark parser

## Project Structure

```
src/perpetual/
├── cli.py              # Click CLI entry point
├── graph.py            # SQLite experiment/hypothesis database
├── memory.py           # Git-backed markdown storage
├── runs.py             # Subprocess launch + watchdog threads
├── gpu.py              # nvidia-smi queries
├── hook.py             # Claude Code SessionStart hook
├── reports.py          # Markdown report generation
├── procedures/         # YAML state machines + guard DSL
│   ├── parser.py       # YAML → ProcedureSpec dataclass
│   ├── runtime.py      # State machine execution
│   ├── verifier.py     # Reachability, deadlock, guard validation
│   └── guards.py       # Lark-based guard expression evaluator
└── policies/           # Experiment selection strategies
    ├── hypothesis.py   # Information-gain scoring
    └── bandit.py       # UCB1 multi-armed bandit
```

## Design Principles

1. **No magic** — explicit sqlite, explicit git commits, explicit subprocess management
2. **Thread safety** — all shared state protected by `threading.Lock` or `threading.RLock`
3. **Atomic writes** — write to `.tmp`, then `os.replace` to final path
4. **Graceful degradation** — `pygit2` is optional (memory works without git history), `nvidia-smi` failures return empty lists
5. **No eval()** — guard expressions are parsed by a Lark LALR grammar, never evaluated as Python

## Adding a CLI Command

1. Add a function decorated with `@cli.command()` in `src/perpetual/cli.py`
2. Use `get_root()` and `ensure_init(root)` for project discovery
3. Import heavy dependencies inside the function (keeps CLI startup fast)
4. Use `click.echo()` for output, `click.echo(..., err=True)` for errors

## Adding a Policy

1. Create a module in `src/perpetual/policies/`
2. Accept a `Graph` instance, return scored/ranked results
3. Avoid side effects — policies are read-only advisors

## Guard DSL

The guard grammar lives in `src/perpetual/procedures/guards.py`. To extend it:

1. Add new tokens/rules to `GUARD_GRAMMAR`
2. Add corresponding methods to `GuardEvaluator(Transformer)`
3. Add test cases covering the new syntax
4. Run `perpetual procedure verify` against a spec that uses the new guards
