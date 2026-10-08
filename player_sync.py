"""Nightly API-Football squad synchronization (Objective 10.2C.2, players only).

Scope boundaries (hard):
  - The-Odds-API remains the prediction/odds provider. Nothing here
    touches odds, fixtures for predictions, value bets, Telegram match
    data, billing, portfolio, acca, owner/auth, or any prediction logic.
  - Player rows are created ONLY through player_identity.register_player
    (the explicit identity boundary). This module performs no direct
    players insert/upsert/update and never fabricates provider IDs.
  - The credential (API_FOOTBALL_KEY) is owned solely by
    apifootball_client.ApiFootballClient, read from the server
    environment, sent only as the x-apisports-key header to the
    API-Football host. It is never logged, returned, stored, or
    committed by this module.
  - Every provider failure (missing_key, network, http, malformed,
    rate_limited) is fail-soft: skip-and-continue, never wipe. A team
    without a verified provider_team_mapping row is skipped, never
    inferred from names.

Scheduling reuses the existing ingestion infrastructure pattern:
  - api.py APScheduler nightly job calls run_player_sync().
  - Render cron and service env follow render.yaml (API_FOOTBALL_KEY
    declared sync:false, value never in source).
"""

from __future__ import annotations

import logging
import os

from apifootball_client import (
    ApiFootballClient,
    ApiFootballError,
    MAX_TEAMS_PER_CYCLE,
    SOURCE,
)

logger = logging.getLogger("player_sync")

TEAM_MAPPING_TABLE = "provider_team_mapping"


def _rows_of(result) -> list:
    data = result.data if hasattr(result, "data") else result
    return list(data or [])


def fetch_team_mappings(supabase, *, source: str = SOURCE) -> list:
    """Read verified (source, external_team_id -> team_id) rows.

    Raises ApiFootballError("malformed", ...) when the mapping table is
    absent (migration not yet applied) so callers fail-soft with an
    explicit reason instead of assuming an empty mapping.
    """
    if not isinstance(source, str) or not source:
        raise ValueError("source must be a non-empty string")
    try:
        rows = _rows_of(
            supabase.table(TEAM_MAPPING_TABLE)
            .select("source, external_team_id, team_id")
            .eq("source", source)
            .execute()
        )
    except Exception as exc:
        raise ApiFootballError(
            "malformed",
            f"{TEAM_MAPPING_TABLE} unavailable: {type(exc).__name__}",
        )
    return [dict(r) for r in rows]


