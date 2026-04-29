"""GPU awareness — query nvidia-smi, pick best GPU, render summary."""

from __future__ import annotations

import subprocess
from typing import List, Dict, Optional


def query_gpus() -> List[Dict]:
    """Return a list of dicts describing each GPU, or [] on failure."""
    try:
        result = subprocess.run(
            [
                "nvidia-smi",
                "--query-gpu=index,name,memory.free,memory.total,utilization.gpu",
                "--format=csv,noheader,nounits",
            ],
            capture_output=True,
            text=True,
            timeout=5,
        )
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return []

    if result.returncode != 0:
        return []

    gpus = []
    for line in result.stdout.strip().splitlines():
        parts = [p.strip() for p in line.split(",")]
        if len(parts) < 5:
            continue
        try:
            gpus.append(
                {
                    "index": int(parts[0]),
                    "name": parts[1],
                    "memory_free_mb": int(parts[2]),
                    "memory_total_mb": int(parts[3]),
                    "utilization_pct": int(parts[4]),
                }
            )
        except (ValueError, IndexError):
            continue
    return gpus


def gpu_summary() -> str:
    """Human-readable table of GPU status, or a fallback string."""
    gpus = query_gpus()
    if not gpus:
        return "No GPUs detected."

    from tabulate import tabulate

    rows = [
        [
            g["index"],
            g["name"],
            "{}/{}".format(g["memory_free_mb"], g["memory_total_mb"]),
            g["utilization_pct"],
        ]
        for g in gpus
    ]
    return tabulate(rows, headers=["Index", "Name", "Free/Total MB", "Util%"])


def pick_gpu(min_free_mb: int = 4000) -> Optional[int]:
    """Return index of GPU with most free memory (>= min_free_mb), or None."""
    gpus = query_gpus()
    candidates = [g for g in gpus if g["memory_free_mb"] >= min_free_mb]
    if not candidates:
        return None
    best = max(candidates, key=lambda g: g["memory_free_mb"])
    return best["index"]
