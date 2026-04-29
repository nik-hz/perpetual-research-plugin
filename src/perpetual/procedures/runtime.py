from __future__ import annotations
from dataclasses import dataclass, field
from perpetual.procedures.parser import ProcedureSpec
from perpetual.procedures.guards import evaluate_guard

@dataclass
class ProcedureState:
    spec: ProcedureSpec
    current: str = ""
    history: list[dict] = field(default_factory=list)

    def __post_init__(self):
        if not self.current:
            self.current = self.spec.initial

    @property
    def is_terminal(self) -> bool:
        return self.current in self.spec.terminal

    def legal_transitions(self, context: dict | None = None) -> list:
        """Return transitions from current state whose guards pass."""
        context = context or {}
        legal = []
        for t in self.spec.transitions:
            if t.source == self.current:
                if evaluate_guard(t.guard, context):
                    legal.append(t)
        return legal

    def advance(self, target: str, context: dict | None = None) -> bool:
        """Advance to target state if there's a legal transition. Returns True if advanced."""
        context = context or {}
        for t in self.legal_transitions(context):
            if t.target == target:
                self.history.append({
                    "from": self.current,
                    "to": target,
                    "guard": t.guard,
                    "action": t.action,
                })
                self.current = target
                return True
        return False

    def force_advance(self, target: str):
        """Advance without checking guards."""
        self.history.append({
            "from": self.current,
            "to": target,
            "guard": "forced",
            "action": "",
        })
        self.current = target

    def summary(self) -> str:
        """Return a summary of current state."""
        legal = self.legal_transitions()
        targets = [t.target for t in legal]
        s = f"State: {self.current}"
        if self.is_terminal:
            s += " (TERMINAL)"
        if targets:
            s += f" -> can go to: {', '.join(targets)}"
        return s
