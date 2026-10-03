"""Canonical player identity policy (stdlib-only).

players.id (the existing BIGSERIAL sequence) is the ONLY canonical player-ID
namespace: permanent, never reassigned, never reused, and independent of
team, provider, name spelling, competition/season, and statistics.

Resolution (resolve_player) is read-only and fail-closed:

    provider mapping (source + external TEXT ID) -> canonical player
    alias (alias + source)                       -> canonical player
    canonical registry row (id or exact name)    -> canonical player

Multiple supplied signals must agree on one player; disagreement raises
PlayerIdentityConflictError; no usable signal raises
UnknownPlayerIdentityError. No fuzzy matching, no inference from teams or
dates, no implicit creation during normal resolution.

Registration (register_player) is the ONLY creation boundary: explicit
inputs, sequence-generated IDs (never caller-assigned, never updated),
insert-then-verify races, evidence-only mapping/alias writes. Never infers
identity from team or provider names; never fabricates provider IDs.

players.external_id is legacy, unattributed, and wrongly typed: this module
never reads it, never writes it, and never references it.
"""

from __future__ import annotations

import logging
import re

logger = logging.getLogger(__name__)

_WS_RE = re.compile(r"\s+")


class PlayerIdentityError(ValueError):
    """Base failure for player identity resolution/registration."""


class UnknownPlayerIdentityError(PlayerIdentityError):
    """No authoritative record establishes the requested player identity."""


class PlayerIdentityConflictError(PlayerIdentityError):
    """Authoritative records disagree (ambiguous or conflicting identity)."""


def canonicalize_player_name(raw: str) -> str:
    """Mechanically normalize a player display name.

    Same whitespace convention as team canonicalization: strip
    leading/trailing whitespace, collapse internal runs. Case and wording
    are preserved. Raises ValueError on empty/non-string input (explicit
    unknown handling, never a guessed identity).
    """
    if not isinstance(raw, str):
        raise ValueError("player name must be a string")
    cleaned = _WS_RE.sub(" ", raw.strip())
    if not cleaned:
        raise ValueError("player name must not be empty")
    return cleaned


def _require_text_or_absent(value, *, field: str) -> str | None:
    """Normalize TEXT identity input: None/"" is absent; non-str fails closed."""
    if value is None or value == "":
        return None
    if not isinstance(value, str):
        raise TypeError(
            f"{field} must be TEXT (stored verbatim); "
            f"refusing non-string {type(value).__name__}."
        )
    return value


def _require_mapped_target(players, player_id: int, *, kind: str) -> dict:
    """Return the registry row for a mapped ID; a dangling target conflicts.

    A mapping/alias pointing at a nonexistent canonical row is corrupt
    evidence, never an unknown identity (mirrors the 6A/6B dangling-target
    rule): it raises Conflict rather than resolving or guessing.
    """
    try:
        return _canonical_player_row(players, player_id)
    except UnknownPlayerIdentityError:
        raise PlayerIdentityConflictError(
            f"Provider {kind} mapping points to unknown canonical "
            f"player ID {player_id!r}."
        )


def _require_player_id(value) -> int | None:
    """Normalize a canonical player ID: None is absent; non-int fails closed."""
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, int):
        raise TypeError(
            "player_id must be an integer canonical players.id; "
            f"refusing {type(value).__name__}."
        )
    return value


def _rows_of(result) -> list:
    data = result.data if hasattr(result, "data") else result
    return list(data or [])


def _canonical_player_row(players, player_id: int) -> dict:
    """Return the single registry row for a canonical ID, fail closed."""
    matches = [row for row in players if row.get("id") == player_id]
    if not matches:
        raise UnknownPlayerIdentityError(
            f"Unknown canonical player ID {player_id!r}: no players row."
        )
    names = {row.get("name") for row in matches}
    if len(names) > 1:
        raise PlayerIdentityConflictError(
            f"Canonical player ID {player_id!r} has divergent registry rows."
        )
    return dict(matches[0])


