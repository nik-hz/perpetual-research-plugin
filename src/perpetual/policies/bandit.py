from __future__ import annotations
import math
from dataclasses import dataclass, field

@dataclass
class Arm:
    name: str
    config: dict
    pulls: int = 0
    total_reward: float = 0.0

    @property
    def mean_reward(self) -> float:
        if self.pulls == 0:
            return 0.0
        return self.total_reward / self.pulls

@dataclass
class UCB1Bandit:
    """UCB1 multi-armed bandit for hyperparameter sweeps."""
    arms: list[Arm] = field(default_factory=list)

    @property
    def total_pulls(self) -> int:
        return sum(a.pulls for a in self.arms)

    def add_arm(self, name: str, config: dict):
        self.arms.append(Arm(name=name, config=config))

    def ucb1_score(self, arm: Arm) -> float:
        """UCB1 score: mean_reward + sqrt(2 * ln(total_pulls) / arm_pulls)."""
        if arm.pulls == 0:
            return float("inf")  # Unpulled arms have highest priority
        exploration = math.sqrt(2.0 * math.log(self.total_pulls) / arm.pulls)
        return arm.mean_reward + exploration

    def select(self) -> Arm | None:
        """Select the arm with highest UCB1 score."""
        if not self.arms:
            return None
        return max(self.arms, key=self.ucb1_score)

    def update(self, arm_name: str, reward: float):
        """Update an arm with observed reward."""
        for arm in self.arms:
            if arm.name == arm_name:
                arm.pulls += 1
                arm.total_reward += reward
                return
        raise ValueError(f"Unknown arm: {arm_name}")

    def rankings(self) -> list[dict]:
        """Return arms ranked by UCB1 score, descending."""
        scored = [(self.ucb1_score(a), a) for a in self.arms]
        scored.sort(key=lambda x: x[0], reverse=True)
        return [
            {
                "name": a.name,
                "config": a.config,
                "pulls": a.pulls,
                "mean_reward": a.mean_reward,
                "ucb1_score": s if s != float("inf") else "∞",
            }
            for s, a in scored
        ]

    def suggest_batch(self, n: int = 3) -> list[dict]:
        """Suggest a batch of n arms to pull next (by UCB1 ranking)."""
        rankings = self.rankings()
        return rankings[:n]

    # @sig 45813cad | role: from_sweep_config | by: claude-code-993d23b6 | at: 2026-04-30T03:14:40Z
    @classmethod
    def from_sweep_config(cls, config: dict) -> UCB1Bandit:
        """Create a bandit from a sweep config dict.

        Config format:
        {
            "arms": [
                {"name": "lr-1e-3", "config": {"lr": 1e-3}},
                {"name": "lr-1e-4", "config": {"lr": 1e-4}},
            ]
        }
        """
        bandit = cls()
        for arm_cfg in config.get("arms", []):
            bandit.add_arm(arm_cfg["name"], arm_cfg.get("config", {}))
        return bandit
