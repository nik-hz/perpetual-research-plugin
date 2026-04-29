"""sigil — hash-anchored provenance comments for code edited by AI agents."""

from sigil.format import (
    compute_hash,
    format_sigil_line,
    normalize_body,
    parse_sigil_line,
)
from sigil.sidecar import Sidecar, drift_status
from sigil.store import update_for_file

__all__ = [
    "compute_hash",
    "drift_status",
    "format_sigil_line",
    "normalize_body",
    "parse_sigil_line",
    "Sidecar",
    "update_for_file",
]
