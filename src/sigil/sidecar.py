"""Sidecar index: JSON store at .sigil/index.json."""

from __future__ import annotations

import json
import os
from pathlib import Path

SIDECAR_DIR = ".sigil"
SIDECAR_FILE = "index.json"


class Sidecar:
    def __init__(self, root: Path):
        self.root = root
        self.path = root / SIDECAR_DIR / SIDECAR_FILE
        self.data = self._load()

    def _load(self) -> dict:
        if self.path.exists():
            return json.loads(self.path.read_text(encoding="utf-8"))
        return {"version": "0.1", "project_root": str(self.root), "last_full_scan": None, "symbols": {}}

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_suffix(".tmp")
        tmp.write_text(json.dumps(self.data, indent=2, sort_keys=True), encoding="utf-8")
        os.replace(tmp, self.path)

    def upsert(self, symbol_id: str, record: dict) -> None:
        self.data["symbols"][symbol_id] = record


def drift_status(record: dict) -> str:
    if not record.get("sigil_present"):
        return "unmanaged"
    if record.get("body_hash") is None:
        return "orphaned"
    return "synced" if record.get("sigil_hash") == record.get("body_hash") else "drifted"


def refresh_sidecar(root: Path, sidecar: Sidecar) -> None:
    """Re-read files referenced in the sidecar and update each symbol's current body_hash."""
    from sigil.languages import get_adapter

    by_file: dict[str, list[str]] = {}
    for sid, rec in sidecar.data["symbols"].items():
        by_file.setdefault(rec["file"], []).append(sid)

    for rel, sids in by_file.items():
        path = root / rel
        if not path.exists():
            for sid in sids:
                sidecar.data["symbols"][sid]["body_hash"] = None
            continue

        adapter = get_adapter(path.suffix)
        if adapter is None:
            continue

        try:
            records = adapter.parse(path, rel)
        except Exception:
            continue

        seen = {r.symbol_id: r for r in records}
        for sid in sids:
            r = seen.get(sid)
            sidecar.data["symbols"][sid]["body_hash"] = r.body_hash if r else None
