import os
import httpx
import asyncio
import logging
from datetime import datetime
from typing import Dict, List, Any, Optional

logger = logging.getLogger(__name__)

class FootballAPIClient:
    """
    Solely uses Sportradar (Soccer Data) for match and team information.
    """
    def __init__(self, api_key: str = None):
        self.api_key = api_key or os.environ.get('SPORTRADAR_API_KEY')
        # Sportradar trial API endpoint
        self.base_url = "https://api.sportradar.com/soccer/trial/v4/en"
        self.circuit_breaker = {"status": "healthy", "last_failure": None}

        if not self.api_key:
            logger.warning("SPORTRADAR_API_KEY not found. API calls will fail.")

    def _is_healthy(self) -> bool:
        if self.circuit_breaker["status"] == "healthy": return True
        last_failure = self.circuit_breaker["last_failure"]
        if last_failure and (datetime.now() - last_failure).total_seconds() > 60:
            self.circuit_breaker["status"] = "healthy"; return True
        return False

    def _mark_failure(self):
        self.circuit_breaker = {"status": "unhealthy", "last_failure": datetime.now()}

    def normalize_match(self, s: Dict) -> Dict:
        ev = s.get('sport_event', {})
        st = s.get('sport_event_status', {})
        home = next((c for c in ev.get('competitors', []) if c.get('qualifier') == 'home'), {})
        away = next((c for c in ev.get('competitors', []) if c.get('qualifier') == 'away'), {})

        return {
            "fixture": {
                "id": ev.get('id'),
                "date": ev.get('start_time')
            },
            "teams": {
                "home": {
                    "name": home.get('name'),
                    "id": home.get('id'),
                    "logo": None # Sportradar trial doesn't usually provide logos directly
                },
                "away": {
                    "name": away.get('name'),
                    "id": away.get('id'),
                    "logo": None
                }
            },
            "league": {
                "name": ev.get('sport_event_context', {}).get('league', {}).get('name'),
                "id": ev.get('sport_event_context', {}).get('league', {}).get('id')
            },
            "goals": {
                "home": st.get('home_score'),
                "away": st.get('away_score')
            },
            "status": {"long": st.get('status')}
        }

    async def get_matches_by_date(self, date_from: str, date_to: str = None) -> Dict:
        if not self._is_healthy(): return {"response": []}

        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                # Sportradar daily schedule endpoint: /schedules/{date}/schedule.json
                res = await client.get(
                    f"{self.base_url}/schedules/{date_from}/schedule.json",
                    params={"api_key": self.api_key}
                )
                if res.status_code == 200:
                    data = res.json()
                    matches = [self.normalize_match(s) for s in data.get('schedules', [])]
                    return {"response": matches}
                else:
                    logger.error(f"Sportradar error: {res.status_code} - {res.text}")
                    self._mark_failure()
                    return {"response": []}
        except Exception as e:
            logger.error(f"Sportradar exception: {e}")
            self._mark_failure()
            return {"response": []}

    async def get_team_fixtures(self, team_id: str, last: int = 40) -> Dict:
        # Sportradar team profile or results endpoint
        # /competitors/{competitor_id}/results.json
        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                res = await client.get(
                    f"{self.base_url}/competitors/{team_id}/results.json",
                    params={"api_key": self.api_key}
                )
                if res.status_code == 200:
                    data = res.json()
                    # We can use normalize_match on results as well
                    matches = [self.normalize_match(s) for s in data.get('results', [])[:last]]
                    return {"response": matches}
                return {"response": []}
        except Exception:
            return {"response": []}

    async def get_standings(self, league_id: str) -> Dict:
        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                # /seasons/{season_id}/standings.json - Requires season_id in Sportradar
                # For simplicity, we might need a mapping or just return empty if unknown
                return {"response": []}
        except Exception:
            return {"response": []}

    async def search_teams(self, query: str) -> Dict:
        # Sportradar doesn't have a direct "search" endpoint in trial v4 soccer usually.
        # It's more about knowing the IDs.
        return {"response": []}

    async def list_leagues(self) -> Dict:
        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                res = await client.get(
                    f"{self.base_url}/competitions.json",
                    params={"api_key": self.api_key}
                )
                if res.status_code == 200:
                    data = res.json()
                    leagues = []
                    for c in data.get('competitions', []):
                        leagues.append({"league": {"id": c.get('id'), "name": c.get('name')}})
                    return {"response": leagues}
                return {"response": []}
        except Exception:
            return {"response": []}

    async def get_odds_by_event_id(self, event_id: str) -> Dict:
        # Sportradar trial doesn't include odds usually.
        return {}

    async def get_stats_by_event_id(self, event_id: str) -> Dict:
        # /sport_events/{sport_event_id}/timeline.json
        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                res = await client.get(
                    f"{self.base_url}/sport_events/{event_id}/timeline.json",
                    params={"api_key": self.api_key}
                )
                if res.status_code == 200:
                    return res.json()
                return {"response": []}
        except Exception:
            return {"response": []}
