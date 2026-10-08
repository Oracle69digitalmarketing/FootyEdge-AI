"""One-shot VERIFY-ONLY API-Football team discovery (Objective 10.2C.2).

VERIFY-ONLY — NO DATABASE WRITES.

Structural guarantees (enforced by tests/test_verify_only.py):
  - Stdlib only (json, os, sys, urllib). No supabase import, no
    service-role client, no table access, no INSERT/UPDATE/UPSERT/DELETE
    anywhere in this file — database writes are not merely avoided,
    they are unrepresentable here.
  - API_FOOTBALL_KEY presence is checked as a boolean; the value travels
    solely in the x-apisports-key header to v3.football.api-sports.io
    and is never printed, logged, returned, or stored.
  - Call budget: 1 /status + 6 /teams?search= + at most 6
    /players/squads = at most 13 provider calls (Free-plan safe).
  - Selection rule (fail-closed): from each live search response, the
    intended team is the SINGLE row whose team.name equals the intended
    provider name exactly (case-insensitive, whitespace-collapsed).
    Zero or several exact matches -> STOP for that team: no squad
    request is made, nothing is inferred from country, venue, or
    closeness.
  - Squad rule: the squad response must echo team.id == requested
    provider ID AND team.name == selected provider name; otherwise STOP
    for that team.
  - Exit code 0 only when all six teams verify; nonzero otherwise.
  - Not wired into any scheduler, cron, endpoint, or pipeline: run once
    by an operator inside the legitimate production runtime and read the
    report from the logs. Mapping inserts and any player backfill happen
    only after explicit human review of this report, through separate,
    explicitly authorized steps — never automatically.
"""

from __future__ import annotations

import json
import os
import sys
import urllib.parse
import urllib.request

BANNER = "VERIFY-ONLY — NO DATABASE WRITES"

BASE_URL = "https://v3.football.api-sports.io"
KEY_VAR = "API_FOOTBALL_KEY"

# (canonical FootyEdge name, canonical teams.id, intended provider name
# used as the live search term). Provider IDs are NEVER listed here:
# they come only from live API responses (requirement 5).
TARGETS = (
    ("Arsenal", 221659396777490, "Arsenal"),
    ("Barcelona", 6794002167939, "Barcelona"),
    ("Bayern Munich", 18768778449461, "Bayern Munich"),
    ("Liverpool", 116955586910447, "Liverpool"),
    ("Man City", 149534346580314, "Manchester City"),
    ("Real Madrid", 83469380690940, "Real Madrid"),
)


def _normalize(name: object) -> str | None:
    if not isinstance(name, str):
        return None
    cleaned = " ".join(name.split())
    return cleaned.lower() if cleaned else None


