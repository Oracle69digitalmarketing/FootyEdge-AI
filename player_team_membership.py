"""History-authoritative team membership resolution (stdlib-only).

Ownership: players owns identity (id, name); player_team_history owns
membership. This module resolves a player's current team from history
for read paths (API) without touching players.team_id. Appends and
identity remain in player_identity / player_sync; this module never
writes.

Ordering rule: greatest history row id (sequence-generated
server-side). See current_history_row in player_identity for the
documented rule and its limitations.
"""

from __future__ import annotations


def _rows_of(result) -> list:
    data = result.data if hasattr(result, "data") else result
    return list(data or [])


async def attach_current_teams(supabase, players: list) -> list:
    """Return player rows with the "teams" property resolved from history.

    For each input row (with integer "id"), the current team is the
    greatest-id player_team_history row for that player, and "teams" is
    the full canonical teams row for that team. A player with no
    history, a history row pointing at a missing team, or malformed
    membership evidence resolves to "teams": None (the API/UI "Free
    Agent" fallback) — a team is never invented or inferred.

    Inputs are not mutated; new dicts are returned. Database errors
    propagate to the caller and must not be mistaken for missing
    membership.
    """
    rows = [dict(row) for row in (players or [])]
    if not rows:
        return []
    wanted = [row["id"] for row in rows
              if isinstance(row.get("id"), int)
              and not isinstance(row.get("id"), bool)]
    latest: dict = {}
    if wanted:
        history = _rows_of(
            supabase.table("player_team_history")
            .select("id, player_id, team_id")
            .in_("player_id", wanted)
            .execute()
        )
        for entry in history:
            if not isinstance(entry, dict):
                continue
            pid = entry.get("player_id")
            hid = entry.get("id")
            tid = entry.get("team_id")
            if not isinstance(pid, int) or isinstance(pid, bool):
                continue
            if not isinstance(hid, int) or isinstance(hid, bool):
                continue
            if not isinstance(tid, int) or isinstance(tid, bool):
                continue
            if pid not in latest or hid > latest[pid]["id"]:
                latest[pid] = entry
    teams_by_id: dict = {}
    team_ids = sorted({entry["team_id"] for entry in latest.values()})
    if team_ids:
        for team in _rows_of(
            supabase.table("teams").select("*").in_("id", team_ids).execute()
        ):
            if isinstance(team, dict) and isinstance(team.get("id"), int):
                teams_by_id[team["id"]] = team
    merged = []
    for row in rows:
        current = latest.get(row.get("id"))
        team = teams_by_id.get(current["team_id"]) if current else None
        row["teams"] = dict(team) if isinstance(team, dict) else None
        merged.append(row)
    return merged


__all__ = ["attach_current_teams"]
