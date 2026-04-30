import os
import httpx
from datetime import datetime
import logging
from typing import Dict, List, Any, Optional

logger = logging.getLogger(__name__)

class FootballAPIClient:
    """
    Unified Football Data Client for free-api-live-football-data.p.rapidapi.com (Creativesdev)
    """
    def __init__(self):
        # Prefer the key provided in environment, fallback to User's key
        self.rapidapi_key = os.environ.get('RAPIDAPI_KEY', "9d484677a1mshd7d8d62a256ff73p138c8bjsn0e732e2acfd1")
        self.rapid_host = "free-api-live-football-data.p.rapidapi.com"
        self.headers = {
            'x-rapidapi-key': self.rapidapi_key,
            'x-rapidapi-host': self.rapid_host,
            'Content-Type': 'application/json'
        }

    async def _make_request(self, endpoint: str, params: Dict = None):
        url = f"https://{self.rapid_host}/{endpoint}"
        try:
            async with httpx.AsyncClient(timeout=25.0) as client:
                res = await client.get(url, headers=self.headers, params=params)
                if res.status_code == 200:
                    data = res.json()
                    if data.get('status') == 'failed':
                        logger.warning(f"API returned failed status for {url}: {data.get('message')}")
                        return None
                    return data
                logger.warning(f"Provider at {url} returned {res.status_code}: {res.text}")
                return None
        except Exception as e:
            logger.error(f"Request failed to {url}: {e}")
            return None

    async def get_matches_by_date(self, date_from: str, date_to: str = None) -> Dict:
        """
        Fetches matches for a specific date. Format: YYYYMMDD
        """
        clean_date = date_from.replace("-", "")
        res = await self._make_request("football-get-matches-by-date", {"date": clean_date})
        if res and 'response' in res:
            return {"response": self._normalize_matches(res['response'].get('matches', []))}
        return {"response": []}

    def _normalize_matches(self, matches: List[Dict]) -> List[Dict]:
        normalized = []
        for m in matches:
            home = m.get('home', {})
            away = m.get('away', {})
            normalized.append({
                "fixture": {"id": m.get('id'), "date": m.get('status', {}).get('utcTime') or m.get('time')},
                "teams": {
                    "home": {"name": home.get('name'), "id": home.get('id'), "logo": f"https://images.fotmob.com/image_resources/logo/teamlogo/{home.get('id')}.png"},
                    "away": {"name": away.get('name'), "id": away.get('id'), "logo": f"https://images.fotmob.com/image_resources/logo/teamlogo/{away.get('id')}.png"}
                },
                "league": {"name": str(m.get('leagueId')), "id": m.get('leagueId')},
                "goals": {"home": home.get('score'), "away": away.get('score')},
                "status": m.get('status', {})
            })
        return normalized

    async def search_teams(self, query: str) -> Dict:
        res = await self._make_request("football-teams-search", {"search": query})
        if res and 'response' in res:
             teams = []
             for item in res['response'].get('suggestions', []):
                 if item.get('type') == 'team':
                     teams.append({
                         "team": {
                             "id": item.get('id'),
                             "name": item.get('name'),
                             "logo": f"https://images.fotmob.com/image_resources/logo/teamlogo/{item.get('id')}.png"
                         }
                     })
             return {"response": teams}
        return {"response": []}

    async def get_teams_by_league(self, league_id: int):
        """
        Adapts 'standing' endpoint to provide team list since 'teams-by-league' is missing.
        """
        res = await self.get_standings(str(league_id))
        teams = []
        if res and 'response' in res and 'standing' in res['response']:
             for t in res['response']['standing']:
                 teams.append({
                     "team": {
                         "id": t.get('id'),
                         "name": t.get('name'),
                         "logo": f"https://images.fotmob.com/image_resources/logo/teamlogo/{t.get('id')}.png",
                         "country": "Unknown" # Provider doesn't give country in standing
                     },
                     "league": {"name": "League " + str(league_id)}
                 })
        return {"response": teams}

    async def list_leagues(self):
        # We use popular leagues as the primary list for efficiency
        res = await self._make_request("football-popular-leagues")
        if res and 'response' in res:
            leagues = []
            for l in res['response'].get('popular', []):
                leagues.append({
                    "league": {
                        "id": l.get('id'),
                        "name": l.get('name'),
                        "logo": l.get('logo')
                    }
                })
            return {"response": leagues}
        return {"response": []}

    async def get_standings(self, league_id: str):
        return await self._make_request("football-get-standing-all", {"leagueid": league_id})

    async def get_h2h(self, event_id: str):
        return await self._make_request("football-get-head-to-head", {"eventid": event_id})

    async def get_odds_by_event_id(self, event_id: str):
        # No working odds endpoint found yet for this provider.
        # Using poll result as a fallback for 'sentiment' odds if available.
        res = await self._make_request("football-get-odds-poll-match-events", {"eventid": event_id})
        return {"response": []} # Return empty for now to trigger internal model defaults
