"""Click CLI: sig init | list | drift | show | hook post-tool | hook session-start."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import click

from sigil.format import now_iso
from sigil.languages import get_adapter, supported_extensions
from sigil.sidecar import Sidecar, drift_status, refresh_sidecar
from sigil.store import _record_from_existing, find_project_root, is_ignored, _EXT_TO_LANG


@click.group()
def cli() -> None:
    """sig — sigil provenance tracker."""


@cli.command()
@click.option("--root", default=".", help="Project root (default: walk up from cwd).")
def init(root: str) -> None:
    """Snapshot all supported source files into the sidecar without inserting in-source comments."""
    root_path = find_project_root(Path(root))
    sidecar = Sidecar(root_path)
    exts = supported_extensions()
    n_new = 0
    for ext in exts:
        for f in root_path.rglob(f"*{ext}"):
            if is_ignored(f, root_path):
                continue
            rel = str(f.resolve().relative_to(root_path.resolve()))
            adapter = get_adapter(f.suffix)
            if adapter is None:
                continue
            language = _EXT_TO_LANG.get(f.suffix, f.suffix.lstrip("."))
            try:
                records = adapter.parse(f, rel)
            except Exception as e:
                click.echo(f"skip {rel}: {e}", err=True)
                continue
            for rec in records:
                if rec.symbol_id not in sidecar.data["symbols"]:
                    sidecar.upsert(rec.symbol_id, _record_from_existing(rel, rec, language))
                    n_new += 1
    sidecar.data["last_full_scan"] = now_iso()
    sidecar.save()
    click.echo(f"snapshotted {n_new} symbols → {sidecar.path}")


@cli.command(name="list")
@click.option("--drifted", is_flag=True)
def list_cmd(drifted: bool) -> None:
    """List tracked symbols and their drift status."""
    root = find_project_root(Path("."))
    sidecar = Sidecar(root)
    refresh_sidecar(root, sidecar)
    for sid, rec in sorted(sidecar.data["symbols"].items()):
        status = drift_status(rec)
        if drifted and status != "drifted":
            continue
        agent = rec.get("sigil_agent") or "-"
        click.echo(f"{status:10s} {sid}  ({agent})")


@cli.command()
def drift() -> None:
    """List drifted symbols. Exit 1 if any drift found, else 0."""
    root = find_project_root(Path("."))
    sidecar = Sidecar(root)
    refresh_sidecar(root, sidecar)
    drifted = [(sid, rec) for sid, rec in sidecar.data["symbols"].items() if drift_status(rec) == "drifted"]
    if not drifted:
        click.echo("no drift")
        sys.exit(0)
    for sid, rec in drifted:
        click.echo(sid)
        click.echo(f"  recorded:  {rec['sigil_hash']} by {rec['sigil_agent']} at {rec['sigil_timestamp']}")
        click.echo(f"  current:   {rec['body_hash']}")
    sys.exit(1)


@cli.command()
@click.argument("symbol_id")
def show(symbol_id: str) -> None:
    """Show the full sidecar record for one symbol."""
    root = find_project_root(Path("."))
    sidecar = Sidecar(root)
    rec = sidecar.data["symbols"].get(symbol_id)
    if not rec:
        click.echo(f"no record: {symbol_id}", err=True)
        sys.exit(2)
    click.echo(json.dumps(rec, indent=2, sort_keys=True))


@cli.group()
def hook() -> None:
    """Internal — Claude Code hook entry points."""


@hook.command("post-tool")
def _hook_post_tool() -> None:
    """PostToolUse handler. Reads the Claude Code JSON payload from stdin."""
    from sigil.hook import hook_post_tool
    hook_post_tool()


@hook.command("session-start")
def _hook_session_start() -> None:
    """SessionStart handler. Reports drifted sigiled functions as additionalContext."""
    from sigil.hook import hook_session_start
    hook_session_start()


def main() -> None:
    cli()