def _resolve_via_mapping(player_mappings, *, source, external_player_id,
                         players) -> int | None:
    """Resolve one canonical ID through provider mappings.

    The mapping path engages ONLY when the provider mapping identifier
    is actually supplied (source together with external player ID): a
    source by itself is a scope qualifier for other namespaces (notably
    aliases), not a provider mapping query, so it skips this path and
    resolution continues. An external ID without its source remains a
    partial reference and raises Unknown. Mirrors the 6A/6B
    provider-mapping semantics.
    """
    if external_player_id is None:
        return None
    if source is None:
        raise UnknownPlayerIdentityError(
            "Partial provider player reference: source and external player ID "
            "are both required; refusing to guess."
        )
    rows = [
        row
        for row in player_mappings
        if row.get("source") == source
        and row.get("external_player_id") == external_player_id
    ]
    if not rows:
        raise UnknownPlayerIdentityError(
            f"Unknown provider player ({source!r}, {external_player_id!r}): "
            "no mapping."
        )
    ids = {row.get("player_id") for row in rows}
    if len(ids) > 1:
        raise PlayerIdentityConflictError(
            f"Ambiguous provider player ({source!r}, {external_player_id!r}): "
            f"maps to multiple canonical IDs {sorted(ids)}."
        )
    (resolved_id,) = ids
    _require_mapped_target(players, resolved_id, kind="player")
    return resolved_id


def _resolve_via_alias(aliases, *, alias, source, players) -> int | None:
    """Resolve one canonical ID through alias pointers.

    Source scoping applies when a source is supplied; without one, the alias
    is matched across sources and any multi-target result conflicts. Alias
    validity windows are recorded evidence only and are never consulted:
    the resolver must not infer identity from dates.
    """
    if alias is None:
        return None
    rows = [row for row in aliases if row.get("alias") == alias]
    if source is not None:
        rows = [row for row in rows if row.get("source") == source]
    if not rows:
        raise UnknownPlayerIdentityError(
            f"Unknown player alias {alias!r}"
            + (f" for source {source!r}" if source is not None else "")
            + ": no alias record."
        )
    ids = {row.get("player_id") for row in rows}
    if len(ids) > 1:
        raise PlayerIdentityConflictError(
            f"Ambiguous player alias {alias!r}: "
            f"points to multiple canonical IDs {sorted(ids)}."
        )
    (resolved_id,) = ids
    _require_mapped_target(players, resolved_id, kind="alias")
    return resolved_id


def _resolve_via_name(players, name: str) -> int | None:
    """Resolve one canonical ID through the exact registry name.

    Namesake rule: several rows sharing one display name is a Conflict,
    never a first-row pick, never a merge.
    """
    if name is None:
        return None
    canonical = canonicalize_player_name(name)
    matches = [row for row in players if row.get("name") == canonical]
    if not matches:
        raise UnknownPlayerIdentityError(
            f"Unknown canonical player {canonical!r}: no players row."
        )
    ids = {row.get("id") for row in matches}
    if len(ids) > 1:
        raise PlayerIdentityConflictError(
            f"Ambiguous canonical player name {canonical!r}: "
            f"multiple players share it {sorted(ids)}; refusing to choose."
        )
    (resolved_id,) = ids
    return resolved_id


def _resolve_via_id(players, player_id) -> int | None:
    """Resolve a directly supplied canonical ID against the registry."""
    if player_id is None:
        return None
    _canonical_player_row(players, player_id)
    return player_id


def resolve_player(
    *,
    player_id=None,
    source=None,
    external_player_id=None,
    alias=None,
    alias_source=None,
    name=None,
    players=(),
    player_mappings=(),
    aliases=(),
) -> tuple[int, str]:
    """Resolve caller-supplied references to (player_id, canonical_name).

    Accepts a canonical ID, a provider reference (source + external TEXT
    ID), an alias (+ optional source scope), a canonical display name, or
    several at once — which must then agree on one player. Canonical
    spelling always comes from the registry row, never from provider or
    alias text. Read-only: never creates players, mappings, aliases, or
    membership rows. Unknown signals raise UnknownPlayerIdentityError;
    disagreement raises PlayerIdentityConflictError.
    """
    resolved_id = _require_player_id(player_id)
    source = _require_text_or_absent(source, field="source")
    external_player_id = _require_text_or_absent(
        external_player_id, field="external player ID"
    )
    alias = _require_text_or_absent(alias, field="alias")
    alias_source = _require_text_or_absent(alias_source, field="source")
    if name is not None:
        # Canonicalized here so "" / non-string names fail closed as invalid.
        canonicalize_player_name(name)

    candidates = []
    via_id = _resolve_via_id(players, resolved_id)
    if via_id is not None:
        candidates.append(("canonical ID", via_id))
    via_mapping = _resolve_via_mapping(
        player_mappings, source=source,
        external_player_id=external_player_id, players=players,
    )
    if via_mapping is not None:
        candidates.append(("provider mapping", via_mapping))
    via_alias = _resolve_via_alias(
        aliases, alias=alias,
        source=(alias_source if alias_source is not None else source),
        players=players,
    )
    if via_alias is not None:
        candidates.append(("alias", via_alias))
    via_name = _resolve_via_name(players, name)
    if via_name is not None:
        candidates.append(("registry name", via_name))

    if not candidates:
        raise UnknownPlayerIdentityError(
            "No player reference supplied: provide a canonical ID, a "
            "provider (source, external ID) reference, an alias, and/or a "
            "canonical display name."
        )
    ids = {player_id_ for _, player_id_ in candidates}
    if len(ids) > 1:
        detail = ", ".join(f"{label} -> {pid}" for label, pid in candidates)
        raise PlayerIdentityConflictError(
            f"Supplied player identity signals disagree: {detail}."
        )
    (final_id,) = ids
    row = _canonical_player_row(players, final_id)
    return final_id, row["name"]


