"""Canonical competition/season identity resolver (Objective 6A, stdlib-only).

Deterministic, fail-closed boundary between provider competition/season
references and canonical identity:

    provider (source + external ids) + authoritative mappings
        -> canonical competition (competitions.code)
        -> canonical season (seasons.label)
        -> canonical competition-season relationship (explicit membership)

Separate canonical entities; "Premier League 2025/26" is never an identity.

Rules (mirroring team_identity / fixture_provenance conventions):

- Exact matching only. No fuzzy name matching, no inference from fixtures,
  dates, or arbitrary provider text (this resolver takes no date/fixture
  input at all).
- Unknown / ambiguous / conflicting identity raises; nothing is guessed.
- Read-only: never creates canonical competitions, seasons, mappings, or
  relationships. Resolution inputs are plain caller-supplied data
  (registry rows, mapping rows, membership pairs); the 6B mapping tables
  are read via fetch_provider_*_mappings and the 6C competition_season
  table via fetch_competition_seasons.
- External provider IDs are TEXT verbatim: non-string values fail closed
  instead of being cast.
"""

from __future__ import annotations

from dataclasses import dataclass


class CompetitionIdentityError(ValueError):
    """Base failure for competition/season identity resolution."""


class UnknownCompetitionIdentityError(CompetitionIdentityError):
    """No authoritative mapping establishes the requested identity."""


class CompetitionIdentityConflictError(CompetitionIdentityError):
    """Authoritative mappings disagree (ambiguous or conflicting identity)."""


@dataclass(frozen=True)
class CompetitionSeasonResolution:
    """Structured successful resolution of one competition-season pair."""

    competition_id: int
    competition_code: str
    season_id: int
    season_label: str


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


def _resolve_canonical(rows, *, key: str, value: str, entity: str) -> dict:
    """Exact-match one canonical registry row; fail closed otherwise."""
    matches = [row for row in rows if row.get(key) == value]
    if not matches:
        raise UnknownCompetitionIdentityError(
            f"Unknown canonical {entity} {value!r}: no registry entry."
        )
    ids = {row.get("id") for row in matches}
    if len(ids) > 1:
        raise CompetitionIdentityConflictError(
            f"Canonical {entity} {value!r} maps to multiple IDs: {sorted(ids)}."
        )
    return dict(matches[0])


def _resolve_via_mapping(
    mappings,
    *,
    source: str | None,
    external_id: str | None,
    entity: str,
    id_field: str,
) -> int | None:
    """Resolve one canonical ID through provider mappings.

    Returns None when no provider reference is supplied. Raises Unknown
    when the reference is partial or unmapped, Conflict when ambiguous.
    """
    if source is None and external_id is None:
        return None
    if source is None or external_id is None:
        raise UnknownCompetitionIdentityError(
            f"Partial provider {entity} reference: source and external ID "
            "are both required; refusing to guess."
        )
    rows = [
        row
        for row in mappings
        if row.get("source") == source
        and row.get(id_field) == external_id
    ]
    if not rows:
        raise UnknownCompetitionIdentityError(
            f"Unknown provider {entity} ({source!r}, {external_id!r}): "
            "no mapping."
        )
    ids = {row.get("competition_id" if entity == "competition" else "season_id")
           for row in rows}
    if len(ids) > 1:
        raise CompetitionIdentityConflictError(
            f"Ambiguous provider {entity} ({source!r}, {external_id!r}): "
            f"maps to multiple canonical IDs {sorted(ids)}."
        )
    (resolved_id,) = ids
    return resolved_id


def _check_mapped_target_exists(resolved_id, rows, *, entity: str) -> dict:
    targets = [row for row in rows if row.get("id") == resolved_id]
    if not targets:
        raise CompetitionIdentityConflictError(
            f"Provider {entity} mapping points to unknown canonical ID "
            f"{resolved_id!r}."
        )
    ids = {row.get("id") for row in targets}
    if len(ids) > 1:  # pragma: no cover - registry IDs are unique by schema
        raise CompetitionIdentityConflictError(
            f"Canonical {entity} ID {resolved_id!r} is ambiguous."
        )
    return dict(targets[0])