def sync_players(
    supabase,
    client: ApiFootballClient | None = None,
    *,
    team_ids: list | None = None,
    dry_run: bool = False,
) -> dict:
    """Synchronize squads for mapped teams via register_player.

    Args:
        supabase: service-role server client (injected; never built here
            in tests so no credentials are needed offline).
        client: ApiFootballClient (injected in tests; otherwise built
            from the server environment).
        team_ids: optional explicit canonical team_id allowlist for a
            deliberate backfill (e.g. the six canonical teams). Unmapped
            teams in the allowlist are reported as skipped, never
            inferred.
        dry_run: when True, report verified mappings without any
            provider calls or player writes (the pre-write ID report).

    Returns a summary dict with counts only (no credential, no raw
    provider payloads): status, teams_mapped, teams_attempted,
    players_registered, skipped and failed per-team details, and the
    verified mapping list used.
    """
    from player_identity import PlayerIdentityError, register_player

    api = client if client is not None else ApiFootballClient()
    if not api.configured:
        return {
            "status": "skipped",
            "reason": "missing_key",
            "detail": (
                "API_FOOTBALL_KEY is not configured in this environment; "
                "skipping API-Football player sync with zero writes."
            ),
            "teams_mapped": 0,
            "teams_attempted": 0,
            "players_registered": 0,
            "teams": [],
            "mappings": [],
        }

    try:
        mappings = fetch_team_mappings(supabase)
    except ApiFootballError as exc:
        return {
            "status": "skipped",
            "reason": exc.kind,
            "detail": str(exc),
            "teams_mapped": 0,
            "teams_attempted": 0,
            "players_registered": 0,
            "teams": [],
            "mappings": [],
        }

    if team_ids is not None:
        wanted = {int(t) for t in team_ids}
        mappings = [m for m in mappings if m.get("team_id") in wanted]

    # Free-plan discipline: never exceed the per-cycle provider-call cap.
    cycle = mappings[: (api._max_teams if hasattr(api, "_max_teams") else MAX_TEAMS_PER_CYCLE)]

    report_mappings = [
        {
            "team_id": m.get("team_id"),
            "external_team_id": m.get("external_team_id"),
        }
        for m in cycle
    ]
    if dry_run:
        return {
            "status": "dry_run",
            "reason": "report_only",
            "detail": (
                "Verified provider team IDs reported; zero provider "
                "calls and zero player writes performed."
            ),
            "teams_mapped": len(report_mappings),
            "teams_attempted": 0,
            "players_registered": 0,
            "teams": [],
            "mappings": report_mappings,
        }

    teams: list = []
    registered = 0
    for mapping in cycle:
        external_id = mapping.get("external_team_id")
        team_id = mapping.get("team_id")
        entry: dict = {
            "team_id": team_id,
            "external_team_id": external_id,
            "status": "pending",
            "registered": 0,
            "skipped": 0,
        }
        if external_id is None or team_id is None:
            entry.update({"status": "skipped", "reason": "incomplete_mapping"})
            teams.append(entry)
            continue
        try:
            squad = api.get_squad(str(external_id))
        except ApiFootballError as exc:
            entry.update({"status": "skipped", "reason": exc.kind})
            teams.append(entry)
            continue
        except Exception as exc:  # fail-soft: never let one team stop the cycle
            entry.update({"status": "skipped", "reason": type(exc).__name__})
            teams.append(entry)
            continue
        for player in squad:
            try:
                register_player(
                    name=player["name"],
                    supabase=supabase,
                    source=SOURCE,
                    external_player_id=player["provider_player_id"],
                    team_id=int(team_id),
                )
                registered += 1
                entry["registered"] += 1
            except PlayerIdentityError:
                entry["skipped"] += 1
                continue
            except Exception:
                entry["skipped"] += 1
                continue
        entry["status"] = "ok"
        teams.append(entry)

    return {
        "status": "ok",
        "teams_mapped": len(report_mappings),
        "teams_attempted": len(teams),
        "players_registered": registered,
        "teams": teams,
        "mappings": report_mappings,
    }


def run_player_sync() -> dict:
    """Production entrypoint for the nightly scheduler / cron worker.

    Builds the service-role Supabase client and the server-credential
    API-Football client from the environment (values never logged),
    runs sync_players(), and logs counts only. Always fail-soft:
    any top-level failure is logged and returned as a skipped summary,
    never raised into the scheduler.
    """
    try:
        supabase_url = os.environ.get("SUPABASE_URL")
        supabase_key = os.environ.get("SUPABASE_SERVICE_KEY") or os.environ.get(
            "SUPABASE_KEY"
        )
        if not supabase_url or not supabase_key:
            logger.warning("player sync skipped: Supabase not configured.")
            return {
                "status": "skipped",
                "reason": "missing_supabase",
                "teams_mapped": 0,
                "teams_attempted": 0,
                "players_registered": 0,
                "teams": [],
                "mappings": [],
            }
        from supabase import create_client  # local import: keeps offline tests stdlib-only

        supabase = create_client(supabase_url, supabase_key)
        summary = sync_players(supabase)
        logger.info(
            "player sync: status=%s mapped=%d attempted=%d registered=%d",
            summary.get("status"),
            summary.get("teams_mapped"),
            summary.get("teams_attempted"),
            summary.get("players_registered"),
        )
        return summary
    except Exception as exc:  # scheduler must never break on player sync
        logger.warning("player sync skipped: %s", type(exc).__name__)
        return {
            "status": "skipped",
            "reason": type(exc).__name__,
            "teams_mapped": 0,
            "teams_attempted": 0,
            "players_registered": 0,
            "teams": [],
            "mappings": [],
        }


__all__ = ["SOURCE", "TEAM_MAPPING_TABLE", "fetch_team_mappings", "run_player_sync", "sync_players"]
