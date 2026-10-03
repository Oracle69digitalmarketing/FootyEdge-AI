"""Odds API fixture provenance boundary (stdlib-only, except team_identity).

Establishes the persistence path:

    Odds API event_id
        -> match_provider_identity.external_match_id  (TEXT, verbatim)
        -> matches.id                                 (internal FK)

Fixture identity and team identity are separate namespaces:

- This module NEVER writes teams.id, teams rows, team_aliases rows, or
  team_identity_sources rows. Team names are resolved read-only through
  resolve_canonical_id_db, and the provider event id is NEVER passed as
  external_team_id.
- The live predictor path (find_all_value_bets / predict_match) does not
  persist matches and is intentionally NOT touched: persistence happens
  only when BOTH the external event id AND the authoritative internal
  matches.id are known. Nothing is fabricated when either is missing.
- Match reconciliation uses the existing grain
  (home_team_id, away_team_id, match_date) only. No fuzzy matching, no
  raw-name identity keys.
"""

from __future__ import annotations

import logging

from team_identity import resolve_canonical_id_db

logger = logging.getLogger(__name__)

# Provider source label for The-Odds-API fixture events.
ODDS_API_SOURCE = "odds-api"


class FixtureProvenanceConflictError(ValueError):
    """Same (source, external_match_id) already maps to another match.

    The existing mapping is authoritative; the event is never silently
    remapped. Raised fail-closed for that mapping operation only.
    """


def extract_odds_event_id(normalized_match: dict) -> str | None:
    """Return the preserved Odds API event id from a normalized match.

    Read-only accessor over the normalization contract
    (football_api_client.OddsAPIProvider.normalize_match):
    ``{"fixture": {"id": <event_id>, "date": <commence_time>}, ...}``.
    The value is returned verbatim (no cast, no hash, no normalization);
    missing/empty stays missing (None).
    """
    fixture = (normalized_match or {}).get("fixture") or {}
    event_id = fixture.get("id")
    if event_id is None or event_id == "":
        return None
    return event_id


def _rows_of(result) -> list:
    data = result.data if hasattr(result, "data") else result
    return list(data or [])


def record_fixture_provenance(
    supabase,
    *,
    source: str,
    external_match_id: str,
    match_id: int,
) -> dict | None:
    """Persist one (source, external_match_id) -> match_id mapping.

    - Missing event id (None/"") or missing match_id (None): write no row,
      return None, do not fail.
    - Non-string event id: TypeError fail-closed (integer-cast storage is
      forbidden; external_match_id MUST remain TEXT verbatim).
    - Same (source, event) for the same match: idempotent, return existing.
    - Same (source, event) for another match: log + raise
      FixtureProvenanceConflictError; the stored row is NOT overwritten.
    - Never touches teams / team_aliases / team_identity_sources.
    """
    if external_match_id is None or external_match_id == "":
        return None
    if not isinstance(external_match_id, str):
        raise TypeError(
            "external_match_id must be stored verbatim as TEXT; "
            f"refusing non-string {type(external_match_id).__name__}."
        )
    if not isinstance(source, str) or not source:
        raise ValueError("source is required.")
    if match_id is None:
        logger.warning(
            "Fixture provenance skipped: no authoritative matches.id "
            "for (%r, %r); not fabricating one.",
            source,
            external_match_id,
        )
        return None

    existing = _rows_of(
        supabase.table("match_provider_identity")
        .select("id, match_id, source, external_match_id")
        .eq("source", source)
        .eq("external_match_id", external_match_id)
        .execute()
    )
    if existing:
        mapped_ids = {row["match_id"] for row in existing}
        if mapped_ids == {match_id}:
            return dict(existing[0])
        logger.error(
            "Fixture provenance conflict: (%r, %r) already maps to %s; "
            "refusing to remap to %s.",
            source,
            external_match_id,
            sorted(mapped_ids),
            match_id,
        )
        raise FixtureProvenanceConflictError(
            f"Provider event ({source!r}, {external_match_id!r}) already maps "
            f"to match(es) {sorted(mapped_ids)}; cannot map to {match_id}."
        )

    result = (
        supabase.table("match_provider_identity")
        .insert(
            {
                "match_id": match_id,
                "source": source,
                "external_match_id": external_match_id,
            }
        )
        .execute()
    )
    rows = _rows_of(result)
    return dict(rows[0]) if rows else {
        "match_id": match_id,
        "source": source,
        "external_match_id": external_match_id,
    }


def resolve_and_record_odds_event(
    supabase,
    *,
    external_match_id: str,
    home_name: str,
    away_name: str,
    match_date: str,
    source: str = ODDS_API_SOURCE,
    team_source: str = ODDS_API_SOURCE,
) -> dict | None:
    """Resolve an Odds event to its unique match and record provenance.

    Teams resolve read-only via resolve_canonical_id_db (the event id is
    never supplied as external_team_id); the match is looked up on the
    existing (home_team_id, away_team_id, match_date) grain. Records only
    when the match is uniquely identifiable:

    - missing event id -> None (no row, underlying fixture unaffected);
    - zero or multiple matching matches -> None + warning (no fabrication);
    - mapping conflict -> FixtureProvenanceConflictError (no remap).
    """
    if external_match_id is None or external_match_id == "":
        return None

    home_canonical, home_id = resolve_canonical_id_db(
        home_name, source=team_source, supabase=supabase
    )
    away_canonical, away_id = resolve_canonical_id_db(
        away_name, source=team_source, supabase=supabase
    )
    _ = (home_canonical, away_canonical)

    candidates = _rows_of(
        supabase.table("matches")
        .select("id, home_team_id, away_team_id, match_date")
        .eq("home_team_id", home_id)
        .eq("away_team_id", away_id)
        .eq("match_date", match_date)
        .execute()
    )
    if len(candidates) != 1:
        logger.warning(
            "Fixture provenance skipped: event (%r, %r) resolves to %d "
            "matches on the (home_team_id, away_team_id, match_date) grain; "
            "not fabricating a match.",
            source,
            external_match_id,
            len(candidates),
        )
        return None

    return record_fixture_provenance(
        supabase,
        source=source,
        external_match_id=external_match_id,
        match_id=candidates[0]["id"],
    )


__all__ = [
    "ODDS_API_SOURCE",
    "FixtureProvenanceConflictError",
    "extract_odds_event_id",
    "record_fixture_provenance",
    "resolve_and_record_odds_event",
]
