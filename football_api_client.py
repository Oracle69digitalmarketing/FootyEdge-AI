import os
import httpx
import asyncio
import logging
from datetime import datetime
from typing import Dict, List, Any, Optional

logger = logging.getLogger(__name__)

class BaseFootballProvider:
    def __init__(self, api_key: str = None):
        self.api_key = api_key
        self.headers = {}

    async def get_matches(self, date_from: str, date_to: str) -> List[Dict]:
        raise NotImplementedError

    def normalize_match(self, match: Dict) -> Dict:
        return match

class OddsAPIProvider(BaseFootballProvider):
    """
    Implementation for The-Odds-API (the-odds-api.com)
    """
    def __init__(self, api_key: str):
        super().__init__(api_key)
        self.base_url = "https://api.the-odds-api.com/v4/sports"
        self.sport = "soccer_epl" # Default to EPL, can be dynamic

    async def get_matches(self, date_from: str, date_to: str) -> List[Dict]:
        """
        Fetches odds (which include match info) from The-Odds-API.
        """
        if not self.api_key:
            return []
        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                res = await client.get(
                    f"{self.base_url}/{self.sport}/odds",
                    params={
                        "apiKey": self.api_key,
                        "regions": "uk",
                        "markets": "h2h,totals",
                        "oddsFormat": "decimal"
                    }
                )
                if res.status_code == 200:
                    data = res.json()
                    return [self.normalize_match(m) for m in data]
                else:
                    logger.error(f"Odds-API error: {res.status_code} - {res.text}")
                    return []
        except Exception as e:
            logger.error(f"Odds-API exception: {e}")
            return []

    def normalize_match(self, m: Dict) -> Dict:
        # Map The-Odds-API format to our internal format
        home_team = m.get('home_team')
        away_team = m.get('away_team')

        # Extract odds if available
        odds = {}
        for bookmaker in m.get('bookmakers', []):
            if bookmaker['key'] in ['williamhill', 'betfair_ex_uk', 'unibet_uk', 'bet365']:
                for market in bookmaker.get('markets', []):
                    if market['key'] == 'h2h':
                        for outcome in market.get('outcomes', []):
                            if outcome['name'] == home_team: odds['home_win'] = outcome['price']
                            elif outcome['name'] == away_team: odds['away_win'] = outcome['price']
                            else: odds['draw'] = outcome['price']
                    elif market['key'] == 'totals':
                        for outcome in market.get('outcomes', []):
                            if outcome['name'] == 'Over' and outcome['point'] == 2.5:
                                odds['Over 2.5'] = outcome['price']
                            elif outcome['name'] == 'Under' and outcome['point'] == 2.5:
                                odds['Under 2.5'] = outcome['price']
                if odds.get('home_win'): break # Take first found reliable bookmaker with at least H2H

        return {
            "fixture": {
                "id": m.get('id'),
                "date": m.get('commence_time')
            },
            "teams": {
                "home": {"name": home_team, "id": None, "logo": None},
                "away": {"name": away_team, "id": None, "logo": None}
            },
            "league": {"name": m.get('sport_title'), "id": m.get('sport_key')},
            "goals": {"home": None, "away": None},
            "status": {"long": "Upcoming"},
            "live_odds": odds
        }

class FootballAPIClient:
    def __init__(self):
        self.api_key = os.environ.get('ODDS_API_KEY')
        self.provider = OddsAPIProvider(self.api_key) if self.api_key else None
        
        if not self.api_key:
            logger.warning("ODDS_API_KEY not found. API calls will fail.")

    async def get_matches_by_date(self, date_from: str, date_to: str = None) -> Dict:
        if not self.provider: return {"response": []}
        matches = await self.provider.get_matches(date_from, date_to)
        return {"response": matches}

    async def get_team_fixtures(self, team_id: str, last: int = 40) -> Dict:
        return {"response": []}

    async def list_leagues(self):
        if not self.provider: return {"response": []}
        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                res = await client.get(
                    f"{self.provider.base_url}",
                    params={"apiKey": self.api_key}
                )
                if res.status_code == 200:
                    data = res.json()
                    leagues = []
                    for s in data:
                        if s.get('group') == 'Soccer':
                            leagues.append({"league": {"id": s.get('key'), "name": s.get('title')}})
                    return {"response": leagues}
                return {"response": []}
        except Exception:
            return {"response": []}

    async def search_teams(self, query: str) -> Dict:
        return {"response": []}

    async def get_odds_by_event_id(self, event_id: str) -> Dict:
        return {}

    async def get_stats_by_event_id(self, event_id: str) -> Dict:
        return {"response": []}
