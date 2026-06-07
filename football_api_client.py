import os
import httpx
import asyncio
import pandas as pd
from datetime import datetime
import logging
from typing import Dict, List, Any, Optional

logger = logging.getLogger(__name__)

class BaseFootballProvider:
    def __init__(self, api_key: str = None):
        self.api_key = api_key
        self.headers = {}

    async def get_matches(self, date_from: str, date_to: str) -> List[Dict]:
        raise NotImplementedError

    async def get_fixtures(self, league_id: int, season: int, from_date: str, to_date: str) -> List[Dict]:
        return []

    def normalize_match(self, match: Dict) -> Dict:
        # Enforce strict schema: fixture, teams, league, goals, status
        return {
            "fixture": {"id": match.get("fixture", {}).get("id"), "date": match.get("fixture", {}).get("date")},
            "teams": {
                "home": {"name": match.get("teams", {}).get("home", {}).get("name"), "id": match.get("teams", {}).get("home", {}).get("id"), "logo": match.get("teams", {}).get("home", {}).get("logo")},
                "away": {"name": match.get("teams", {}).get("away", {}).get("name"), "id": match.get("teams", {}).get("away", {}).get("id"), "logo": match.get("teams", {}).get("away", {}).get("logo")}
            },
            "league": {"name": match.get("league", {}).get("name"), "id": match.get("league", {}).get("id")},
            "goals": {"home": match.get("goals", {}).get("home"), "away": match.get("goals", {}).get("away")},
            "status": match.get("status", {"long": "Unknown"})
        }

class LocalCSVProvider(BaseFootballProvider):
    def __init__(self, file_path: str):
        super().__init__()
        self.file_path = file_path
        self.df = pd.read_csv(file_path)

    async def get_matches(self, date_from: str, date_to: str) -> List[Dict]:
        mask = (self.df['MatchDate'] >= date_from) & (self.df['MatchDate'] <= date_to)
        subset = self.df.loc[mask]
        matches = []
        for _, row in subset.iterrows():
            matches.append({
                "fixture": {"id": f"{row['HomeTeam']}-{row['AwayTeam']}-{row['MatchDate']}", "date": row['MatchDate']},
                "teams": {
                    "home": {"name": row['HomeTeam'], "id": None, "logo": None},
                    "away": {"name": row['AwayTeam'], "id": None, "logo": None}
                },
                "league": {"name": row['Division'], "id": None},
                "goals": {"home": row['FTHome'], "away": row['FTAway']},
                "status": {"long": "Finished"}
            })
        return [self.normalize_match(m) for m in matches]

# --- Existing Providers Updated to inherit BaseFootballProvider and use normalize_match ---
class RapidAPIProvider(BaseFootballProvider):
    def __init__(self, api_key: str):
        super().__init__(api_key)
        self.host = "free-api-live-football-data.p.rapidapi.com"
        self.headers = {'x-rapidapi-key': self.api_key, 'x-rapidapi-host': self.host}

    async def get_matches(self, date_from: str, date_to: str) -> List[Dict]:
        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                res = await client.get(f"https://{self.host}/football-get-matches-by-date", headers=self.headers, params={"date": date_from.replace("-", "")})
                if res.status_code == 200:
                    data = res.json()
                    return [self.normalize_match(self._raw_to_internal(m)) for m in data.get('response', {}).get('matches', [])]
                return []
        except: return []

    def _raw_to_internal(self, m: Dict) -> Dict:
        home = m.get('home', {})
        away = m.get('away', {})
        return {
            "fixture": {"id": m.get('id'), "date": m.get('status', {}).get('utcTime')},
            "teams": {
                "home": {"name": home.get('name'), "id": home.get('id'), "logo": f"https://images.fotmob.com/image_resources/logo/teamlogo/{home.get('id')}.png"},
                "away": {"name": away.get('name'), "id": away.get('id'), "logo": f"https://images.fotmob.com/image_resources/logo/teamlogo/{away.get('id')}.png"}
            },
            "league": {"name": str(m.get('leagueId')), "id": m.get('leagueId')},
            "goals": {"home": home.get('score'), "away": away.get('score')},
            "status": m.get('status', {"long": "Scheduled"})
        }

