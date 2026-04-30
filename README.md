<p align="center">
  <img src="assets/banner.svg" alt="Perpetual" width="100%">
</p>

# Perpetual

An autonomous research agent that tracks hypotheses, proposes experiments, manages GPU runs, and maintains persistent memory — all from the command line.

Perpetual turns a research project into a structured loop: **hypothesize → propose → approve → run → analyze → update memory → repeat**. It keeps a sqlite experiment graph, git-backed markdown memory, subprocess watchdogs for training runs, and a guard DSL for formal procedure specs.

## Quickstart

```bash
# Install
pip install -e .

# Initialize in your project
cd /path/to/your/research
perpetual init --project "Investigating optimal learning rates for LoRA fine-tuning"

# Add a hypothesis
perpetual hypotheses add "Learning rate 3e-4 outperforms 1e-3 on validation loss" --prior 0.6

# Propose an experiment
perpetual propose --hypothesis hyp-001 --config '{"lr": 3e-4, "epochs": 10}' --notes "Baseline comparison"

# Approve and launch
perpetual approve exp-001
perpetual run exp-001 "python train.py --lr 3e-4" --gpu 0

# Monitor
perpetual status
perpetual scan

# When done, generate a report
perpetual report
```

## Installation

Requires Python 3.8+.

### As a Claude Code plugin

```bash
# From the marketplace (when published)
/plugin marketplace add nik-hz/perpetual

# Or install from a local path
/plugin add /path/to/perpetual
```

### Manual (development)

```bash
git clone https://github.com/nik-hz/perpetual-research-plugin.git
cd perpetual-research-plugin
pip install -e .
```