def resolve_competition(
    *,
    code: str | None = None,
    source: str | None = None,
    external_competition_id: str | None = None,
    competitions=(),
    competition_mappings=(),
) -> tuple[int, str]:
    """Resolve canonical competition -> (competition_id, competition_code).

    Accepts a canonical code, a provider reference (source + external ID),
    or both (which must then agree). Canonical spelling is always taken
    from the registry row, never echoed from provider text.
    """
    code = _require_text_or_absent(code, field="competition code")
    source = _require_text_or_absent(source, field="source")
    external_competition_id = _require_text_or_absent(
        external_competition_id, field="external competition ID"
    )

    canonical_row = None
    if code is not None:
        canonical_row = _resolve_canonical(
            competitions, key="code", value=code, entity="competition"
        )

    mapped_id = _resolve_via_mapping(
        competition_mappings,
        source=source,
        external_id=external_competition_id,
        entity="competition",
        id_field="external_competition_id",
    )
    mapped_row = None
    if mapped_id is not None:
        mapped_row = _check_mapped_target_exists(
            mapped_id, competitions, entity="competition"
        )

    if canonical_row is not None and mapped_row is not None:
        if canonical_row.get("id") != mapped_row.get("id"):
            raise CompetitionIdentityConflictError(
                f"Provider competition ({source!r}, {external_competition_id!r}) "
                f"maps to {mapped_row.get('id')!r} but canonical code "
                f"{code!r} resolves to {canonical_row.get('id')!r}."
            )
        return canonical_row["id"], canonical_row["code"]
    if mapped_row is not None:
        return mapped_row["id"], mapped_row["code"]
    if canonical_row is not None:
        return canonical_row["id"], canonical_row["code"]
    raise UnknownCompetitionIdentityError(
        "No competition reference supplied: provide a canonical code "
        "and/or a provider (source, external ID) reference."
    )


def resolve_season(
    *,
    label: str | None = None,
    source: str | None = None,
    external_season_id: str | None = None,
    seasons=(),
    season_mappings=(),
) -> tuple[int, str]:
    """Resolve canonical season -> (season_id, season_label).

    Same contract as resolve_competition: canonical label, provider
    reference, or both (which must agree). Never infers from dates.
    """
    label = _require_text_or_absent(label, field="season label")
    source = _require_text_or_absent(source, field="source")
    external_season_id = _require_text_or_absent(
        external_season_id, field="external season ID"
    )

    canonical_row = None
    if label is not None:
        canonical_row = _resolve_canonical(
            seasons, key="label", value=label, entity="season"
        )

    mapped_id = _resolve_via_mapping(
        season_mappings,
        source=source,
        external_id=external_season_id,
        entity="season",
        id_field="external_season_id",
    )
    mapped_row = None
    if mapped_id is not None:
        mapped_row = _check_mapped_target_exists(
            mapped_id, seasons, entity="season"
        )

    if canonical_row is not None and mapped_row is not None:
        if canonical_row.get("id") != mapped_row.get("id"):
            raise CompetitionIdentityConflictError(
                f"Provider season ({source!r}, {external_season_id!r}) "
                f"maps to {mapped_row.get('id')!r} but canonical label "
                f"{label!r} resolves to {canonical_row.get('id')!r}."
            )
        return canonical_row["id"], canonical_row["label"]
    if mapped_row is not None:
        return mapped_row["id"], mapped_row["label"]
    if canonical_row is not None:
        return canonical_row["id"], canonical_row["label"]
    raise UnknownCompetitionIdentityError(
        "No season reference supplied: provide a canonical label "
        "and/or a provider (source, external ID) reference."
    )


def _membership_pairs(membership) -> set:
    """Normalize membership to {(competition_id, season_id)}.

    Accepts 2-tuples or dict rows with competition_id/season_id keys so
    future 6C table rows can be supplied directly.
    """
    pairs = set()
    for entry in membership or ():
        if isinstance(entry, dict):
            pairs.add((entry.get("competition_id"), entry.get("season_id")))
        else:
            competition_id, season_id = entry
            pairs.add((competition_id, season_id))
    return pairs


