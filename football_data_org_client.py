import os
import httpx
from datetime import datetime, timedelta
import logging
from typing import Dict, List, Any, Optional

logger = logging.getLogger(__name__)

class FootballDataOrgClient:
    """
    Football Data Client for football-data.org (v4)
    """
    def __init__(self):
        self.api_key = os.environ.get('FOOTBALL_DATA_API_KEY')
        self.base_url = "https://api.football-data.org/v4"
        self.headers = {
            'X-Auth-Token': self.api_key,
            'Content-Type': 'application/json'
        }
        # Mapping common league IDs to football-data.org codes
        # Note: football-data.org uses codes like 'PL', 'PD', etc.
        self.LEAGUE_MAP = {
            2021: "PL",   # Premier League
            2014: "PD",   # Primera Division
            2002: "BL1",  # Bundesliga
            2019: "SA",   # Serie A
            2015: "FL1",  # Ligue 1
            2001: "CL",   # Champions League
            2003: "DED",  # Eredivisie
            2017: "PPL",  # Primeira Liga
            2013: "BSA",  # Campeonato Brasileiro Série A
            2016: "ELC",  # Championship
            2000: "WC",   # FIFA World Cup
            2018: "EC",   # European Championship
        }
        
        # Reverse mapping for convenience
        self.ID_MAP = {v: k for k, v in self.LEAGUE_MAP.items()}

    async def _make_request(self, endpoint: str, params: Dict = None):
        if not self.api_key:
            logger.error("FOOTBALL_DATA_API_KEY not set.")
            return None
            
        url = f"{self.base_url}/{endpoint.lstrip('/')}"
        try:
            async with httpx.AsyncClient(timeout=25.0) as client:
                res = await client.get(url, headers=self.headers, params=params)
                if res.status_code == 200:
                    return res.json()
                elif res.status_code == 429:
                    logger.warning(f"Rate limit hit for {url}. Seconds to reset: {res.headers.get('X-RequestCounter-Reset')}")
                    return None
                logger.warning(f"football-data.org at {url} returned {res.status_code}: {res.text}")
                return None
        except Exception as e:
            logger.error(f"Request failed to {url}: {e}")
            return None

    async def get_matches_by_date(self, date_from: str, date_to: str = None, competitions: List[str] = None) -> Dict:
        """
        Fetches matches for a specific date range. Format: YYYY-MM-DD
        """
        if not date_to:
            date_to = date_from
            
        params = {"dateFrom": date_from, "dateTo": date_to}
        if competitions:
            params["competitions"] = ",".join(competitions)

        res = await self._make_request("matches", params)
        if res and 'matches' in res:
            matches = self._normalize_matches(res['matches'])
            return {"response": matches}
        return {"response": []}

    async def get_matches(self, **kwargs) -> Dict:
        """
        Generic matches endpoint
        """
        res = await self._make_request("matches", kwargs)
        if res and 'matches' in res:
            return {"response": self._normalize_matches(res['matches'])}
        return {"response": []}

    def _normalize_matches(self, matches: List[Dict]) -> List[Dict]:
        normalized = []
        for m in matches:
            home = m.get('homeTeam', {})
            away = m.get('awayTeam', {})
            competition = m.get('competition', {})
            score = m.get('score', {}).get('fullTime', {})
            
            normalized.append({
                "fixture": {
                    "id": m.get('id'), 
                    "date": m.get('utcDate')
                },
                "teams": {
                    "home": {
                        "name": home.get('name'), 
                        "id": home.get('id'), 
                        "logo": home.get('crest')
                    },
                    "away": {
                        "name": away.get('name'), 
                        "id": away.get('id'), 
                        "logo": away.get('crest')
                    }
                },
                "league": {
                    "name": competition.get('name'), 
                    "id": competition.get('id'),
                    "code": competition.get('code')
                },
                "goals": {
                    "home": score.get('home'), 
                    "away": score.get('away')
                },
                "status": {
                    "long": m.get('status'),
                    "utcTime": m.get('utcDate')
                }
            })
        return normalized

    async def get_standings(self, league_id_or_code: str):
        endpoint = f"competitions/{league_id_or_code}/standings"
        res = await self._make_request(endpoint)
        if res and 'standings' in res:
            # Flatten standings to match expected format
            # RapidAPI client expected: {"standing": [...]}
            flattened = []
            for table in res['standings']:
                if table.get('type') == 'TOTAL':
                    for entry in table.get('table', []):
                        team = entry.get('team', {})
                        flattened.append({
                            "id": team.get('id'),
                            "name": team.get('name'),
                            "logo": team.get('crest'),
                            "idx": entry.get('position'),
                            "pts": entry.get('points'),
                            "played": entry.get('playedGames'),
                            "wins": entry.get('won'),
                            "draws": entry.get('draw'),
                            "losses": entry.get('lost'),
                            "goalsFor": entry.get('goalsFor'),
                            "goalsAgainst": entry.get('goalsAgainst'),
                            "goalConDiff": entry.get('goalDifference')
                        })
            return {"response": {"standing": flattened}}
        return {"response": {}}

    async def get_teams_by_league(self, league_id_or_code: str):
        endpoint = f"competitions/{league_id_or_code}/teams"
        res = await self._make_request(endpoint)
        if res and 'teams' in res:
            teams = []
            league_name = res.get('competition', {}).get('name', 'Unknown')
            for t in res['teams']:
                teams.append({
                    "team": {
                        "id": t.get('id'),
                        "name": t.get('name'),
                        "logo": t.get('crest'),
                        "country": t.get('area', {}).get('name')
                    },
                    "league": {"name": league_name}
                })
            return {"response": teams}
        return {"response": []}

    async def list_leagues(self):
        res = await self._make_request("competitions")
        if res and 'competitions' in res:
            leagues = []
            for l in res['competitions']:
                leagues.append({
                    "league": {
                        "id": l.get('id'),
                        "name": l.get('name'),
                        "logo": l.get('emblem'),
                        "code": l.get('code')
                    }
                })
            return {"response": leagues}
        return {"response": []}

    async def get_team_detail(self, team_id: int):
        res = await self._make_request(f"teams/{team_id}")
        if res:
            return {"response": res}
        return None

    async def list_players_by_team(self, team_id: int):
        res = await self._make_request(f"teams/{team_id}")
        if res and 'squad' in res:
            players = []
            for p in res['squad']:
                players.append({
                    "id": p.get('id'),
                    "name": p.get('name'),
                    "position": p.get('position'),
                    "country": p.get('nationality'),
                    "age": self._calculate_age(p.get('dateOfBirth'))
                })
            return {"response": players}
        return {"response": []}

    def _calculate_age(self, dob_str: str) -> Optional[int]:
        if not dob_str:
            return None
        try:
            dob = datetime.strptime(dob_str, "%Y-%m-%d")
            today = datetime.now()
            return today.year - dob.year - ((today.month, today.day) < (dob.month, dob.day))
        except:
            return None

    async def get_player_detail(self, player_id: int):
        res = await self._make_request(f"persons/{player_id}")
        if res:
            return {"response": res}
        return None

    async def get_h2h(self, team1_id: int, team2_id: int = None, match_id: int = None):
        """
        football-data.org uses match_id for H2H
        """
        if match_id:
            res = await self._make_request(f"matches/{match_id}/head2head")
            if res:
                return {"response": res}
        return {"response": {}}

    async def get_odds_by_event_id(self, event_id: int):
        # football-data.org doesn't provide odds on free tier
        return {"response": []}

    async def search_teams(self, query: str):
        # No direct search, list all teams and filter? Heavy for 10req/min.
        # As a fallback, we'll try to use /v4/teams which lists teams, but it's paginated.
        # For efficiency, we might just return empty or search in a small subset.
        # Actually, let's try to fetch teams with a name filter if it exists (undocumented but common)
        # Or just return empty to avoid wasting quota.
        return {"response": []}

    async def search_players(self, query: str):
        return {"response": []}

    async def search_leagues(self, query: str):
        leagues = await self.list_leagues()
        if leagues and 'response' in leagues:
            filtered = [l for l in leagues['response'] if query.lower() in l['league']['name'].lower()]
            return {"response": filtered}
        return {"response": []}

    async def get_team_fixtures(self, team_id: int, last: int = 10):
        res = await self._make_request(f"teams/{team_id}/matches", {"status": "FINISHED", "limit": last})
        if res and 'matches' in res:
             return {"response": self._normalize_matches(res['matches'])}
        return {"response": []}

    def get_365scores_match_url(self, home_team: str, away_team: str) -> str:
        query = f"{home_team} vs {away_team}"
        encoded_query = query.replace(" ", "%20")
        return f"https://www.365scores.com/football/search?query={encoded_query}"
