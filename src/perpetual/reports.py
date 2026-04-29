"""Markdown report generation for the perpetual research agent."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING

from tabulate import tabulate

if TYPE_CHECKING:
    from perpetual.graph import Graph
    from perpetual.memory import Memory
    from perpetual.runs import RunManager


# @sig 1f47e75f | role: generate_report | by: claude-code-b7232740 | at: 2026-04-29T23:53:59Z
def generate_report(graph, memory, run_manager, gpu_module):
    # type: (Graph, Memory, RunManager, object) -> str
    """Generate a comprehensive markdown research report.

    Parameters
    ----------
    graph : Graph
        Experiment/hypothesis database.
    memory : Memory
        Git-backed markdown memory store.
    run_manager : RunManager
        Tracks running experiment subprocesses.
    gpu_module : module
        The ``perpetual.gpu`` module (must expose ``gpu_summary()``).
    """
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    # Scan runs once and reuse the results across sections.
    runs = run_manager.scan_runs()
    sections = [
        "# Research Report \u2014 {}\n".format(today),
        _section_summary(graph),
        _section_active_runs(runs),
        _section_completed(graph),
        _section_failures(graph, runs),
        _section_hypotheses(graph),
        _section_gpu(gpu_module),
        _section_budget(graph),
        _section_memory(memory),
        _section_open_questions(),
    ]
    return "\n".join(sections)


# ------------------------------------------------------------------
# Individual sections
# ------------------------------------------------------------------

def _section_summary(graph):
    # type: (Graph) -> str
    experiments = graph.list_experiments()
    hypotheses = graph.list_hypotheses()

    n_exp = len(experiments)
    n_done = sum(1 for e in experiments if e["status"] == "done")
    n_running = sum(1 for e in experiments if e["status"] == "running")
    n_failed = sum(1 for e in experiments if e["status"] == "failed")

    n_hyp = len(hypotheses)
    n_open = sum(1 for h in hypotheses if h["status"] == "open")
    n_supported = sum(1 for h in hypotheses if h["status"] == "supported")
    n_refuted = sum(1 for h in hypotheses if h["status"] == "refuted")

    return (
        "## Summary\n\n"
        "{n_exp} experiments total ({n_done} done, {n_running} running, {n_failed} failed), "
        "{n_hyp} hypotheses ({n_open} open, {n_supported} supported, {n_refuted} refuted).\n"
    ).format(
        n_exp=n_exp, n_done=n_done, n_running=n_running, n_failed=n_failed,
        n_hyp=n_hyp, n_open=n_open, n_supported=n_supported, n_refuted=n_refuted,
    )


# @sig 8c1c4a71 | role: _section_active_runs | by: claude-code-b7232740 | at: 2026-04-29T23:54:04Z
def _section_active_runs(runs):
    # type: (list[dict]) -> str
    active = [r for r in runs if r["status"] == "running"]
    if not active:
        return "## Active Runs\n\nNo active runs.\n"

    rows = [[r["exp_id"], r["status"], r.get("started_at", "")] for r in active]
    table = tabulate(rows, headers=["Exp ID", "Status", "Started At"], tablefmt="pipe")
    return "## Active Runs\n\n{}\n".format(table)


def _section_completed(graph):
    # type: (Graph) -> str
    done = graph.list_experiments(status="done")
    if not done:
        return "## Completed Experiments\n\nNone yet.\n"

    rows = []
    for e in done:
        config_str = e.get("config", "{}")
        if len(config_str) > 80:
            config_str = config_str[:80] + "..."
        rows.append([
            e["id"],
            e.get("hypothesis_id", ""),
            config_str,
            e.get("notes", ""),
        ])
    table = tabulate(rows, headers=["Exp ID", "Hypothesis", "Config", "Notes"], tablefmt="pipe")
    return "## Completed Experiments\n\n{}\n".format(table)


# @sig 4065f97d | role: _section_failures | by: claude-code-b7232740 | at: 2026-04-29T23:54:09Z
def _section_failures(graph, runs):
    # type: (Graph, list[dict]) -> str
    failed = graph.list_experiments(status="failed")
    crashed_runs = [r for r in runs if r["status"] == "crashed"]

    parts = ["## Failures\n"]

    if not failed and not crashed_runs:
        parts.append("No failures recorded.\n")
        return "\n".join(parts)

    if failed:
        rows = [[e["id"], e.get("hypothesis_id", ""), e.get("notes", "")] for e in failed]
        table = tabulate(rows, headers=["Exp ID", "Hypothesis", "Notes"], tablefmt="pipe")
        parts.append(table)
        parts.append("")

    if crashed_runs:
        parts.append("**Crashed runs (crash.json detected):**\n")
        for r in crashed_runs:
            parts.append("- `{}` (started {})".format(r["exp_id"], r.get("started_at", "unknown")))
        parts.append("")

    return "\n".join(parts)


def _section_hypotheses(graph):
    # type: (Graph) -> str
    hyps = graph.list_hypotheses()
    if not hyps:
        return "## Hypotheses\n\nNo hypotheses recorded.\n"

    rows = [
        [h["id"], h["claim"], h["prior"], h["confidence"], h["status"]]
        for h in hyps
    ]
    table = tabulate(
        rows, headers=["ID", "Claim", "Prior", "Confidence", "Status"], tablefmt="pipe",
    )
    return "## Hypotheses\n\n{}\n".format(table)


def _section_gpu(gpu_module):
    # type: (object) -> str
    try:
        summary = gpu_module.gpu_summary()
    except Exception:
        summary = "Unable to query GPU status."
    return "## GPU Status\n\n{}\n".format(summary)


def _section_budget(graph):
    # type: (Graph) -> str
    total = graph.total_budget()
    parts = ["## Budget\n"]
    parts.append("**Total GPU-hours consumed:** {:.2f}\n".format(total))

    experiments = graph.list_experiments()
    budget_rows = []
    for e in experiments:
        hours = graph.budget_by_experiment(e["id"])
        if hours > 0:
            budget_rows.append([e["id"], "{:.2f}".format(hours)])

    if budget_rows:
        table = tabulate(budget_rows, headers=["Exp ID", "GPU-hours"], tablefmt="pipe")
        parts.append(table)
        parts.append("")
    else:
        parts.append("No per-experiment GPU-hours logged.\n")

    return "\n".join(parts)


def _section_memory(memory):
    # type: (Memory) -> str
    try:
        content = memory.read("index.md")
    except FileNotFoundError:
        content = "_(index.md not found)_"

    if len(content) > 500:
        content = content[:500] + "\n\n_(truncated)_"

    return "## Memory Updates\n\n{}\n".format(content)


def _section_open_questions():
    # type: () -> str
    return "## Open Questions\n\n_Add open questions here._\n"


# ------------------------------------------------------------------
# Persistence
# ------------------------------------------------------------------

def save_report(report, reports_dir):
    # type: (str, str | Path) -> Path
    """Save *report* to ``reports_dir/{ISO_timestamp}.md`` and return the path."""
    reports_dir = Path(reports_dir)
    reports_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H%M%SZ")
    dest = reports_dir / "{}.md".format(timestamp)
    dest.write_text(report, encoding="utf-8")
    return dest
