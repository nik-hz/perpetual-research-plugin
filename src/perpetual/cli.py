import click
import json
import os
import sys
from pathlib import Path

def get_root() -> Path:
    """Find .perpetual/ directory, searching up from cwd."""
    p = Path.cwd()
    while p != p.parent:
        if (p / ".perpetual").is_dir():
            return p / ".perpetual"
        p = p.parent
    return Path.cwd() / ".perpetual"

def ensure_init(root: Path):
    """Ensure .perpetual/ exists, exit with message if not."""
    if not root.is_dir():
        click.echo(f"Not initialized. Run 'perpetual init' first.", err=True)
        sys.exit(1)

# @sig 42f9aaca | role: cli | by: claude-code-b7232740 | at: 2026-04-29T22:11:32Z
@click.group()
def cli():
    """Perpetual — autonomous research agent."""
    pass

# @sig 4c4eb7e3 | role: init | by: claude-code-b7232740 | at: 2026-04-29T23:53:40Z
@cli.command()
@click.option("--project", "-p", default="", help="Project description")
def init(project):
    """Initialize .perpetual/ in current directory."""
    root = Path.cwd() / ".perpetual"
    root.mkdir(exist_ok=True)

    # Config
    config_path = root / "config.yaml"
    if not config_path.exists():
        import yaml
        cfg = {"project": project or "unnamed", "budget_gpu_hours": 100.0}
        config_path.write_text(yaml.dump(cfg, default_flow_style=False, sort_keys=False))

    # Graph
    from perpetual.graph import Graph
    Graph(root / "graph.db").close()

    # Memory
    from perpetual.memory import Memory
    Memory(root / "memory")

    # Dirs
    (root / "reports").mkdir(exist_ok=True)
    (root / "procedures").mkdir(exist_ok=True)
    (root / "policies").mkdir(exist_ok=True)

    if project:
        mem = Memory(root / "memory")
        mem.write("project.md", f"# Project Context\n\n{project}\n", "init project context")

    click.echo(f"Initialized .perpetual/ in {Path.cwd()}")

@cli.command()
@click.option("--confirm", is_flag=True, default=False, help="Confirm destructive reset")
def reset(confirm):
    """Wipe all experiments, hypotheses, and budget — keep memory and config."""
    root = get_root()
    ensure_init(root)

    if not confirm:
        click.echo(
            "This will permanently delete all experiments, hypotheses, and budget logs.\n"
            "Re-run with --confirm to proceed.",
            err=True,
        )
        sys.exit(1)

    db_path = root / "graph.db"
    if db_path.exists():
        db_path.unlink()
        click.echo("Deleted graph.db")

    # Re-initialise schema (empty DB)
    from perpetual.graph import Graph
    Graph(root / "graph.db").close()
    click.echo("Re-created empty graph.db")

    # Sync hypotheses.md so memory reflects the empty state
    from perpetual.memory import Memory
    mem = Memory(root / "memory")
    mem.write("hypotheses.md", "# Hypotheses\n\n_No hypotheses yet._\n", "reset")
    click.echo("Reset complete.")

# @sig 95039710 | role: status | by: claude-code-b7232740 | at: 2026-04-29T22:11:32Z
@cli.command()
def status():
    """Show current research status."""
    root = get_root()
    ensure_init(root)

    from perpetual.graph import Graph

    graph = Graph(root / "graph.db")

    # Experiments summary
    exps = graph.list_experiments()
    by_status = {}
    for e in exps:
        by_status.setdefault(e["status"], []).append(e)

    click.echo("## Experiments")
    if exps:
        for st, items in sorted(by_status.items()):
            click.echo(f"  {st}: {len(items)}")
    else:
        click.echo("  No experiments yet.")

    # Hypotheses summary
    hyps = graph.list_hypotheses()
    click.echo(f"\n## Hypotheses: {len(hyps)} total")
    for h in hyps:
        click.echo(f"  [{h['status']}] {h['id']}: {h['claim']}")

    # Budget
    total = graph.total_budget()
    click.echo(f"\n## Budget: {total:.1f} GPU-hours used")

    graph.close()

# --- Hypotheses subgroup ---

# @sig a0a86e4f | role: _sync_hypotheses_md | by: claude-code-993d23b6 | at: 2026-04-30T04:52:42Z
def _sync_hypotheses_md(graph, root):
    """Regenerate memory/hypotheses.md from the graph DB."""
    from perpetual.memory import Memory
    hyps = graph.list_hypotheses()
    if not hyps:
        content = "# Hypotheses\n\n_No hypotheses yet._\n"
    else:
        lines = ["# Hypotheses\n"]
        for h in hyps:
            lines.append(
                "- **{id}** [{status}] {claim} "
                "(prior={prior:.2f}, confidence={confidence:.2f})".format(**h)
            )
        content = "\n".join(lines) + "\n"
    mem = Memory(root / "memory")
    mem.write("hypotheses.md", content, "sync hypotheses")

@cli.group()
def hypotheses():
    """Manage hypotheses."""
    pass