class ThreeSixFiveScoresProvider(BaseFootballProvider):
    def __init__(self, api_key: str):
        super().__init__(api_key)
        self.host = "365scores.p.rapidapi.com"
        self.headers = {'x-rapidapi-key': self.api_key, 'x-rapidapi-host': self.host}

    async def get_matches(self, date_from: str, date_to: str) -> List[Dict]:
        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                res = await client.get(f"https://{self.host}/matches/list", headers=self.headers, params={"date": date_from})
                if res.status_code == 200:
                    data = res.json()
                    return [self.normalize_match(self._raw_to_internal(m)) for m in data.get('matches', [])]
                return []
        except: return []

    def _raw_to_internal(self, m: Dict) -> Dict:
        return {
            "fixture": {"id": m.get('id'), "date": m.get('startTime')},
            "teams": {
                "home": {"name": m.get('homeTeam', {}).get('name'), "id": m.get('homeTeam', {}).get('id'), "logo": None},
                "away": {"name": m.get('awayTeam', {}).get('name'), "id": m.get('awayTeam', {}).get('id'), "logo": None}
            },
            "league": {"name": m.get('competition', {}).get('name'), "id": m.get('competition', {}).get('id')},
            "goals": {"home": m.get('homeScore'), "away": m.get('awayScore')},
            "status": {"long": m.get('statusText')}
        }

class FootballDataOrgProvider(BaseFootballProvider):
    def __init__(self, api_key: str):
        super().__init__(api_key)
        self.base_url = "https://api.football-data.org/v4"
        self.headers = {'X-Auth-Token': self.api_key}

    async def get_matches(self, date_from: str, date_to: str) -> List[Dict]:
        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                res = await client.get(f"{self.base_url}/matches", headers=self.headers, params={"dateFrom": date_from, "dateTo": date_to})
                if res.status_code == 200:
                    data = res.json()
                    return [self.normalize_match(self._raw_to_internal(m)) for m in data.get('matches', [])]
                return []
        except: return []

    def _raw_to_internal(self, m: Dict) -> Dict:
        return {
            "fixture": {"id": m.get('id'), "date": m.get('utcDate')},
            "teams": {
                "home": {"name": m.get('homeTeam', {}).get('name'), "id": m.get('homeTeam', {}).get('id'), "logo": m.get('homeTeam', {}).get('crest')},
                "away": {"name": m.get('awayTeam', {}).get('name'), "id": m.get('awayTeam', {}).get('id'), "logo": m.get('awayTeam', {}).get('crest')}
            },
            "league": {"name": m.get('competition', {}).get('name'), "id": m.get('competition', {}).get('id')},
            "goals": {"home": m.get('score', {}).get('fullTime', {}).get('home'), "away": m.get('score', {}).get('fullTime', {}).get('away')},
            "status": {"long": m.get('status')}
        }

class SportradarProvider(BaseFootballProvider):
    def __init__(self, api_key: str):
        super().__init__(api_key)
        self.base_url = "https://api.sportradar.com/soccer/trial/v4/en"

    async def get_matches(self, date_from: str, date_to: str) -> List[Dict]:
        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                res = await client.get(f"{self.base_url}/schedules/{date_from}/schedule.json", params={"api_key": self.api_key})
                if res.status_code == 200:
                    data = res.json()
                    return [self.normalize_match(self._raw_to_internal(s)) for s in data.get('schedules', [])]
                return []
        except: return []

    def _raw_to_internal(self, s: Dict) -> Dict:
        ev = s.get('sport_event', {})
        st = s.get('sport_event_status', {})
        home = next((c for c in ev.get('competitors', []) if c.get('qualifier') == 'home'), {})
        away = next((c for c in ev.get('competitors', []) if c.get('qualifier') == 'away'), {})
        return {
            "fixture": {"id": ev.get('id'), "date": ev.get('start_time')},
            "teams": {
                "home": {"name": home.get('name'), "id": home.get('id'), "logo": None},
                "away": {"name": away.get('name'), "id": away.get('id'), "logo": None}
            },
            "league": {"name": ev.get('sport_event_context', {}).get('league', {}).get('name'), "id": ev.get('sport_event_context', {}).get('league', {}).get('id')},
            "goals": {"home": st.get('home_score'), "away": st.get('away_score')},
            "status": {"long": st.get('status')}
        }

class TheStatsAPIProvider(BaseFootballProvider):
    def __init__(self, api_key: str):
        super().__init__(api_key)
        self.base_url = "https://thestatsapi.com"
        self.headers = {"Authorization": f"Bearer {self.api_key}", "Accept": "application/json"}

    async def get_match_deep_stats(self, match_id: str) -> Dict[str, Any]:
        return {} # Simplified for now

    async def get_matches(self, date_from: str, date_to: str) -> List[Dict]:
        return []
    
    def normalize_match(self, match: Dict) -> Dict:
        return {}

