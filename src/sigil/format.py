"""Pure helpers: normalization, hashing, sigil line parsing/formatting."""

from __future__ import annotations

import hashlib
import re
from datetime import datetime, timezone
from typing import Optional

# Comment prefixes recognized by parse_sigil_line (order matters for matching).
COMMENT_PREFIXES = ("#", "//", ";")

_SIGIL_RE_CACHE: dict[str, re.Pattern[str]] = {}


def sigil_re(prefix: str = "#") -> re.Pattern[str]:
    """Build (and cache) a compiled sigil regex for the given comment prefix."""
    if prefix not in _SIGIL_RE_CACHE:
        escaped = re.escape(prefix)
        _SIGIL_RE_CACHE[prefix] = re.compile(
            rf"^{escaped}\s*@sig\s+([0-9a-f]{{8}})\s*\|\s*role:\s*(.*?)\s*\|\s*by:\s*(.*?)\s*\|\s*at:\s*(\S+)\s*$"
        )
    return _SIGIL_RE_CACHE[prefix]


# Legacy fixed regex for backwards compatibility (Python's '#' prefix).
SIGIL_RE = sigil_re("#")


def normalize_body(body: str) -> str:
    lines = body.split("\n")
    lines = [re.sub(r"\s+", " ", line.strip()) for line in lines]
    while lines and not lines[0]:
        lines.pop(0)
    while lines and not lines[-1]:
        lines.pop()
    return "\n".join(lines)


def compute_hash(body: str) -> str:
    return hashlib.sha256(normalize_body(body).encode("utf-8")).hexdigest()[:8]


def now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def parse_sigil_line(line: str) -> Optional[dict]:
    """Parse a sigil comment line, auto-detecting the comment prefix."""
    stripped = line.strip()
    for prefix in COMMENT_PREFIXES:
        m = sigil_re(prefix).match(stripped)
        if m:
            return {
                "hash": m.group(1),
                "role": m.group(2),
                "agent_id": m.group(3),
                "timestamp": m.group(4),
            }
    return None


def format_sigil_line(hash_: str, role: str, agent_id: str, ts: str, prefix: str = "#") -> str:
    role = role.replace("|", "/")
    agent_id = agent_id.replace("|", "/")
    return f"{prefix} @sig {hash_} | role: {role} | by: {agent_id} | at: {ts}"