def _mapping_rows(supabase, *, source, external_player_id) -> list:
    return _rows_of(
        supabase.table("player_identity_sources")
        .select("player_id, source, external_player_id")
        .eq("source", source)
        .eq("external_player_id", external_player_id)
        .execute()
    )


def _alias_rows(supabase, *, alias, source) -> list:
    query = (
        supabase.table("player_aliases")
        .select("player_id, alias, source")
        .eq("alias", alias)
    )
    if source is not None:
        query = query.eq("source", source)
    return _rows_of(query.execute())


def _player_rows_by_name(supabase, canonical: str) -> list:
    return _rows_of(
        supabase.table("players").select("id, name").eq("name", canonical).execute()
    )


def _insert_player_row(supabase, canonical: str) -> dict:
    """Insert one registry row, letting the sequence generate the ID.

    Never assigns players.id explicitly; never updates IDs. On write
    conflict, re-reads by exact name: exactly one row is adopted
    (concurrent insert of the same identity), zero or several rows is a
    Conflict (never a blind pick, never a merge).
    """
    try:
        result = supabase.table("players").insert({"name": canonical}).execute()
        stored = _rows_of(result)
        if stored:
            return dict(stored[0])
    except Exception:
        pass
    existing = _player_rows_by_name(supabase, canonical)
    ids = {row.get("id") for row in existing}
    if len(ids) != 1:
        raise PlayerIdentityConflictError(
            f"Player registration for {canonical!r} is ambiguous: "
            f"{len(ids)} registry rows share the name; refusing to choose."
        )
    return dict(existing[0])


def _insert_mapping_row(supabase, *, player_id, source, external_player_id,
                        external_name) -> None:
    """Insert one provider mapping from explicit evidence (never inferred).

    Duplicate grain re-read: same target is idempotent success, another
    target is Conflict. The existing mapping is never overwritten.
    """
    try:
        supabase.table("player_identity_sources").insert(
            {
                "player_id": player_id,
                "source": source,
                "external_player_id": external_player_id,
                "external_name": external_name,
            }
        ).execute()
        return
    except Exception:
        pass
    current = {
        row.get("player_id")
        for row in _mapping_rows(
            supabase, source=source, external_player_id=external_player_id
        )
    }
    if current != {player_id}:
        raise PlayerIdentityConflictError(
            f"Provider player ({source!r}, {external_player_id!r}) conflicts "
            f"during registration: {sorted(current)}."
        )


def _insert_alias_row(supabase, *, player_id, alias, source) -> None:
    """Insert one alias pointer from explicit evidence (never inferred)."""
    try:
        supabase.table("player_aliases").insert(
            {"player_id": player_id, "alias": alias, "source": source}
        ).execute()
        return
    except Exception:
        pass
    current = {
        row.get("player_id")
        for row in _alias_rows(supabase, alias=alias, source=source)
    }
    if current != {player_id}:
        raise PlayerIdentityConflictError(
            f"Player alias ({alias!r}, {source!r}) conflicts during "
            f"registration: {sorted(current)}."
        )