# @sig 8e9fee06 | role: hypotheses_add | by: claude-code-993d23b6 | at: 2026-04-30T04:52:57Z
@hypotheses.command("add")
@click.argument("claim")
@click.option("--prior", "-p", type=float, default=0.5, help="Prior probability")
def hypotheses_add(claim, prior):
    """Add a hypothesis."""
    root = get_root()
    ensure_init(root)
    from perpetual.graph import Graph
    graph = Graph(root / "graph.db")
    try:
        h = graph.add_hypothesis(claim=claim, prior=prior)
    except ValueError as e:
        click.echo(str(e), err=True)
        graph.close()
        sys.exit(1)
    click.echo(f"Added {h['id']}: {h['claim']} (prior={h['prior']})")
    _sync_hypotheses_md(graph, root)
    graph.close()

@hypotheses.command("list")
@click.option("--status", "-s", type=click.Choice(["open", "supported", "refuted", "suspended"]), default=None)
def hypotheses_list(status):
    """List hypotheses."""
    root = get_root()
    ensure_init(root)
    from perpetual.graph import Graph
    from tabulate import tabulate
    graph = Graph(root / "graph.db")
    hyps = graph.list_hypotheses(status=status)
    if hyps:
        rows = [(h["id"], h["claim"][:60], f"{h['prior']:.2f}", f"{h['confidence']:.2f}", h["status"]) for h in hyps]
        click.echo(tabulate(rows, headers=["ID", "Claim", "Prior", "Confidence", "Status"], tablefmt="pipe"))
    else:
        click.echo("No hypotheses.")
    graph.close()

# @sig 32709bba | role: hypotheses_update | by: claude-code-993d23b6 | at: 2026-04-30T04:53:21Z
@hypotheses.command("update")
@click.argument("hyp_id")
@click.option("--prior", type=float, default=None)
@click.option("--confidence", type=float, default=None)
@click.option("--status", type=click.Choice(["open", "supported", "refuted", "suspended"]), default=None)
def hypotheses_update(hyp_id, prior, confidence, status):
    """Update a hypothesis."""
    root = get_root()
    ensure_init(root)
    from perpetual.graph import Graph
    graph = Graph(root / "graph.db")
    kwargs = {}
    if prior is not None: kwargs["prior"] = prior
    if confidence is not None: kwargs["confidence"] = confidence
    if status is not None: kwargs["status"] = status
    if not kwargs:
        click.echo("Nothing to update.", err=True)
        return
    try:
        graph.update_hypothesis(hyp_id, **kwargs)
    except KeyError:
        click.echo(f"Hypothesis {hyp_id} not found.", err=True)
        graph.close()
        sys.exit(1)
    except ValueError as e:
        click.echo(str(e), err=True)
        graph.close()
        sys.exit(1)
    click.echo(f"Updated {hyp_id}")
    _sync_hypotheses_md(graph, root)
    graph.close()

# @sig 831a64d4 | role: propose | by: claude-code-993d23b6 | at: 2026-04-30T03:14:50Z
@cli.command()
@click.option("--hypothesis", "-h", "hyp_id", default=None, help="Target hypothesis")
@click.option("--config", "-c", "config_json", default="{}", help="Config JSON")
@click.option("--notes", "-n", default="", help="Notes")
def propose(hyp_id, config_json, notes):
    """Propose an experiment."""
    root = get_root()
    ensure_init(root)
    from perpetual.graph import Graph
    graph = Graph(root / "graph.db")
    try:
        config = json.loads(config_json)
    except json.JSONDecodeError as e:
        click.echo(f"Invalid JSON config: {e}", err=True)
        sys.exit(1)
    if hyp_id and not graph.get_hypothesis(hyp_id):
        click.echo(f"Hypothesis {hyp_id} not found.", err=True)
        graph.close()
        sys.exit(1)
    exp = graph.add_experiment(hypothesis_id=hyp_id, config=config, notes=notes)
    click.echo(f"Proposed {exp['id']}")
    if hyp_id:
        click.echo(f"  targeting hypothesis {hyp_id}")
    click.echo(f"  config: {json.dumps(config)}")
    graph.close()

@cli.command()
@click.argument("exp_id")
def approve(exp_id):
    """Approve a proposed experiment."""
    root = get_root()
    ensure_init(root)
    from perpetual.graph import Graph
    graph = Graph(root / "graph.db")
    exp = graph.get_experiment(exp_id)
    if not exp:
        click.echo(f"Experiment {exp_id} not found.", err=True)
        sys.exit(1)
    if exp["status"] != "proposed":
        click.echo(f"Experiment {exp_id} is {exp['status']}, not proposed.", err=True)
        graph.close()
        sys.exit(1)
    graph.update_experiment(exp_id, status="approved")
    click.echo(f"Approved {exp_id}")
    graph.close()

