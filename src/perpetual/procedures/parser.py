from __future__ import annotations
from dataclasses import dataclass, field
from pathlib import Path
import yaml

@dataclass
class Transition:
    source: str
    target: str
    guard: str = "always"  # Guard DSL expression
    action: str = ""       # Description of what to do

@dataclass
class ProcedureSpec:
    name: str
    states: list[str]
    initial: str
    terminal: list[str]
    transitions: list[Transition]
    metadata: dict = field(default_factory=dict)

def parse_spec(path: str | Path) -> ProcedureSpec:
    """Parse a YAML procedure spec file."""
    with open(path) as f:
        data = yaml.safe_load(f)

    name = data.get("name", Path(path).stem)
    states = data.get("states", [])
    initial = data.get("initial", states[0] if states else "")
    terminal = data.get("terminal", [])
    if isinstance(terminal, str):
        terminal = [terminal]

    transitions = []
    for t in data.get("transitions", []):
        transitions.append(Transition(
            source=t["from"],
            target=t["to"],
            guard=t.get("guard", "always"),
            action=t.get("action", ""),
        ))

    return ProcedureSpec(
        name=name,
        states=states,
        initial=initial,
        terminal=terminal,
        transitions=transitions,
        metadata=data.get("metadata", {}),
    )

def dump_spec(spec: ProcedureSpec) -> str:
    """Serialize ProcedureSpec back to YAML."""
    data = {
        "name": spec.name,
        "states": spec.states,
        "initial": spec.initial,
        "terminal": spec.terminal,
        "transitions": [
            {"from": t.source, "to": t.target, "guard": t.guard, "action": t.action}
            for t in spec.transitions
        ],
    }
    if spec.metadata:
        data["metadata"] = spec.metadata
    return yaml.dump(data, default_flow_style=False, sort_keys=False)
