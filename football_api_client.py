import os
import httpx
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

class FootballAPIClient:
    def __init__(self, api_key: str = None):
        self.api_key = api_key or os.environ.get('RAPIDAPI_KEY')
        self.host = os.environ.get('RAPIDAPI_HOST', "api-football-v1.p.rapidapi.com")
        self.base_url = f"https://{self.host}/v3"
        self.headers = {
            'x-rapidapi-key': self.api_key,
            'x-rapidapi-host': self.host
        }

    async def _make_request(self, endpoint, params=None):
        if not self.api_key:
            return {"error": "RapidAPI key not configured."}
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                # If using free-api-live-football-data, it might not need /v3 or has different structure
                # But we'll try to be adaptive.
                url = f"{self.base_url}/{endpoint}"
                response = await client.get(url, headers=self.headers, params=params)

                if response.status_code == 404 and "/v3/" in url:
                    # Fallback to non-v3 if v3 fails with 404
                    url = f"https://{self.host}/{endpoint}"
                    response = await client.get(url, headers=self.headers, params=params)

                response.raise_for_status()
                return response.json()
        except httpx.HTTPStatusError as e:
            logger.error(f"HTTP error {e.response.status_code} for {endpoint}: {e.response.text}")
            return {"error": str(e), "status_code": e.response.status_code if e.response else 500}
        except Exception as e:
            logger.error(f"Unexpected error for {endpoint}: {e}")
            return {"error": str(e), "status_code": 500}

    async def search_teams(self, query: str):
        # Adaptive search param
        params = {"search": query} if "api-football" in self.host else {"q": query, "team_name": query}
        res = await self._make_request("teams", params=params)
        return res

    async def get_team_detail(self, team_id: int):
        return await self._make_request("teams", params={"id": team_id, "team_id": team_id})

    async def get_team_fixtures(self, team_id: int, last: int = 40):
        endpoint = "fixtures" if "api-football" in self.host else "football-get-matches-by-team"
        params = {"team": team_id, "last": last} if "api-football" in self.host else {"team_id": team_id}
        return await self._make_request(endpoint, params=params)

    async def list_leagues(self):
        return await self._make_request("leagues", params={"type": "league", "season": str(datetime.now().year - 1)})

    async def get_league_detail(self, league_id: int):
        return await self._make_request("leagues", params={"id": league_id})
        
    async def get_teams_by_league(self, league_id: int):
        season = datetime.now().year
        return await self._make_request("teams", params={"league": str(league_id), "season": str(season)})

    async def search_leagues(self, query: str):
        params = {"search": query} if "api-football" in self.host else {"q": query}
        return await self._make_request("leagues", params=params)

    async def get_matches_by_date(self, date: str):
        if "free-api-live-football-data" in self.host:
            for ep in ["football-get-matches-by-date", "get-matches-by-date", "fixtures"]:
                res = await self._make_request(ep, params={"match_date": date, "date": date})
                if res.get('response'): return res
            return await self._make_request("football-get-matches-by-date", params={"match_date": date})
        return await self._make_request("fixtures", params={"date": date})

    async def get_odds_by_event_id(self, event_id: int):
        endpoint = "odds" if "api-football" in self.host else "football-get-odds-by-match"
        params = {"fixture": event_id} if "api-football" in self.host else {"match_id": event_id}
        return await self._make_request(endpoint, params=params)

    async def get_stats_by_event_id(self, event_id: int):
        return await self._make_request("fixtures/statistics", params={"fixture": event_id})

    async def get_h2h(self, team1_id: int, team2_id: int):
        h2h_str = f"{team1_id}-{team2_id}"
        return await self._make_request("fixtures/headtohead", params={"h2h": h2h_str})

    async def get_standings(self, league_id: int):
        season = datetime.now().year
        return await self._make_request("standings", params={"league": str(league_id), "season": str(season)})

    async def list_players_by_team(self, team_id: int):
        season = datetime.now().year
        return await self._make_request("players", params={"team": str(team_id), "season": str(season)})

    async def get_player_detail(self, player_id: int):
        season = datetime.now().year
        return await self._make_request("players", params={"id": str(player_id), "season": str(season)})
        
    async def search_players(self, query: str):
        season = datetime.now().year
        res = await self._make_request("players", params={"search": query, "season": str(season)})
        if not res.get('response') or len(res['response']) == 0:
            res = await self._make_request("players", params={"search": query, "season": str(season - 1)})
        return res
