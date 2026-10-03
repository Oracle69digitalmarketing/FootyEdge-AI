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


class UnknownTeamIdentityError(ValueError):
    """Raised when a provider name has no canonical/alias registration.

    Callers must register an alias (team_aliases) or use the explicit
    registration path (allow_create=True) instead of silently minting
    a possibly-duplicate identity from spelling variation.
    """


class TeamIdentityConflictError(ValueError):
    """Raised when identity mappings disagree about one canonical team.

    Cases: same provider ID mapped to two teams, same alias mapped to
    two teams, or provider mapping and alias pointing to different teams.
    Never resolved by silently picking one side.
    """


def is_legacy_id(team_id: int) -> bool:
    return team_id in LEGACY_TEAM_IDS


def is_canonical_id_for_name(team_id: int, canonical_name: str) -> bool:
    return team_id == generate_canonical_id(canonical_name)


def resolve_canonical_id(
    raw_name: str,
    aliases: dict[str, str] | None = None,
    allow_create: bool = False,
) -> tuple[str, int]:
    """Resolve raw provider name -> (canonical_name, canonical_id).

    known provider identity -> canonical team
    known explicit alias    -> canonical team
    unknown provider identity -> raises UnknownTeamIdentityError
        unless allow_create=True (explicit deterministic registration path).

    Unknown entities are never silently merged and never auto-minted by
    default, so spelling variants (Man Utd vs Manchester United,
    Nott'm vs Nottm vs Nottingham Forest) cannot create separate teams
    unless identity evidence is registered. allow_create=True mints the
    stable SHA-256/12-hex of the canonicalized name (same namespace,
    explicit path only). Never returns a legacy ID. Raises ValueError
    on empty input.
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
    if allow_create:
        return canonical, generate_canonical_id(canonical)
    raise UnknownTeamIdentityError(
        f"Unknown team identity {canonical!r}: register an alias in "
        "team_aliases/team_identity_sources or call with allow_create=True."
    )


__all__ = [
    "CANONICAL_TEAMS",
    "KNOWN_ALIASES",
    "LEGACY_TEAM_IDS",
    "TeamIdentityConflictError",
    "UnknownTeamIdentityError",
    "canonicalize_name",
    "generate_canonical_id",
    "is_canonical_id_for_name",
    "is_legacy_id",
    "resolve_canonical_id",
    "resolve_canonical_id_db",
]


def _reject_legacy_id(team_id: int, context: str) -> int:
    """Raise if a team ID belongs to the retired legacy namespace."""
    if is_legacy_id(team_id):
        raise ValueError(f"Legacy team ID {team_id} rejected ({context}).")
    return team_id


def _rows_of(result) -> list:
    """Extract the row list from a Supabase select result (real or stub)."""
    data = result.data if hasattr(result, "data") else result
    return list(data or [])


def _canonical_team_name(supabase, team_id: int) -> str:
    """Return the stored canonical name for a mapped team ID.

    The teams row owns the canonical spelling; alias/provider text must
    never overwrite it. A mapping without a team row is a data conflict.
    """
    rows = _rows_of(
        supabase.table("teams").select("id, name").eq("id", team_id).execute()
    )
    names = {row["name"] for row in rows}
    if len(names) != 1:
        raise TeamIdentityConflictError(
            f"Mapped team ID {team_id} has no unique teams row."
        )
    (name,) = names
    return canonicalize_name(name)


def resolve_canonical_id_db(
    raw_name: str,
    source: str,
    supabase,
    external_team_id=None,
    allow_create: bool = False,
) -> tuple[str, int]:
    """Resolve a provider team name to its canonical team via the database.

    Single reusable policy boundary. Precedence:
      1. explicit alias (team_aliases)
      2. provider identity mapping (team_identity_sources, source + ID)
      3. exact canonical team name (teams)
      4. explicit controlled registration (allow_create=True)
      5. otherwise raise UnknownTeamIdentityError

    No fuzzy similarity, edit distance, token or substring matching:
    every lookup is an exact match. Never returns a legacy ID.
    Registration mints only the immutable SHA-256/12-hex namespace,
    never overwrites an existing team, and never creates an alias
    implicitly.
    """
    canonical = canonicalize_name(raw_name)

    has_provider_id = external_team_id is not None and str(external_team_id) != ""
    if has_provider_id:
        if not isinstance(source, str) or not source.strip():
            raise ValueError("source is required with external_team_id.")
        try:
            supplied = int(str(external_team_id))
        except (TypeError, ValueError):
            supplied = None
        if supplied is not None:
            _reject_legacy_id(supplied, "supplied external_team_id")

    mapped_team_id = None
    if has_provider_id:
        mapping_rows = _rows_of(
            supabase.table("team_identity_sources")
            .select("team_id")
            .eq("source", source)
            .eq("external_team_id", str(external_team_id))
            .execute()
        )
        mapped_ids = {row["team_id"] for row in mapping_rows}
        if len(mapped_ids) > 1:
            raise TeamIdentityConflictError(
                f"Provider identity ({source!r}, {external_team_id!r}) maps to "
                f"multiple teams: {sorted(mapped_ids)}."
            )
        if mapped_ids:
            (mapped_team_id,) = mapped_ids

    alias_rows = _rows_of(
        supabase.table("team_aliases").select("team_id").eq("alias", canonical).execute()
    )
    alias_ids = {row["team_id"] for row in alias_rows}
    if len(alias_ids) > 1:
        raise TeamIdentityConflictError(
            f"Alias {canonical!r} maps to multiple teams: {sorted(alias_ids)}."
        )
    alias_team_id = next(iter(alias_ids), None)

    if mapped_team_id is not None and alias_team_id is not None:
        if mapped_team_id != alias_team_id:
            raise TeamIdentityConflictError(
                f"Provider identity ({source!r}, {external_team_id!r}) points to "
                f"{mapped_team_id} but alias {canonical!r} points to "
                f"{alias_team_id}."
            )
        team_id = _reject_legacy_id(mapped_team_id, "provider/alias mapping")
        return _canonical_team_name(supabase, team_id), team_id
    if mapped_team_id is not None:
        team_id = _reject_legacy_id(mapped_team_id, "provider mapping")
        return _canonical_team_name(supabase, team_id), team_id
    if alias_team_id is not None:
        team_id = _reject_legacy_id(alias_team_id, "alias mapping")
        return _canonical_team_name(supabase, team_id), team_id

    team_rows = _rows_of(
        supabase.table("teams").select("id, name").eq("name", canonical).execute()
    )
    team_ids = {row["id"] for row in team_rows}
    if len(team_ids) > 1:
        raise TeamIdentityConflictError(
            f"Canonical name {canonical!r} resolves to multiple team IDs: "
            f"{sorted(team_ids)}."
        )
    if team_ids:
        (team_id,) = team_ids
        return canonical, _reject_legacy_id(team_id, "teams table")

    if not allow_create:
        raise UnknownTeamIdentityError(
            f"Unknown team identity {canonical!r}: register an alias in "
            "team_aliases/team_identity_sources or call with allow_create=True."
        )

    team_id = generate_canonical_id(canonical)
    _reject_legacy_id(team_id, "registration")
    try:
        supabase.table("teams").insert({"id": team_id, "name": canonical}).execute()
    except Exception:
        existing = _rows_of(
            supabase.table("teams").select("id, name").eq("name", canonical).execute()
        )
        if not existing:
            raise
        (team_id,) = {row["id"] for row in existing}
        return canonical, _reject_legacy_id(team_id, "teams table")
    if has_provider_id:
        try:
            supabase.table("team_identity_sources").insert(
                {
                    "team_id": team_id,
                    "source": source,
                    "external_team_id": str(external_team_id),
                    "external_name": raw_name,
                }
            ).execute()
        except Exception:
            current = _rows_of(
                supabase.table("team_identity_sources")
                .select("team_id")
                .eq("source", source)
                .eq("external_team_id", str(external_team_id))
                .execute()
            )
            current_ids = {row["team_id"] for row in current}
            if current_ids != {team_id}:
                raise TeamIdentityConflictError(
                    f"Provider identity ({source!r}, {external_team_id!r}) "
                    f"conflicts during registration: {sorted(current_ids)}."
                )
    return canonical, team_id
