import os
import httpx
from datetime import datetime
import logging
from typing import Dict, List, Any, Optional

logger = logging.getLogger(__name__)

class FootballAPIClient:
    """
    Unified Football Data Client with Multi-Provider Fallback.
    Providers: RapidAPI, TheSportDB, Sofascore (H2H)
    """
    def __init__(self):
        self.rapidapi_key = os.environ.get('RAPIDAPI_KEY')
        self.tsdb_key = "3" # TheSportDB Public Test Key (Stable for scores)
        self.rapid_host = "free-api-live-football-data.p.rapidapi.com"
        self.sofascore_host = "sofascore.p.rapidapi.com"
        
        self.headers_rapid = {
            'x-rapidapi-key': self.rapidapi_key or "",
            'x-rapidapi-host': self.rapid_host,
            'Content-Type': 'application/json'
        }
        
        self.headers_sofascore = {
            'x-rapidapi-key': self.rapidapi_key or "",
            'x-rapidapi-host': self.sofascore_host,
            'Content-Type': 'application/json'
        }

    async def _make_request(self, endpoint: str, params: Dict = None, provider: str = "rapid"):
        if provider == "rapid":
            url = f"https://{self.rapid_host}/{endpoint}"
            headers = self.headers_rapid
        elif provider == "sofascore":
            url = f"https://{self.sofascore_host}/{endpoint}"
            headers = self.headers_sofascore
        elif provider == "tsdb":
            url = f"https://www.thesportdb.com/api/v1/json/{self.tsdb_key}/{endpoint}"
            headers = {'Content-Type': 'application/json'}
        else:
            return None

        try:
            async with httpx.AsyncClient(timeout=20.0) as client:
                res = await client.get(url, headers=headers, params=params)
                if res.status_code == 200:
                    return res.json()
                return None
        except Exception as e:
            logger.error(f"Request failed to {provider}: {e}")
            return None

    async def get_matches_by_date(self, date_from: str, date_to: str = None) -> Dict:
        """
        Fetches matches with fallback to TheSportDB.
        """
        # 1. Try RapidAPI
        clean_date = date_from.replace("-", "")
        res = await self._make_request("football-get-matches-by-date", {"date": clean_date}, provider="rapid")
        if res and 'response' in res:
            return {"response": self._normalize_matches(res['response'].get('matches', []))}
            
        # 2. Fallback to TheSportDB (No Key Required for Public API)
        logger.info("RapidAPI limit hit. Falling back to TheSportDB for today's scores...")
        res_tsdb = await self._make_request("eventsday.php", {"d": date_from, "s": "Soccer"}, provider="tsdb")
        if res_tsdb and 'events' in res_tsdb:
            return {"response": self._normalize_tsdb_matches(res_tsdb['events'])}
                
        return {"response": []}

    def _normalize_tsdb_matches(self, events: List[Dict]) -> List[Dict]:
        normalized = []
        for e in events:
            normalized.append({
                "fixture": {"id": e.get('idEvent'), "date": f"{e.get('dateEvent')}T{e.get('strTime')}"},
                "teams": {
                    "home": {"name": e.get('strHomeTeam'), "id": e.get('idHomeTeam'), "logo": ""},
                    "away": {"name": e.get('strAwayTeam'), "id": e.get('idAwayTeam'), "logo": ""}
                },
                "league": {"name": e.get('strLeague'), "id": e.get('idLeague')},
                "goals": {"home": e.get('intHomeScore'), "away": e.get('intAwayScore')},
                "status": {"long": e.get('strStatus')}
            })
        return normalized

    async def get_sofascore_h2h(self, team1_id: int, team2_id: int):
        """
        Uses Sofascore API for deep H2H analysis.
        """
        return await self._make_request("matches/get-h2h-events", {
            "homeTeamId": team1_id,
            "awayTeamId": team2_id
        }, provider="sofascore")

    async def get_matches_by_date(self, date_from: str, date_to: str = None) -> Dict:
        """
        Fetches matches with fallback.
        """
        # Try RapidAPI first
        clean_date = date_from.replace("-", "")
        res = await self._make_request("football-get-matches-by-date", {"date": clean_date}, provider="rapid")
        
        if res and 'response' in res:
            return {"response": self._normalize_matches(res['response'].get('matches', []))}
            
        # Fallback to Football-Data.org if RapidAPI is exhausted (429)
        if self.fd_org_key:
            logger.info("RapidAPI exhausted. Falling back to Football-Data.org...")
            # Football-Data uses dateFrom/dateTo
            res_fd = await self._make_request("matches", {"dateFrom": date_from, "dateTo": date_from}, provider="fd")
            if res_fd and 'matches' in res_fd:
                return {"response": self._normalize_fd_matches(res_fd['matches'])}
                
        return {"response": []}

    def _normalize_fd_matches(self, matches: List[Dict]) -> List[Dict]:
        normalized = []
        for m in matches:
            normalized.append({
                "fixture": {"id": m.get('id'), "date": m.get('utcDate')},
                "teams": {
                    "home": {"name": m['homeTeam']['name'], "id": m['homeTeam']['id'], "logo": m['homeTeam'].get('crest')},
                    "away": {"name": m['awayTeam']['name'], "id": m['awayTeam']['id'], "logo": m['awayTeam'].get('crest')}
                },
                "league": {"name": m['competition']['name'], "id": m['competition']['id']},
                "goals": {"home": m.get('score', {}).get('fullTime', {}).get('home'), "away": m.get('score', {}).get('fullTime', {}).get('away')},
                "status": {"long": m.get('status')}
            })
        return normalized

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