def resolve_competition_season(
    *,
    competition_code: str | None = None,
    season_label: str | None = None,
    source: str | None = None,
    external_competition_id: str | None = None,
    external_season_id: str | None = None,
    competitions=(),
    seasons=(),
    competition_mappings=(),
    season_mappings=(),
    membership=None,
) -> CompetitionSeasonResolution:
    """Resolve provider/canonical references to a competition-season pair.

    Both sides must resolve; the pair must then be present in the explicit
    membership set. membership=None (no authoritative relationship info)
    or an absent pair raises UnknownCompetitionIdentityError: the
    relationship is never inferred.
    """
    competition_id, code = resolve_competition(
        code=competition_code,
        source=source,
        external_competition_id=external_competition_id,
        competitions=competitions,
        competition_mappings=competition_mappings,
    )
    season_id, label = resolve_season(
        label=season_label,
        source=source,
        external_season_id=external_season_id,
        seasons=seasons,
        season_mappings=season_mappings,
    )
    if membership is None:
        raise UnknownCompetitionIdentityError(
            f"No authoritative membership for competition {competition_id!r} "
            f"+ season {season_id!r}: relationship unresolved."
        )
    if (competition_id, season_id) not in _membership_pairs(membership):
        raise UnknownCompetitionIdentityError(
            f"Invalid competition-season relationship: competition "
            f"{competition_id!r} + season {season_id!r} have no membership."
        )
    return CompetitionSeasonResolution(
        competition_id=competition_id,
        competition_code=code,
        season_id=season_id,
        season_label=label,
    )


# --- Objective 6B: database retrieval layer (read-only) ---
#
# The pure resolver above is unchanged. These helpers fetch authoritative
# mapping rows from the 003 tables (provider_competition_mapping /
# provider_season_mapping) and return them in exactly the shape the
# resolver consumes: {source, external_competition_id, competition_id} /
# {source, external_season_id, season_id}. No resolution, no inference,
# no writes. Source filtering is exact-match only.


def _rows_of(result) -> list:
    data = result.data if hasattr(result, "data") else result
    return list(data or [])


def fetch_provider_competition_mappings(supabase, *, source: str | None = None) -> list:
    """Fetch provider competition mappings for the resolver (read-only)."""
    if source is not None:
        source = _require_text_or_absent(source, field="source")
    query = supabase.table("provider_competition_mapping").select(
        "source, external_competition_id, competition_id"
    )
    if source is not None:
        query = query.eq("source", source)
    return [dict(row) for row in _rows_of(query.execute())]


def fetch_provider_season_mappings(supabase, *, source: str | None = None) -> list:
    """Fetch provider season mappings for the resolver (read-only)."""
    if source is not None:
        source = _require_text_or_absent(source, field="source")
    query = supabase.table("provider_season_mapping").select(
        "source, external_season_id, season_id"
    )
    if source is not None:
        query = query.eq("source", source)
    return [dict(row) for row in _rows_of(query.execute())]


def fetch_competition_seasons(supabase) -> list:
    """Fetch canonical competition-season membership rows (read-only).

    Objective 6C retrieval for the competition_season table. Returns rows
    shaped for the resolver's membership parameter:
    {competition_id, season_id}. No filtering, no inference, no writes.
    """
    return [
        dict(row)
        for row in _rows_of(
            supabase.table("competition_season")
            .select("competition_id, season_id")
            .execute()
        )
    ]


__all__ = [
    "CompetitionIdentityError",
    "UnknownCompetitionIdentityError",
    "CompetitionIdentityConflictError",
    "CompetitionSeasonResolution",
    "resolve_competition",
    "resolve_season",
    "resolve_competition_season",
    "fetch_provider_competition_mappings",
    "fetch_provider_season_mappings",
    "fetch_competition_seasons",
]