@cli.command()
@click.argument("exp_id")
@click.argument("outcome", type=click.Choice(["done", "failed"]))
@click.option("--notes", "-n", default="", help="Outcome notes")
def complete(exp_id, outcome, notes):
    """Mark an experiment done or failed."""
    root = get_root()
    ensure_init(root)
    from perpetual.graph import Graph
    graph = Graph(root / "graph.db")
    exp = graph.get_experiment(exp_id)
    if not exp:
        click.echo(f"Experiment {exp_id} not found.", err=True)
        sys.exit(1)
    kwargs = {"status": outcome}
    if notes:
        kwargs["notes"] = notes
    graph.update_experiment(exp_id, **kwargs)
    click.echo(f"Marked {exp_id} as {outcome}")
    graph.close()

@cli.command()
def report():
    """Generate a research report."""
    root = get_root()
    ensure_init(root)
    from perpetual.graph import Graph
    from perpetual.memory import Memory
    from perpetual import gpu
    from perpetual.reports import generate_report, save_report

    graph = Graph(root / "graph.db")
    mem = Memory(root / "memory")

    text = generate_report(graph, mem, gpu)
    path = save_report(text, root / "reports")
    click.echo(text)
    click.echo(f"\nSaved to {path}")
    graph.close()

@cli.command()
def budget():
    """Show budget usage."""
    root = get_root()
    ensure_init(root)
    from perpetual.graph import Graph
    from tabulate import tabulate
    graph = Graph(root / "graph.db")

    total = graph.total_budget()
    click.echo(f"Total GPU-hours: {total:.2f}")

    exps = graph.list_experiments()
    rows = []
    for e in exps:
        h = graph.budget_by_experiment(e["id"])
        if h > 0:
            rows.append((e["id"], f"{h:.2f}"))
    if rows:
        click.echo(tabulate(rows, headers=["Experiment", "GPU-hours"], tablefmt="pipe"))
    graph.close()

@cli.command()
@click.argument("exp_id")
@click.argument("gpu_hours", type=float)
def log_budget(exp_id, gpu_hours):
    """Manually log GPU-hours for a completed experiment."""
    root = get_root()
    ensure_init(root)
    from perpetual.graph import Graph
    graph = Graph(root / "graph.db")
    if not graph.get_experiment(exp_id):
        click.echo(f"Experiment {exp_id} not found.", err=True)
        graph.close()
        sys.exit(1)
    graph.log_budget(exp_id, gpu_hours)
    click.echo(f"Logged {gpu_hours:.2f} GPU-hours for {exp_id}")
    graph.close()

@cli.command()
def gpu_status():
    """Show GPU status."""
    from perpetual.gpu import gpu_summary
    click.echo(gpu_summary())

# --- Procedure subgroup ---

@cli.group()
def procedure():
    """Manage procedure specs."""
    pass

@procedure.command()
@click.argument("spec_path", type=click.Path(exists=True))
def verify(spec_path):
    """Verify a procedure spec."""
    from perpetual.procedures.parser import parse_spec
    from perpetual.procedures.verifier import verify_spec
    spec = parse_spec(spec_path)
    issues = verify_spec(spec)
    if issues:
        click.echo("Issues found:")
        for issue in issues:
            click.echo(f"  - {issue}")
    else:
        click.echo("Spec is valid.")

@procedure.command()
@click.argument("spec_path", type=click.Path(exists=True))
def show(spec_path):
    """Show procedure spec status."""
    from perpetual.procedures.parser import parse_spec
    spec = parse_spec(spec_path)
    click.echo(f"Procedure: {spec.name}")
    click.echo(f"States: {', '.join(spec.states)}")
    click.echo(f"Initial: {spec.initial}")
    click.echo(f"Terminal: {', '.join(spec.terminal)}")
    click.echo(f"Transitions: {len(spec.transitions)}")

# --- Memory subgroup ---

@cli.group()
def memory():
    """Manage research memory."""
    pass

@memory.command("show")
@click.argument("path", default="index.md")
def memory_show(path):
    """Show a memory file."""
    root = get_root()
    ensure_init(root)
    from perpetual.memory import Memory
    mem = Memory(root / "memory")
    try:
        click.echo(mem.read(path))
    except FileNotFoundError:
        click.echo(f"File not found: {path}", err=True)

@memory.command("write")
@click.argument("path")
@click.argument("content")
@click.option("--message", "-m", default=None)
def memory_write(path, content, message):
    """Write to a memory file."""
    root = get_root()
    ensure_init(root)
    from perpetual.memory import Memory
    mem = Memory(root / "memory")
    mem.write(path, content, message)
    click.echo(f"Written to {path}")

@memory.command("list")
@click.argument("subdir", default="")
def memory_list(subdir):
    """List memory files."""
    root = get_root()
    ensure_init(root)
    from perpetual.memory import Memory
    mem = Memory(root / "memory")
    for f in mem.list_files(subdir):
        click.echo(f"  {f}")

# --- Hook subgroup ---

@cli.group()
def hook():
    """Plugin hooks."""
    pass

@hook.command("session-start")
def session_start():
    """SessionStart hook — emit research context."""
    from perpetual.hook import session_start_hook
    session_start_hook()

if __name__ == "__main__":
    cli()
