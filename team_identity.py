"""Canonical football identity policy (stdlib-only).

SHA-256/12-hex is the ONLY canonical team-ID namespace.
Provider names must be canonicalized then resolved; never used raw as identity.
"""

from __future__ import annotations

import hashlib
import re

_WS_RE = re.compile(r"\s+")


def canonicalize_name(raw: str) -> str:
    """Mechanically normalize: strip leading/trailing, collapse internal whitespace.

    Preserves case and meaningful words (FC, United, City, ...).
    Raises ValueError on empty/non-string input (explicit unknown handling).
    """
    if not isinstance(raw, str):
        raise ValueError("team name must be a string")
    cleaned = _WS_RE.sub(" ", raw.strip())
    if not cleaned:
        raise ValueError("team name must not be empty")
    return cleaned


def generate_canonical_id(canonical_name: str) -> int:
    """id = int(sha256(canonical_name.encode()).hexdigest()[:12], 16)."""
    canonical = canonicalize_name(canonical_name)
    return int(hashlib.sha256(canonical.encode("utf-8")).hexdigest()[:12], 16)


# Authoritative currently-represented canonical teams (name -> id).
CANONICAL_TEAMS: dict[str, int] = {
    "Arsenal": 221659396777490,
    "Man City": 149534346580314,
    "Real Madrid": 83469380690940,
    "Barcelona": 6794002167939,
    "Liverpool": 116955586910447,
    "Bayern Munich": 18768778449461,
}

# Legacy IDs that must not survive migration.
LEGACY_TEAM_IDS = frozenset({101, 102, 103, 104, 105, 106, 10001, 10002, 10003, 10004})

# Evidence-based provider aliases ONLY. Similar-looking names must NOT be
# added here without evidence. Empty by default; ingestion registers proven
# mappings in team_aliases / team_identity_sources tables.
KNOWN_ALIASES: dict[str, str] = {}


def is_legacy_id(team_id: int) -> bool:
    return team_id in LEGACY_TEAM_IDS


def is_canonical_id_for_name(team_id: int, canonical_name: str) -> bool:
    return team_id == generate_canonical_id(canonical_name)


def resolve_canonical_id(raw_name: str, aliases: dict[str, str] | None = None) -> tuple[str, int]:
    """Resolve raw provider name -> (canonical_name, canonical_id).

    Order: canonicalize -> explicit alias map -> known canonical set ->
    new canonical identity (SHA of canonicalized name, NOT a new namespace).
    Never returns a legacy ID. Raises ValueError on empty input.
    """
    canonical = canonicalize_name(raw_name)
    alias_map = dict(KNOWN_ALIASES)
    if aliases:
        alias_map.update(aliases)
    if canonical in alias_map:
        target = canonicalize_name(alias_map[canonical])
        return target, generate_canonical_id(target)
    if canonical in CANONICAL_TEAMS:
        return canonical, CANONICAL_TEAMS[canonical]
    return canonical, generate_canonical_id(canonical)


__all__ = [
    "CANONICAL_TEAMS",
    "KNOWN_ALIASES",
    "LEGACY_TEAM_IDS",
    "canonicalize_name",
    "generate_canonical_id",
    "is_canonical_id_for_name",
    "is_legacy_id",
    "resolve_canonical_id",
]