class FootballAPIClient:
    def __init__(self):
        self.providers = []
        self.stats_provider = None
        self.circuit_breaker = {} # {provider_name: {"status": "healthy", "last_failure": None}}
        self.POPULAR_LEAGUES = {
            47: "Premier League", 87: "La Liga", 54: "Bundesliga", 55: "Serie A", 
            53: "Ligue 1", 42: "Champions League", 73: "Europa League"
        }
        
        # Load keys strictly from environment
        rapid_key = os.environ.get('RAPIDAPI_KEY')
        fd_key = os.environ.get('FOOTBALL_DATA_API_KEY')
        sr_key = os.environ.get('SPORTRADAR_API_KEY')
        stats_key = os.environ.get('THESTATSAPI_KEY')
        
        if fd_key:
            self.providers.append(FootballDataOrgProvider(fd_key))
            self.circuit_breaker["FootballDataOrgProvider"] = {"status": "healthy", "last_failure": None}
        if sr_key:
            self.providers.append(SportradarProvider(sr_key))
            self.circuit_breaker["SportradarProvider"] = {"status": "healthy", "last_failure": None}
        if rapid_key:
            self.providers.append(ThreeSixFiveScoresProvider(rapid_key))
            self.providers.append(RapidAPIProvider(rapid_key))
            self.circuit_breaker["ThreeSixFiveScoresProvider"] = {"status": "healthy", "last_failure": None}
            self.circuit_breaker["RapidAPIProvider"] = {"status": "healthy", "last_failure": None}
        if stats_key:
            self.stats_provider = TheStatsAPIProvider(stats_key)

    def _is_provider_healthy(self, provider_name: str) -> bool:
        if self.circuit_breaker.get(provider_name, {}).get("status") == "healthy": return True
        last_failure = self.circuit_breaker.get(provider_name, {}).get("last_failure")
        if last_failure and (datetime.now() - last_failure).total_seconds() > 60:
            self.circuit_breaker[provider_name]["status"] = "healthy"; return True
        return False

    def _mark_provider_failure(self, provider_name: str):
        self.circuit_breaker[provider_name] = {"status": "unhealthy", "last_failure": datetime.now()}

    async def get_fixtures(self, league_id: int, season: int, from_date: str, to_date: str) -> List[Dict]:
        for provider in self.providers:
            provider_name = provider.__class__.__name__
            if not self._is_provider_healthy(provider_name): continue
            
            fixtures = await provider.get_fixtures(league_id, season, from_date, to_date)
            if fixtures: return fixtures
            else: self._mark_provider_failure(provider_name)
        return []

    async def get_matches_by_date(self, date_from: str, date_to: str = None) -> Dict:
        if not date_to: date_to = date_from
        for provider in self.providers:
            provider_name = provider.__class__.__name__
            if not self._is_provider_healthy(provider_name): continue
            matches = await provider.get_matches(date_from, date_to)
            if matches: return {"response": matches}
            self._mark_provider_failure(provider_name)
        return {"response": []}

    async def _make_request(self, endpoint: str, params: Dict = None) -> Dict:
        for provider in self.providers:
            provider_name = provider.__class__.__name__
            if not self._is_provider_healthy(provider_name): continue
            
            if isinstance(provider, (RapidAPIProvider, ThreeSixFiveScoresProvider)):
                url = f"https://{provider.host}/{endpoint}"
                try:
                    async with httpx.AsyncClient(timeout=25.0) as client:
                        res = await client.get(url, headers=provider.headers, params=params)
                        if res.status_code == 200: return res.json()
                        else: self._mark_provider_failure(provider_name)
                except: self._mark_provider_failure(provider_name)
        return {}

    async def get_match_deep_stats(self, match_id: str) -> Dict[str, Any]:
        if self.stats_provider:
            return await self.stats_provider.get_match_deep_stats(match_id)
        return {"error": "Stats provider not configured"}

    async def get_match_player_stats(self, match_id: str) -> Dict[str, Any]:
        if self.stats_provider:
            return await self.stats_provider.get_match_player_stats(match_id)
        return {"error": "Stats provider not configured"}

    async def get_match_shotmap(self, match_id: str) -> Dict[str, Any]:
        if self.stats_provider:
            return await self.stats_provider.get_match_shotmap(match_id)
        return {"error": "Stats provider not configured"}

    async def get_match_player_odds(self, match_id: str) -> Dict[str, Any]:
        if self.stats_provider:
            return await self.stats_provider.get_match_player_odds(match_id)
        return {"error": "Stats provider not configured"}

    async def search_teams(self, query: str) -> Dict:
        for provider in self.providers:
            if isinstance(provider, RapidAPIProvider):
                provider_name = provider.__class__.__name__
                if not self._is_provider_healthy(provider_name): continue
                
                url = f"https://{provider.host}/football-teams-search"
                try:
                    async with httpx.AsyncClient(timeout=10.0) as client:
                        res = await client.get(url, headers=provider.headers, params={"search": query})
                        if res.status_code == 200:
                            data = res.json()
                            teams = []
                            for item in data.get('response', {}).get('suggestions', []):
                                if item.get('type') == 'team':
                                    teams.append({"team": {"id": item.get('id'), "name": item.get('name'), "logo": f"https://images.fotmob.com/image_resources/logo/teamlogo/{item.get('id')}.png"}})
                            return {"response": teams}
                        else: self._mark_provider_failure(provider_name)
                except: self._mark_provider_failure(provider_name)
        return {"response": []}

    async def get_odds_by_event_id(self, event_id: str):
        for provider in self.providers:
            if isinstance(provider, RapidAPIProvider):
                provider_name = provider.__class__.__name__
                if not self._is_provider_healthy(provider_name): continue
                
                url = f"https://{provider.host}/football-get-odds-poll-match-events"
                try:
                    async with httpx.AsyncClient(timeout=10.0) as client:
                        res = await client.get(url, headers=provider.headers, params={"eventid": event_id})
                        if res.status_code == 200: return res.json()
                        else: self._mark_provider_failure(provider_name)
                except: self._mark_provider_failure(provider_name)
        return {"response": []}

    async def get_standings(self, league_id: str):
        for provider in self.providers:
            if isinstance(provider, RapidAPIProvider):
                provider_name = provider.__class__.__name__
                if not self._is_provider_healthy(provider_name): continue
                
                url = f"https://{provider.host}/football-get-standing-all"
                try:
                    async with httpx.AsyncClient(timeout=10.0) as client:
                        res = await client.get(url, headers=provider.headers, params={"leagueid": league_id})
                        if res.status_code == 200: return res.json()
                        else: self._mark_provider_failure(provider_name)
                except: self._mark_provider_failure(provider_name)
        return {"response": []}

    def get_365scores_match_url(self, home_team: str, away_team: str) -> str:
        query = f"{home_team} vs {away_team}"
        encoded_query = query.replace(" ", "%20")
        return f"https://www.365scores.com/football/search?query={encoded_query}"

    async def list_leagues(self):
        for provider in self.providers:
            if isinstance(provider, RapidAPIProvider):
                provider_name = provider.__class__.__name__
                if not self._is_provider_healthy(provider_name): continue
                
                url = f"https://{provider.host}/football-popular-leagues"
                try:
                    async with httpx.AsyncClient(timeout=10.0) as client:
                        res = await client.get(url, headers=provider.headers)
                        if res.status_code == 200:
                            data = res.json()
                            leagues = []
                            for l in data.get('response', {}).get('popular', []):
                                leagues.append({"league": {"id": l.get('id'), "name": l.get('name'), "logo": l.get('logo')}})
                            return {"response": leagues}
                        else: self._mark_provider_failure(provider_name)
                except: self._mark_provider_failure(provider_name)
        return {"response": []}

    async def get_teams_by_league(self, league_id: int):
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
                         "country": "Unknown"
                     },
                     "league": {"name": league_name}
                 })
        return {"response": teams}

    async def get_team_fixtures(self, team_id: int, last: int = 40):
        res = await self._make_request("football-get-team-fixtures", {"teamid": team_id, "last": last})
        return res if res else {"response": []}

    async def search_players(self, query: str):
        res = await self._make_request("football-players-search", {"search": query})
        return res if res else {"response": []}

    async def get_team_detail(self, team_id: int):
        res = await self._make_request("football-get-team-detail", {"teamid": team_id})
        return res if res else {"response": {}}

    async def get_league_detail(self, league_id: int):
        res = await self._make_request("football-get-league-detail", {"leagueid": league_id})
        return res if res else {"response": {}}

    async def search_leagues(self, query: str):
        res = await self._make_request("football-leagues-search", {"search": query})
        return res if res else {"response": []}

    async def get_stats_by_event_id(self, event_id: int):
        res = await self._make_request("football-get-stats", {"eventid": event_id})
        return res if res else {"response": []}

    async def get_h2h(self, team1_id: int, team2_id: int):
        res = await self._make_request("football-get-head-to-head", {"team1id": team1_id, "team2id": team2_id})
        return res if res else {"response": []}

    async def list_players_by_team(self, team_id: int):
        res = await self._make_request("football-get-team-players", {"teamid": team_id})
        return res if res else {"response": []}

    async def get_player_detail(self, player_id: int):
        res = await self._make_request("football-get-player-detail", {"playerid": player_id})
        return res if res else {"response": {}}