Or run directly without installing (requires [uv](https://docs.astral.sh/uv/)):

```bash
./bin/perpetual status
```

### Dependencies

| Package | Purpose |
|---------|---------|
| click | CLI framework |
| pygit2 | Git operations for memory versioning |
| lark | Guard expression DSL parser |
| pyyaml | Procedure spec parsing |
| tabulate | Table formatting for reports and CLI output |

## Architecture

```
.perpetual/                     # Project-scoped runtime state
├── config.yaml                 # Budget limits, project name
├── graph.db                    # SQLite — experiments, hypotheses, budget log
├── memory/                     # Git-backed markdown files
│   ├── index.md                # Research index
│   ├── hypotheses.md           # Hypothesis log
│   ├── project.md              # Project context
│   ├── details/                # Extended notes
│   └── failures/               # Failure post-mortems
├── runs/                       # One directory per experiment run
│   └── exp-001/
│       ├── config.json         # Launch config
│       ├── metadata.json       # PID, start time, status
│       ├── heartbeat.json      # Watchdog heartbeat (every 30s)
│       ├── stdout.log          # Process stdout
│       ├── stderr.log          # Process stderr
│       ├── done.json           # Written on clean exit (rc=0)
│       └── crash.json          # Written on failure
├── reports/                    # Generated markdown reports
├── procedures/                 # Procedure spec YAML files
└── policies/                   # Policy configuration
```

### Core Components

**Graph** (`perpetual.graph`) — SQLite database with WAL mode and thread-safe locking. Stores experiments (proposed → approved → running → done/failed), hypotheses (open → supported/refuted), and GPU-hour budget logs.

**Memory** (`perpetual.memory`) — Atomic-write markdown files versioned with git (via pygit2). Every write creates a commit. Provides `read`, `write`, `append`, `history`, and `load_context`.

**RunManager** (`perpetual.runs`) — Launches experiment subprocesses, spawns a per-run watchdog thread that writes heartbeats every 30 seconds, detects crashes (non-zero exit or failure patterns like `NaN`, `OOM`, `CUDA error`), and writes `done.json` or `crash.json` marker files.

**GPU** (`perpetual.gpu`) — Queries `nvidia-smi` for free memory and utilization. `pick_gpu()` selects the GPU with the most free memory above a threshold.

**Reports** (`perpetual.reports`) — Generates comprehensive markdown reports covering experiment status, hypothesis standings, GPU state, budget usage, and memory contents.

**Procedures** (`perpetual.procedures`) — YAML-defined state machines with a guard DSL. Supports boolean logic (`and`, `or`, `not`) and comparisons over context variables. The verifier checks for unreachable states, deadlocks, and invalid guard expressions.

**Policies** (`perpetual.policies`) — Experiment selection strategies. `hypothesis.py` ranks hypotheses by information gain (prior × (1 − confidence)). `bandit.py` implements UCB1 for hyperparameter sweeps.

## CLI Reference

### Project Setup

```bash
perpetual init [--project TEXT]     # Create .perpetual/ in current directory
```

### Experiment Lifecycle

```bash
perpetual propose [OPTIONS]         # Propose an experiment
  --hypothesis, -h TEXT             #   Target hypothesis ID
  --config, -c JSON                 #   Config as JSON string
  --notes, -n TEXT                  #   Free-text notes

perpetual approve EXP_ID            # Approve for execution
perpetual run EXP_ID CMD [--gpu N]  # Launch with optional GPU binding
perpetual kill EXP_ID               # SIGTERM the process group
perpetual scan                      # Scan all runs, sync status to graph
```

### Monitoring

```bash
perpetual status                    # Experiments, hypotheses, active runs, budget
perpetual report                    # Generate full markdown report
perpetual budget                    # GPU-hour usage breakdown
perpetual gpu-status                # Live nvidia-smi query
```

### Hypotheses

```bash
perpetual hypotheses add CLAIM [--prior FLOAT]
perpetual hypotheses list [--status open|supported|refuted|suspended]
perpetual hypotheses update HYP_ID [--prior F] [--confidence F] [--status S]
```

### Memory

```bash
perpetual memory show [PATH]        # Default: index.md
perpetual memory write PATH CONTENT [--message TEXT]
perpetual memory list [SUBDIR]
```

### Procedure Specs

```bash
perpetual procedure verify SPEC.yaml
perpetual procedure show SPEC.yaml
```

## Procedure Specs

Procedures define formal experiment workflows as state machines in YAML:

```yaml
name: sft-then-rl
states: [baseline, sft, rl_prep, rl, eval, done, failed]
initial: baseline
terminal: [done, failed]
transitions:
  - from: baseline
    to: sft
    guard: results.baseline_loss < 2.0
    action: "Launch SFT training"
  - from: sft
    to: rl_prep
    guard: results.sft_loss < 0.5
  - from: rl_prep
    to: rl
    guard: always
  - from: rl
    to: eval
    guard: results.reward > 0.8
  - from: eval
    to: done
    guard: results.eval_score > 0.9
  - from: eval
    to: failed
    guard: results.eval_score <= 0.5
```

### Guard DSL

Guards are boolean expressions over a context dictionary. No `eval()` — all parsing goes through a Lark LALR grammar.

```
always                                        # Always true
never                                         # Always false
metric.loss < 0.5                             # Comparison
metric.lr == 0.0003                           # Equality
metric.loss < 0.5 and metric.epochs > 3       # Boolean AND
metric.loss < 0.5 or metric.accuracy > 0.9    # Boolean OR
not metric.loss > 1.0                         # Negation
(metric.a > 0.9 or metric.b > 0.9) and metric.c == "ok"  # Grouping
```

## Claude Code Integration

Perpetual ships as a Claude Code plugin. The `hooks/hooks.json` file registers a `SessionStart` hook that injects research context (memory, run status, GPU state, budget) into every Claude Code session.

### Slash commands

When installed as a plugin, these are available in Claude Code:

| Command | Description |
|---------|-------------|
| `/perpetual-status` | Show research state, highlight anything needing attention |
| `/perpetual-catchup` | Scan runs, summarize progress since last session |
| `/perpetual-propose` | Propose experiments based on hypothesis info-gain scores |
| `/perpetual-report` | Generate and review a full research report |
| `/perpetual-hypotheses` | Add, update, and review hypotheses |
| `/perpetual-budget` | Check GPU budget and current availability |

### SessionStart hook

Every new Claude Code session in a project with `.perpetual/` automatically gets:
- Memory contents (index, project context, hypotheses)
- Run status (active, crashed, completed since last session)
- GPU availability and utilization
- Budget usage percentage
- Experiment summary by status

## Data Model

### Experiments

| Field | Type | Values |
|-------|------|--------|
| id | TEXT | `exp-001`, `exp-002`, ... (auto-increment) |
| hypothesis_id | TEXT | FK to hypotheses, nullable |
| status | TEXT | `proposed` → `approved` → `running` → `done` / `failed` |
| config | JSON | Arbitrary experiment configuration |
| results | JSON | Populated after completion |
| notes | TEXT | Free-text |

### Hypotheses

| Field | Type | Values |
|-------|------|--------|
| id | TEXT | `hyp-001`, `hyp-002`, ... |
| claim | TEXT | Natural language claim |
| prior | REAL | 0.0–1.0, initial belief |
| confidence | REAL | 0.0–1.0, updated after evidence |
| status | TEXT | `open` → `supported` / `refuted` / `suspended` |
| evidence | JSON | List of evidence items |

### Budget Log

Each row records GPU-hours consumed by an experiment. `graph.total_budget()` sums all entries.

## Run Lifecycle

```
launch_run(exp_id, command)
    │
    ├── creates runs/{exp_id}/config.json, metadata.json
    ├── spawns subprocess (start_new_session=True)
    └── starts watchdog thread
            │
            ├── writes heartbeat.json every 30s
            ├── scans stdout/stderr for failure patterns
            │     (NaN, OOM, CUDA error, RuntimeError, out of memory)
            │
            ├── on clean exit (rc=0) → done.json
            ├── on crash (rc≠0) → crash.json + last 50 lines of stderr
            └── if process disappears → scan detects on next `perpetual scan`
```

**Recovery:** When the watchdog thread dies with the CLI process (normal for a non-daemon CLI tool), `perpetual scan` recovers by checking PID liveness. If the PID is dead, it scans stderr for failure patterns to decide whether the run completed or crashed. If the heartbeat is >120 seconds old and the PID is still alive, the run is marked stale.

## License

MIT
