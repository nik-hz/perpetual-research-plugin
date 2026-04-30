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
    (root / "runs").mkdir(exist_ok=True)
    (root / "reports").mkdir(exist_ok=True)
    (root / "procedures").mkdir(exist_ok=True)
    (root / "policies").mkdir(exist_ok=True)

    if project:
        mem = Memory(root / "memory")
        mem.write("project.md", f"# Project Context\n\n{project}\n", "init project context")

    click.echo(f"Initialized .perpetual/ in {Path.cwd()}")

# @sig 95039710 | role: status | by: claude-code-b7232740 | at: 2026-04-29T22:11:32Z
@cli.command()
def status():
    """Show current research status."""
    root = get_root()
    ensure_init(root)

    from perpetual.graph import Graph
    from perpetual.runs import RunManager

    graph = Graph(root / "graph.db")
    rm = RunManager(root / "runs")

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

    # Active runs
    runs = rm.scan_runs()
    active = [r for r in runs if r["status"] in ("running", "stale")]
    click.echo(f"\n## Active Runs: {len(active)}")
    for r in active:
        click.echo(f"  {r['exp_id']}: {r['status']}")

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
    """Approve an experiment for execution."""
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
        sys.exit(1)
    graph.update_experiment(exp_id, status="approved")
    click.echo(f"Approved {exp_id}")
    graph.close()

# @sig 3273215c | role: run | by: claude-code-993d23b6 | at: 2026-04-30T03:14:55Z
@cli.command()
@click.argument("exp_id")
@click.argument("command")
@click.option("--gpu", "-g", multiple=True, type=int, help="GPU device indices")
def run(exp_id, command, gpu):
    """Launch an approved experiment."""
    root = get_root()
    ensure_init(root)
    from perpetual.graph import Graph
    from perpetual.runs import RunManager
    graph = Graph(root / "graph.db")
    rm = RunManager(root / "runs")

    exp = graph.get_experiment(exp_id)
    if not exp:
        click.echo(f"Experiment {exp_id} not found.", err=True)
        sys.exit(1)
    if exp["status"] != "approved":
        click.echo(f"Experiment {exp_id} is {exp['status']}, must be approved first.", err=True)
        sys.exit(1)

    gpu_devices = list(gpu) if gpu else None
    result = rm.launch_run(exp_id, command, gpu_devices=gpu_devices)
    graph.update_experiment(exp_id, status="running")
    click.echo(f"Launched {exp_id} (PID {result['pid']})")
    graph.close()

# @sig e5c49c60 | role: kill | by: claude-code-993d23b6 | at: 2026-04-30T04:52:08Z
@cli.command()
@click.argument("exp_id")
def kill(exp_id):
    """Kill a running experiment."""
    root = get_root()
    ensure_init(root)
    from perpetual.runs import RunManager
    from perpetual.graph import Graph
    rm = RunManager(root / "runs")
    graph = Graph(root / "graph.db")
    if rm.kill_run(exp_id):
        graph.update_experiment(exp_id, status="failed")
        click.echo(f"Killed {exp_id}")
    else:
        click.echo(f"Could not kill {exp_id} (not found or already dead).", err=True)
        graph.close()
        sys.exit(1)
    graph.close()

# @sig 6dea8bc8 | role: scan | by: claude-code-993d23b6 | at: 2026-04-30T04:52:24Z
@cli.command()
def scan():
    """Scan runs for completion/crash/stale."""
    root = get_root()
    ensure_init(root)
    from perpetual.runs import RunManager
    from perpetual.graph import Graph
    rm = RunManager(root / "runs")
    graph = Graph(root / "graph.db")

    runs = rm.scan_runs()
    if not runs:
        click.echo("No runs found.")
        return

    for r in runs:
        click.echo(f"  {r['exp_id']}: {r['status']}")
        # Sync status back to graph
        exp = graph.get_experiment(r["exp_id"])
        if exp and exp["status"] == "running":
            if r["status"] == "done":
                graph.update_experiment(r["exp_id"], status="done",
                                        results=r.get("details", {}))
            elif r["status"] in ("crashed", "stale"):
                graph.update_experiment(r["exp_id"], status="failed",
                                        results=r.get("details", {}))
            # Log GPU-hours if the run finished (done or crashed)
            if r["status"] in ("done", "crashed"):
                _log_gpu_budget(graph, rm, r["exp_id"])
    graph.close()


# @sig 6b6f23a0 | role: _log_gpu_budget | by: claude-code-993d23b6 | at: 2026-04-30T04:51:56Z
def _log_gpu_budget(graph, rm, exp_id):
    """Calculate and log GPU-hours for a completed run."""
    # Skip if already logged
    if graph.budget_by_experiment(exp_id) > 0:
        return
    run_data = rm.get_run(exp_id)
    if not run_data:
        return
    # Get duration from done.json or crash.json
    duration_s = 0.0
    for key in ("done", "crash"):
        marker = run_data.get(key, {})
        if "duration_seconds" in marker:
            duration_s = marker["duration_seconds"]
            break
    if duration_s <= 0:
        return
    # Count GPUs from config
    config = run_data.get("config", {})
    gpu_devices = config.get("gpu_devices")
    gpu_count = len(gpu_devices) if gpu_devices else 1
    gpu_hours = gpu_count * duration_s / 3600.0
    graph.log_budget(exp_id, gpu_hours)

@cli.command()
def report():
    """Generate a research report."""
    root = get_root()
    ensure_init(root)
    from perpetual.graph import Graph
    from perpetual.memory import Memory
    from perpetual.runs import RunManager
    from perpetual import gpu
    from perpetual.reports import generate_report, save_report

    graph = Graph(root / "graph.db")
    mem = Memory(root / "memory")
    rm = RunManager(root / "runs")

    text = generate_report(graph, mem, rm, gpu)
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

    # Per-experiment breakdown
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
