import os
import httpx
from datetime import datetime
import logging
from typing import Dict, List, Any, Optional

logger = logging.getLogger(__name__)

class FootballAPIClient:
    """
    Unified Football Data Client with Multi-Provider Fallback.
    Priority: Sportradar -> RapidAPI (Multiple Endpoints)
    """
    def __init__(self):
        self.rapidapi_key = os.environ.get('RAPIDAPI_KEY')
        self.sportradar_key = os.environ.get('SPORTRADAR_API_KEY')
        self.fd_org_key = os.environ.get('FOOTBALL_DATA_API_KEY')
        
        # Hosts and Headers
        self.fd_host = "api.football-data.org/v4"
        self.rapid_host_main = "api-football-v1.p.rapidapi.com"
        self.rapid_host_ratings = "sportapi7.p.rapidapi.com"
        self.rapid_host_search = "free-api-live-football-data.p.rapidapi.com"
        self.rapid_host = self.rapid_host_main  # Default host for fixtures/odds
        
        self.headers_fd = {'X-Auth-Token': self.fd_org_key}
        self.headers_main = {'x-rapidapi-key': self.rapidapi_key, 'x-rapidapi-host': self.rapid_host_main}
        self.headers_ratings = {'x-rapidapi-key': self.rapidapi_key, 'x-rapidapi-host': self.rapid_host_ratings}
        self.headers_search = {'x-rapidapi-key': self.rapidapi_key, 'x-rapidapi-host': self.rapid_host_search}
        self.headers_rapid = self.headers_main # Default headers for fixtures/odds

    async def get_player_ratings(self, player_id: int, tournament_id: int, season_id: int):
        """Fetch SofaScore player ratings (SportAPI7)."""
        url = f"https://{self.rapid_host_ratings}/api/v1/player/{player_id}/unique-tournament/{tournament_id}/season/{season_id}/ratings"
        return await self._make_request(url, self.headers_ratings)

    async def search_players_live(self, query: str):
        """High-speed live player search."""
        url = f"https://{self.rapid_host_search}/football-players-search"
        return await self._make_request(url, self.headers_search, {"search": query})

    async def search_players(self, query: str):
        """Fallback to live search if main API fails."""
        res = await self.search_players_live(query)
        if res and res.get('status') == 'success':
            return res
        # Fallback to main API
        url = f"https://{self.rapid_host_main}/v3/players"
        return await self._make_request(url, self.headers_main, {"search": query})

    async def _make_request(self, url: str, headers: Dict, params: Dict = None):
        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                res = await client.get(url, headers=headers, params=params)
                if res.status_code == 200:
                    return res.json()
                logger.warning(f"Provider at {url} returned {res.status_code}")
                return None
        except Exception as e:
            logger.error(f"Request failed to {url}: {e}")
            return None

    # --- Unified Fixtures Method ---
    async def get_matches_by_date(self, date_from: str, date_to: str = None) -> Dict:
        """
        Attempts to fetch matches from all providers in order of priority.
        Supports single date (date_from) or range (date_from to date_to).
        """
        if not date_to:
            date_to = date_from

        # 1. Try Football-Data.org (Fast and reliable for daily matches)
        if self.fd_org_key:
            url = f"https://{self.fd_host}/matches"
            res = await self._make_request(url, self.headers_fd, {"dateFrom": date_from, "dateTo": date_to})
            if res and 'matches' in res:
                return self._normalize_fd_matches(res['matches'])

        # 2. Try RapidAPI (fallback)
        if self.rapidapi_key:
            url = f"https://{self.rapid_host}/v3/fixtures"
            params = {"from": date_from, "to": date_to}
            if date_from == date_to:
                params = {"date": date_from}
            res = await self._make_request(url, self.headers_rapid, params)
            if res and 'response' in res:
                return self._normalize_rapid_matches(res['response'])
        
        return {"response": []}

    # --- Unified Team Search ---
    async def search_teams(self, query: str) -> Dict:
        if self.rapidapi_key:
            url = f"https://{self.rapid_host}/v3/teams"
            res = await self._make_request(url, self.headers_rapid, {"search": query})
            return res or {"response": []}
        return {"response": []}

    # --- Normalization Helpers ---
    def _normalize_fd_matches(self, matches: List[Dict]) -> List[Dict]:
        normalized = []
        for m in matches:
            normalized.append({
                "fixture": {"id": m['id'], "date": m['utcDate']},
                "teams": {
                    "home": {"name": m['homeTeam']['name'], "logo": m['homeTeam'].get('crest')},
                    "away": {"name": m['awayTeam']['name'], "logo": m['awayTeam'].get('crest')}
                },
                "league": {"name": m['competition']['name']},
                "goals": {"home": m.get('score', {}).get('fullTime', {}).get('home'), 
                          "away": m.get('score', {}).get('fullTime', {}).get('away')}
            })
        return {"response": normalized}

    def _normalize_rapid_matches(self, response: List[Dict]) -> Dict:
        # RapidAPI is already in our desired format
        return {"response": response}

    # --- Existing Methods (Delegating to RapidAPI as the most comprehensive for detail) ---
    async def get_team_fixtures(self, team_id: int, last: int = 40):
        url = f"https://{self.rapid_host}/v3/fixtures"
        return await self._make_request(url, self.headers_rapid, {"team": team_id, "last": last})

    async def get_odds_by_event_id(self, event_id: int):
        url = f"https://{self.rapid_host}/v3/odds"
        return await self._make_request(url, self.headers_rapid, {"fixture": event_id})

    async def list_leagues(self):
        url = f"https://{self.rapid_host}/v3/leagues"
        return await self._make_request(url, self.headers_rapid, {"type": "league", "season": str(datetime.now().year - 1)})
    
    async def get_teams_by_league(self, league_id: int):
        url = f"https://{self.rapid_host}/v3/teams"
        return await self._make_request(url, self.headers_rapid, {"league": str(league_id), "season": str(datetime.now().year)})

    async def get_standings(self, league_id: int):
        url = f"https://{self.rapid_host}/v3/standings"
        return await self._make_request(url, self.headers_rapid, {"league": str(league_id), "season": str(datetime.now().year)})

    async def get_h2h(self, team1_id: int, team2_id: int):
        url = f"https://{self.rapid_host}/v3/fixtures/headtohead"
        return await self._make_request(url, self.headers_rapid, {"h2h": f"{team1_id}-{team2_id}", "last": "10"})
