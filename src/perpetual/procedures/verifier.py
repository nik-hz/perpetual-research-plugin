from __future__ import annotations
from perpetual.procedures.parser import ProcedureSpec
from perpetual.procedures.guards import parse_guard

def verify_spec(spec: ProcedureSpec) -> list[str]:
    """Verify a procedure spec for common issues. Returns list of issue strings."""
    issues = []

    # Check initial state exists
    if spec.initial not in spec.states:
        issues.append(f"Initial state '{spec.initial}' not in states list")

    # Check terminal states exist
    for t in spec.terminal:
        if t not in spec.states:
            issues.append(f"Terminal state '{t}' not in states list")

    # Check transition states exist
    for tr in spec.transitions:
        if tr.source not in spec.states:
            issues.append(f"Transition source '{tr.source}' not in states list")
        if tr.target not in spec.states:
            issues.append(f"Transition target '{tr.target}' not in states list")

    # Check for unreachable states (BFS from initial)
    reachable = set()
    queue = [spec.initial] if spec.initial in spec.states else []
    while queue:
        s = queue.pop(0)
        if s in reachable:
            continue
        reachable.add(s)
        for tr in spec.transitions:
            if tr.source == s and tr.target not in reachable:
                queue.append(tr.target)

    unreachable = set(spec.states) - reachable
    for s in unreachable:
        issues.append(f"State '{s}' is unreachable from initial state")

    # Check terminal states are reachable
    for t in spec.terminal:
        if t in spec.states and t not in reachable:
            issues.append(f"Terminal state '{t}' is unreachable")

    # Check for potential deadlocks (non-terminal states with no outgoing transitions)
    for s in spec.states:
        if s not in spec.terminal:
            outgoing = [tr for tr in spec.transitions if tr.source == s]
            if not outgoing:
                issues.append(f"Potential deadlock: state '{s}' has no outgoing transitions and is not terminal")

    # Validate guard expressions parse
    for tr in spec.transitions:
        try:
            if tr.guard not in ("always", "never"):
                parse_guard(tr.guard)
        except Exception as e:
            issues.append(f"Invalid guard '{tr.guard}' on {tr.source}->{tr.target}: {e}")

    return issues
