"""SessionStart hook handler for Claude Code plugin system.

Called when a Claude Code session starts.  Finds the nearest .perpetual/
directory, loads research context (memory, experiments, GPUs, budget), and
prints a JSON blob to stdout in Claude Code hook format.

All heavy imports are lazy so the hook returns instantly when .perpetual/
is absent.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Optional


def find_root() -> Optional[Path]:
    """Walk up from cwd looking for a .perpetual/ directory."""
    p = Path.cwd()
    while p != p.parent:
        if (p / ".perpetual").is_dir():
            return p / ".perpetual"
        p = p.parent
    return None


# @sig 706fbe2c | role: session_start_hook | by: claude-code-b7232740 | at: 2026-04-29T22:57:46Z
def session_start_hook() -> None:
    root = find_root()
    if not root:
        return

    from perpetual.graph import Graph
    from perpetual.memory import Memory
    from perpetual.gpu import query_gpus, gpu_summary

    parts = []  # type: list[str]

    # ------------------------------------------------------------------
    # Memory context
    # ------------------------------------------------------------------
    try:
        mem = Memory(root / "memory")
        context = mem.load_context()
        if context.strip():
            parts.append(context)
    except Exception:
        pass

    # ------------------------------------------------------------------
    # GPU
    # ------------------------------------------------------------------
    try:
        gpus = query_gpus()
        if gpus:
            parts.append(f"## GPUs\n{gpu_summary()}")
    except Exception:
        pass

    # ------------------------------------------------------------------
    # Budget + experiment summary
    # ------------------------------------------------------------------
    try:
        graph = Graph(root / "graph.db")
        total = graph.total_budget()

        config_path = root / "config.yaml"
        limit = 100.0
        if config_path.exists():
            import yaml
            cfg = yaml.safe_load(config_path.read_text()) or {}
            limit = cfg.get("budget_gpu_hours", 100.0)

        if total > 0 and limit > 0:
            parts.append(
                f"## Budget\n"
                f"{total:.1f} / {limit:.1f} GPU-hours used "
                f"({total / limit * 100:.0f}%)"
            )

        exps = graph.list_experiments()
        if exps:
            by_status = {}  # type: dict[str, list]
            for e in exps:
                by_status.setdefault(e["status"], []).append(e)
            summary = ", ".join(
                f"{len(v)} {k}" for k, v in sorted(by_status.items())
            )
            parts.append(f"## Experiments\n{summary}")

        graph.close()
    except Exception:
        pass

    # ------------------------------------------------------------------
    # Emit hook payload
    # ------------------------------------------------------------------
    if parts:
        output = {
            "additionalContext": (
                "# Perpetual Research Agent\n\n" + "\n\n".join(parts)
            ),
        }
        print(json.dumps(output))


if __name__ == "__main__":
    session_start_hook()
