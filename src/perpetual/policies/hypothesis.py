from __future__ import annotations
from perpetual.graph import Graph

def score_hypothesis(h: dict) -> float:
    """Score a hypothesis by information gain potential: prior * (1 - confidence).
    Higher score = more worth investigating."""
    return h["prior"] * (1.0 - h["confidence"])

def rank_hypotheses(graph: Graph) -> list[dict]:
    """Return open hypotheses ranked by information gain score, descending."""
    hyps = graph.list_hypotheses(status="open")
    scored = [(score_hypothesis(h), h) for h in hyps]
    scored.sort(key=lambda x: x[0], reverse=True)
    return [{"hypothesis": h, "score": s} for s, h in scored]

def propose_experiments(graph: Graph, n: int = 3) -> list[dict]:
    """Propose up to n experiments targeting the highest-info-gain hypotheses.

    Returns list of dicts with:
      - hypothesis_id, claim, score
      - suggested_notes (a hint for what experiment to run)

    Only proposes for hypotheses that don't already have a running/proposed experiment.
    """
    ranked = rank_hypotheses(graph)

    # Filter out hypotheses that already have active experiments
    active_hyp_ids = set()
    for exp in graph.list_experiments():
        if exp["status"] in ("proposed", "approved", "running") and exp.get("hypothesis_id"):
            active_hyp_ids.add(exp["hypothesis_id"])

    proposals = []
    for item in ranked:
        h = item["hypothesis"]
        if h["id"] in active_hyp_ids:
            continue

        proposals.append({
            "hypothesis_id": h["id"],
            "claim": h["claim"],
            "score": item["score"],
            "suggested_notes": f"Test hypothesis: {h['claim']}",
        })

        if len(proposals) >= n:
            break

    return proposals