def _provider_get(key: str, path: str, params: dict,
                  transport=None, timeout: float = 20.0):
    """Authorized GET against the API-Football host only.

    Returns (body, status). The key travels only in the request header;
    this function never prints or returns it.
    """
    if transport is not None:
        return transport(path, params, timeout)
    url = f"{BASE_URL}{path}?{urllib.parse.urlencode(params)}"
    req = urllib.request.Request(
        url, headers={"x-apisports-key": key, "Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.load(resp), resp.status


def _default_transport_factory(key: str):
    def _transport(path: str, params: dict, timeout: float):
        return _provider_get(key, path, params, timeout=timeout)
    return _transport


def verify_teams(transport=None) -> dict:
    """Run the full verify-only pass; return the report (no writes)."""
    report: dict = {
        "banner": BANNER,
        "key_present": bool(os.environ.get(KEY_VAR)),
        "teams": [],
        "provider_calls_made": 0,
        "verified": 0,
    }
    if not report["key_present"]:
        report["status"] = "stopped"
        report["reason"] = (
            f"{KEY_VAR} is not configured in this runtime; "
            "no provider request attempted.")
        return report

    def call(path: str, params: dict):
        body, status = _provider_get(
            os.environ[KEY_VAR], path, params, transport=transport)
        report["provider_calls_made"] += 1
        return body, status

    try:
        status_body, status_code = call("/status", {})
    except Exception as exc:
        report["status"] = "stopped"
        report["reason"] = f"connectivity failure: {type(exc).__name__}"
        return report
    if not isinstance(status_code, int) or status_code < 200 or status_code >= 300:
        report["status"] = "stopped"
        report["reason"] = f"/status returned HTTP {status_code}"
        return report
    if not isinstance(status_body, dict):
        report["status"] = "stopped"
        report["reason"] = "/status response malformed"
        return report
    errors = status_body.get("errors")
    if errors:
        report["status"] = "stopped"
        report["reason"] = f"/status reported errors: {errors}"
        return report

    for canonical_name, canonical_id, provider_name in TARGETS:
        entry: dict = {
            "canonical_name": canonical_name,
            "canonical_team_id": canonical_id,
            "search_term": provider_name,
            "status": "pending",
        }
        wanted = _normalize(provider_name)
        try:
            search_body, search_status = call(
                "/teams", {"search": provider_name})
        except Exception as exc:
            entry.update({"status": "stopped",
                          "reason": f"search failed: {type(exc).__name__}"})
            report["teams"].append(entry)
            continue
        if search_status == 429:
            entry.update({"status": "stopped", "reason": "rate_limited"})
            report["teams"].append(entry)
            continue
        if (not isinstance(search_status, int) or search_status < 200
                or search_status >= 300
                or not isinstance(search_body, dict)
                or not isinstance(search_body.get("response"), list)):
            entry.update({"status": "stopped",
                          "reason": f"search unverifiable (HTTP {search_status})"})
            report["teams"].append(entry)
            continue
        exact = []
        for row in search_body["response"]:
            if not isinstance(row, dict):
                continue
            team = row.get("team")
            if not isinstance(team, dict):
                continue
            if (_normalize(team.get("name")) == wanted
                    and team.get("id") is not None):
                exact.append(team)
        if len(exact) != 1:
            entry.update({
                "status": "stopped",
                "reason": (
                    f"search ambiguous or missing: {len(exact)} exact "
                    f"name matches for {provider_name!r}; refusing to infer."),
            })
            report["teams"].append(entry)
            continue
        (selected,) = exact
        external_id = str(selected["id"])
        try:
            squad_body, squad_status = call(
                "/players/squads", {"team": external_id})
        except Exception as exc:
            entry.update({"status": "stopped",
                          "reason": f"squad request failed: {type(exc).__name__}"})
            report["teams"].append(entry)
            continue
        if (squad_status == 429 or not isinstance(squad_status, int)
                or squad_status < 200 or squad_status >= 300
                or not isinstance(squad_body, dict)
                or not isinstance(squad_body.get("response"), list)
                or not squad_body["response"]):
            entry.update({"status": "stopped",
                          "reason": f"squad unverifiable (HTTP {squad_status})"})
            report["teams"].append(entry)
            continue
        first = squad_body["response"][0]
        echoed = first.get("team") if isinstance(first, dict) else None
        if not isinstance(echoed, dict):
            entry.update({"status": "stopped",
                          "reason": "squad echo missing team block"})
            report["teams"].append(entry)
            continue
        if (str(echoed.get("id")) != external_id
                or _normalize(echoed.get("name")) != wanted):
            entry.update({
                "status": "stopped",
                "reason": (
                    "squad echo mismatch: requested "
                    f"{external_id!r}/{provider_name!r}, echoed "
                    f"{echoed.get('id')!r}/{echoed.get('name')!r}."),
            })
            report["teams"].append(entry)
            continue
        players = first.get("players")
        entry.update({
            "status": "verified",
            "provider_team_id": external_id,
            "provider_team_name": selected["name"],
            "squad_count": len(players) if isinstance(players, list) else None,
        })
        report["verified"] += 1
        report["teams"].append(entry)

    report["status"] = "complete" if report["verified"] == len(TARGETS) else "partial"
    return report


def main() -> int:
    print(BANNER, flush=True)
    report = verify_teams()
    print(json.dumps(report, indent=1))
    return 0 if report.get("status") == "complete" else 1


if __name__ == "__main__":
    sys.exit(main())
