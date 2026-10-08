"""API-Football player-data adapter (Objective 10.2C.2, players only).

This module exists SOLELY for squad/player ingestion. The-Odds-API
remains the prediction/odds provider; nothing here touches odds,
fixtures for predictions, value bets, Telegram match data, or any
prediction logic.

Design notes:
  - Stdlib HTTP (urllib) with an injectable transport, so unit tests run
    without network, credentials, or third-party HTTP clients.
  - The credential (API_FOOTBALL_KEY) is read from the server environment
    only, never logged, never returned, never sent anywhere except the
    API-Football host as the required request header.
  - All failures are explicit ApiFootballError kinds; the ingestion job
    treats every one as skip-and-continue (fail-soft), never wipe.
"""

from __future__ import annotations

import json
import logging
import os
import urllib.parse
import urllib.request
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger("apifootball_client")

SOURCE = "apifootball"
BASE_URL = "https://v3.football.api-sports.io"
KEY_VAR = "API_FOOTBALL_KEY"

# Free-plan discipline: hard cap on provider calls per sync cycle so the
# job can never burn the daily quota in one run (squads = 1 call/team).
MAX_TEAMS_PER_CYCLE = 25


class ApiFootballError(Exception):
    """Explicit provider failure. `kind` selects sync handling."""

    def __init__(self, kind: str, detail: str = "") -> None:
        super().__init__(detail)
        self.kind = kind  # missing_key | network | http | malformed | rate_limited


def _default_transport(url: str, headers: Dict[str, str],
                       timeout: float) -> Any:
    req = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.load(resp), resp.status


class ApiFootballClient:
    """Minimal squads client. No odds, no fixtures, no predictions."""

    def __init__(self, api_key: Optional[str] = None,
                 transport: Optional[Callable[..., Any]] = None,
                 base_url: str = BASE_URL,
                 timeout: float = 20.0,
                 max_teams_per_cycle: int = MAX_TEAMS_PER_CYCLE) -> None:
        self._key = api_key if api_key is not None else os.environ.get(
            KEY_VAR, "")
        self._transport = transport or _default_transport
        self._base = base_url.rstrip("/")
        self._timeout = timeout
        self._max_teams = max_teams_per_cycle
        self.calls_made = 0

    @property
    def configured(self) -> bool:
        """Whether a credential is present (presence only, never the key)."""
        return bool(self._key)

    def _authorized_get(self, path: str, params: Dict[str, Any]) -> Any:
        """GET with the credential attached at this single boundary.

        The key travels only in the x-apisports-key header to the
        API-Football host. It is never logged, returned, or stored.
        """
        if not self._key:
            raise ApiFootballError(
                "missing_key",
                f"{KEY_VAR} is not configured; skipping API-Football call.")
        url = (f"{self._base}{path}?"
               f"{urllib.parse.urlencode(params)}")
        try:
            body, status = self._transport(
                url,
                {"x-apisports-key": self._key, "Accept": "application/json"},
                self._timeout)
        except ApiFootballError:
            raise
        except Exception as exc:
            raise ApiFootballError(
                "network", f"apifootball request failed: {type(exc).__name__}")
        return body, status

    def get_squad(self, external_team_id: str) -> List[Dict[str, Any]]:
        """Current squad for one provider team ID, normalized.

        Returns player dicts with exactly: provider_player_id (str),
        name, age, position, nationality (None: squads endpoint does not
        supply it), number, photo, team ids/names as echoed by provider.
        Malformed entries are dropped, never fabricated.
        """
        body, status = self._authorized_get(
            "/players/squads", {"team": str(external_team_id)})
        if status == 429:
            raise ApiFootballError("rate_limited",
                                   "apifootball rate limit reached")
        if not isinstance(status, int) or status < 200 or status >= 300:
            raise ApiFootballError("http", f"apifootball status {status}")
        if not isinstance(body, dict) or not isinstance(
                body.get("response"), list):
            raise ApiFootballError("malformed",
                                   "apifootball squads shape unexpected")
        squads = body["response"]
        if not squads:
            return []
        team_block = squads[0] if isinstance(squads[0], dict) else {}
        team = team_block.get("team") if isinstance(
            team_block.get("team"), dict) else {}
        raw_players = team_block.get("players")
        if not isinstance(raw_players, list):
            raise ApiFootballError("malformed",
                                   "apifootball players list unexpected")
        normalized: List[Dict[str, Any]] = []
        for raw in raw_players:
            if not isinstance(raw, dict):
                continue
            pid = raw.get("id")
            name = raw.get("name")
            if pid is None or not isinstance(name, str) or not name.strip():
                continue
            age = raw.get("age")
            number = raw.get("number")
            normalized.append({
                "provider_player_id": str(pid),
                "name": name.strip(),
                "age": age if isinstance(age, int) else None,
                "position": raw.get("position") if isinstance(
                    raw.get("position"), str) else None,
                "nationality": None,
                "number": number if isinstance(number, int) else None,
                "photo": raw.get("photo") if isinstance(
                    raw.get("photo"), str) else None,
                "provider_team_id": str(team.get("id")) if team.get(
                    "id") is not None else None,
                "provider_team_name": team.get("name") if isinstance(
                    team.get("name"), str) else None,
            })
        return normalized
