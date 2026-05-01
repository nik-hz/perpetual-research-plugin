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


# @sig 1f47e75f | role: generate_report | by: claude-code-b7232740 | at: 2026-04-29T23:53:59Z
def generate_report(graph, memory, gpu_module):
    # type: (Graph, Memory, object) -> str
    """Generate a comprehensive markdown research report."""
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    sections = [
        "# Research Report — {}\n".format(today),
        _section_summary(graph),
        _section_experiments(graph),
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
    by_status = {}
    for e in experiments:
        by_status[e["status"]] = by_status.get(e["status"], 0) + 1
    status_str = ", ".join(f"{v} {k}" for k, v in sorted(by_status.items())) or "none"

    n_hyp = len(hypotheses)
    n_open = sum(1 for h in hypotheses if h["status"] == "open")
    n_supported = sum(1 for h in hypotheses if h["status"] == "supported")
    n_refuted = sum(1 for h in hypotheses if h["status"] == "refuted")

    return (
        "## Summary\n\n"
        "{n_exp} experiments ({status_str}), "
        "{n_hyp} hypotheses ({n_open} open, {n_supported} supported, {n_refuted} refuted).\n"
    ).format(
        n_exp=n_exp, status_str=status_str,
        n_hyp=n_hyp, n_open=n_open, n_supported=n_supported, n_refuted=n_refuted,
    )


def _section_experiments(graph):
    # type: (Graph) -> str
    exps = graph.list_experiments()
    if not exps:
        return "## Experiments\n\nNo experiments recorded.\n"

    rows = []
    for e in exps:
        config_str = e.get("config", "{}")
        if len(config_str) > 60:
            config_str = config_str[:60] + "..."
        rows.append([
            e["id"],
            e.get("hypothesis_id", ""),
            e["status"],
            config_str,
            e.get("notes", ""),
        ])
    table = tabulate(rows, headers=["Exp ID", "Hypothesis", "Status", "Config", "Notes"], tablefmt="pipe")
    return "## Experiments\n\n{}\n".format(table)


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
