"""Claude Code hook entry points: PostToolUse and SessionStart."""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import click

from sigil.languages import get_adapter
from sigil.sidecar import Sidecar, drift_status, refresh_sidecar
from sigil.store import find_project_root, update_for_file


def hook_post_tool() -> None:
    """PostToolUse handler. Reads the Claude Code JSON payload from stdin."""
    try:
        payload = json.load(sys.stdin)
    except json.JSONDecodeError:
        sys.exit(0)

    if payload.get("tool_name") not in {"Edit", "Write", "MultiEdit"}:
        sys.exit(0)

    tool_input = payload.get("tool_input") or {}
    file_path_str = tool_input.get("file_path")
    if not file_path_str:
        sys.exit(0)

    file_path = Path(file_path_str)
    if not file_path.exists():
        sys.exit(0)

    # Check if we have an adapter for this file type.
    adapter = get_adapter(file_path.suffix)
    if adapter is None:
        sys.exit(0)

    cwd = payload.get("cwd") or os.getcwd()
    root = find_project_root(Path(cwd))
    session_id = (payload.get("session_id") or "unknown")[:8]
    agent_id = f"claude-code-{session_id}"

    try:
        update_for_file(root, file_path, agent_id)
    except Exception as e:
        click.echo(f"sigil hook: {type(e).__name__}: {e}", err=True)
    sys.exit(0)


def hook_session_start() -> None:
    """SessionStart handler. Reports drifted sigiled functions as additionalContext."""
    try:
        payload = json.load(sys.stdin)
    except json.JSONDecodeError:
        payload = {}

    cwd = payload.get("cwd") or os.getcwd()
    root = find_project_root(Path(cwd))
    sidecar_path = root / ".sigil" / "index.json"
    if not sidecar_path.exists():
        sys.exit(0)

    try:
        sidecar = Sidecar(root)
        refresh_sidecar(root, sidecar)
    except Exception as e:
        click.echo(f"sigil session-start: {type(e).__name__}: {e}", err=True)
        sys.exit(0)

    drifted = [(sid, rec) for sid, rec in sidecar.data["symbols"].items() if drift_status(rec) == "drifted"]
    if not drifted:
        sys.exit(0)

    total = len(sidecar.data["symbols"])
    stamped = sum(1 for r in sidecar.data["symbols"].values() if r.get("sigil_present"))
    lines = [
        f"sigil: {total} tracked symbols, {stamped} agent-stamped, {len(drifted)} drifted since stamp.",
        "",
        "Drifted symbols (human edits since the recorded agent edit — verify before debugging):",
    ]
    for sid, rec in drifted:
        ts = rec.get("sigil_timestamp") or "?"
        agent = rec.get("sigil_agent") or "?"
        lines.append(f"  {sid}  (stamped {ts} by {agent})")

    json.dump(
        {
            "hookSpecificOutput": {
                "hookEventName": "SessionStart",
                "additionalContext": "\n".join(lines),
            }
        },
        sys.stdout,
    )
    sys.exit(0)