def register_player(
    *,
    name: str,
    supabase,
    source=None,
    external_player_id=None,
    alias=None,
    alias_source=None,
    team_id=None,
    competition_id=None,
    season_id=None,
) -> tuple[int, str]:
    """Explicitly register one canonical player (the ONLY creation boundary).

    Required: canonical display name (whitespace-normalized; team, provider,
    and date context never contribute to identity). Optional, evidence-only:
    provider mapping (source + verbatim TEXT external ID, both required
    together), alias pointer (alias + source scope), and an initial team
    membership relationship (team/competition/season IDs recorded in
    player_team_history, never in identity). Provider IDs are never
    fabricated: partial provider evidence raises instead of mapping.
    Registration never infers identity from team or provider names.
    """
    raw_name = name
    canonical = canonicalize_player_name(name)
    source = _require_text_or_absent(source, field="source")
    external_player_id = _require_text_or_absent(
        external_player_id, field="external player ID"
    )
    alias = _require_text_or_absent(alias, field="alias")
    alias_source = _require_text_or_absent(alias_source, field="source")
    if (source is None) != (external_player_id is None):
        raise ValueError(
            "Provider evidence is incomplete: source and external player ID "
            "are both required; refusing to fabricate a mapping."
        )
    alias_scope = alias_source if alias_source is not None else source
    if alias is not None and alias_scope is None:
        raise ValueError(
            "Alias evidence is incomplete: an alias requires a source scope; "
            "refusing to create a sourceless alias."
        )
    if team_id is not None and (
        isinstance(team_id, bool) or not isinstance(team_id, int)
    ):
        raise TypeError("team_id must be an integer teams.id.")

    if external_player_id is not None:
        claimed = {
            row.get("player_id")
            for row in _mapping_rows(
                supabase, source=source, external_player_id=external_player_id
            )
        }
        if claimed:
            if len(claimed) > 1:
                raise PlayerIdentityConflictError(
                    f"Provider player ({source!r}, {external_player_id!r}) "
                    "is already ambiguously mapped."
                )
            (claimed_id,) = claimed
            row = _canonical_player_row(
                _rows_of(
                    supabase.table("players")
                    .select("id, name")
                    .execute()
                ),
                claimed_id,
            )
            if row.get("name") != canonical:
                raise PlayerIdentityConflictError(
                    f"Provider player ({source!r}, {external_player_id!r}) "
                    f"already maps to {row.get('name')!r}, not {canonical!r}."
                )
            return claimed_id, row["name"]

    if alias is not None:
        claimed = {
            row.get("player_id")
            for row in _alias_rows(
                supabase, alias=alias, source=alias_scope
            )
        }
        if claimed:
            if len(claimed) > 1:
                raise PlayerIdentityConflictError(
                    f"Player alias ({alias!r}, {alias_scope!r}) is already "
                    "ambiguously mapped."
                )
            (claimed_id,) = claimed
            row = _canonical_player_row(
                _rows_of(
                    supabase.table("players")
                    .select("id, name")
                    .execute()
                ),
                claimed_id,
            )
            if row.get("name") != canonical:
                raise PlayerIdentityConflictError(
                    f"Player alias ({alias!r}, {alias_scope!r}) already points "
                    f"to {row.get('name')!r}, not {canonical!r}."
                )
            return claimed_id, row["name"]

    stored = _insert_player_row(supabase, canonical)
    player_id, canonical = stored["id"], stored["name"]

    if external_player_id is not None:
        _insert_mapping_row(
            supabase, player_id=player_id, source=source,
            external_player_id=external_player_id, external_name=raw_name,
        )
    if alias is not None:
        _insert_alias_row(
            supabase, player_id=player_id, alias=alias, source=alias_scope
        )
    if team_id is not None:
        supabase.table("player_team_history").insert(
            {
                "player_id": player_id,
                "team_id": team_id,
                "competition_id": competition_id,
                "season_id": season_id,
            }
        ).execute()
    return player_id, canonical


# --- Retrieval layer (read-only; resolver-shaped rows) ---


def fetch_players(supabase) -> list:
    """Fetch canonical registry rows shaped for the resolver (read-only)."""
    return [
        dict(row)
        for row in _rows_of(supabase.table("players").select("id, name").execute())
    ]


def fetch_player_mappings(supabase, *, source: str | None = None) -> list:
    """Fetch provider mapping rows shaped for the resolver (read-only)."""
    source = _require_text_or_absent(source, field="source")
    query = supabase.table("player_identity_sources").select(
        "player_id, source, external_player_id"
    )
    if source is not None:
        query = query.eq("source", source)
    return [dict(row) for row in _rows_of(query.execute())]


def fetch_player_aliases(supabase, *, source: str | None = None) -> list:
    """Fetch alias pointer rows shaped for the resolver (read-only)."""
    source = _require_text_or_absent(source, field="source")
    query = supabase.table("player_aliases").select(
        "player_id, alias, source"
    )
    if source is not None:
        query = query.eq("source", source)
    return [dict(row) for row in _rows_of(query.execute())]


__all__ = [
    "PlayerIdentityError",
    "UnknownPlayerIdentityError",
    "PlayerIdentityConflictError",
    "canonicalize_player_name",
    "resolve_player",
    "register_player",
    "fetch_players",
    "fetch_player_mappings",
    "fetch_player_aliases",
]
