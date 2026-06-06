import os
import httpx
from datetime import datetime, timedelta
import asyncio
import logging
from typing import Dict, List, Any, Optional

logger = logging.getLogger(__name__)

class FootballAPIClient:
    """
    Unified Football Data Client for free-api-live-football-data.p.rapidapi.com (Creativesdev)
    """
    def __init__(self):
        # Prefer the key provided in environment, fallback to User's key
        self.rapidapi_key = os.environ.get('RAPIDAPI_KEY') or os.environ.get('RAPID_API_KEY', "9d484677a1mshd7d8d62a256ff73p138c8bjsn0e732e2acfd1")
        self.rapid_host = "free-api-live-football-data.p.rapidapi.com"
        self.headers = {
            'x-rapidapi-key': self.rapidapi_key,
            'x-rapidapi-host': self.rapid_host,
            'Content-Type': 'application/json'
        }
        # Priority mapping for major leagues (IDs from the provider)
        self.POPULAR_LEAGUES = {
            47: "Premier League", 
            87: "La Liga", 
            54: "Bundesliga", 
            55: "Serie A", 
            53: "Ligue 1", 
            42: "Champions League", 
            73: "Europa League",
            102: "Friendly International",
            530: "Morocco Botola Pro",
            50: "MLS",
            67: "Eredivisie",
            108: "FIFA World Cup",
            104: "Euro Championship",
            105: "Copa America",
            77: "FA Cup",
            110: "AFCON",
            9085: "Egypt League Cup",
            342: "Nigeria Professional Football League",
            918043: "Ettan Norra",
            268: "Liga BetPlay",
            259: "Uruguayan Championship",
            262: "Bolivian Primera División"
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
        Fetches matches for a specific date or range. Format: YYYY-MM-DD
        """
        if not date_to or date_to == date_from:
            clean_date = date_from.replace("-", "")
            res = await self._make_request("football-get-matches-by-date", {"date": clean_date})
            if res and 'response' in res:
                matches = self._normalize_matches(res['response'].get('matches', []))
                self._sort_matches(matches)
                return {"response": matches}
            return {"response": []}
        
        # Handle range
        start = datetime.strptime(date_from, "%Y-%m-%d")
        end = datetime.strptime(date_to, "%Y-%m-%d")
        all_matches = []
        
        # Limit to 7 days to avoid excessive API calls
        days = (end - start).days
        if days > 7:
            end = start + timedelta(days=7)
            days = 7
            
        for i in range(days + 1):
            target_date = (start + timedelta(days=i)).strftime("%Y%m%d")
            res = await self._make_request("football-get-matches-by-date", {"date": target_date})
            if res and 'response' in res:
                all_matches.extend(self._normalize_matches(res['response'].get('matches', [])))
            await asyncio.sleep(0.1) # Small delay to avoid rate limiting
            
        self._sort_matches(all_matches)
        return {"response": all_matches}

    def _sort_matches(self, matches: List[Dict]):
        priority_ids = list(self.POPULAR_LEAGUES.keys())
        
        def sort_key(m):
            lid = m['league']['id']
            if lid in priority_ids:
                return (0, priority_ids.index(lid), m['fixture']['date'])
            return (1, m['league']['name'], m['fixture']['date'])
            
        matches.sort(key=sort_key)

    def _normalize_matches(self, matches: List[Dict]) -> List[Dict]:
        normalized = []
        for m in matches:
            home = m.get('home', {})
            away = m.get('away', {})
            league_id = m.get('leagueId')
            # Resolve league name from mapping or use ID as fallback
            league_name = self.POPULAR_LEAGUES.get(league_id, f"League {league_id}")
            
            normalized.append({
                "fixture": {"id": m.get('id'), "date": m.get('status', {}).get('utcTime') or m.get('time')},
                "teams": {
                    "home": {"name": home.get('name'), "id": home.get('id'), "logo": f"https://images.fotmob.com/image_resources/logo/teamlogo/{home.get('id')}.png"},
                    "away": {"name": away.get('name'), "id": away.get('id'), "logo": f"https://images.fotmob.com/image_resources/logo/teamlogo/{away.get('id')}.png"}
                },
                "league": {"name": league_name, "id": league_id},
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
        league_name = self.POPULAR_LEAGUES.get(league_id, f"League {league_id}")
        
        if res and 'response' in res and 'standing' in res['response']:
             for t in res['response']['standing']:
                 teams.append({
                     "team": {
                         "id": t.get('id'),
                         "name": t.get('name'),
                         "logo": f"https://images.fotmob.com/image_resources/logo/teamlogo/{t.get('id')}.png",
                         "country": "Unknown" # Provider doesn't give country in standing
                     },
                     "league": {"name": league_name}
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

    async def search_leagues(self, query: str):
        res = await self._make_request("football-teams-search", {"search": query})
        if res and 'response' in res:
             leagues = []
             for item in res['response'].get('suggestions', []):
                 if item.get('type') == 'league':
                     leagues.append({
                         "league": {
                             "id": item.get('id'),
                             "name": item.get('name')
                         }
                     })
             return {"response": leagues}
        return {"response": []}

    async def search_players(self, query: str):
        res = await self._make_request("football-teams-search", {"search": query})
        if res and 'response' in res:
             players = []
             for item in res['response'].get('suggestions', []):
                 if item.get('type') == 'player':
                     players.append({
                         "player": {
                             "id": item.get('id'),
                             "name": item.get('name')
                         }
                     })
             return {"response": players}
        return {"response": []}

    async def get_team_detail(self, team_id: int):
        return await self._make_request("football-get-team-info", {"teamid": team_id})

    async def get_league_detail(self, league_id: int):
        return await self._make_request("football-get-league-info", {"leagueid": league_id})

    async def list_players_by_team(self, team_id: int):
        return await self._make_request("football-get-team-players", {"teamid": team_id})

    async def get_player_detail(self, player_id: int):
        return await self._make_request("football-get-player-info", {"playerid": player_id})

    async def get_stats_by_event_id(self, event_id: int):
        return await self._make_request("football-get-match-stats", {"eventid": event_id})

    async def get_standings(self, league_id: str):
        return await self._make_request("football-get-standing-all", {"leagueid": league_id})

    async def get_h2h(self, event_id: str):
        return await self._make_request("football-get-head-to-head", {"eventid": event_id})

    async def get_odds_by_event_id(self, event_id: str):
        # No working odds endpoint found yet for this provider.
        # Using poll result as a fallback for 'sentiment' odds if available.
        res = await self._make_request("football-get-odds-poll-match-events", {"eventid": event_id})
        return {"response": []} # Return empty for now to trigger internal model defaults

    def get_365scores_match_url(self, home_team: str, away_team: str) -> str:
        """
        Generates a 365scores search URL for a given match.
        """
        query = f"{home_team} vs {away_team}"
        encoded_query = query.replace(" ", "%20")
        return f"https://www.365scores.com/football/search?query={encoded_query}"
