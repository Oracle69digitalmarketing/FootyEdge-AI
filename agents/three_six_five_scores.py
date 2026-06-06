import httpx
import logging
from typing import Dict, List, Any, Optional
from datetime import datetime

logger = logging.getLogger(__name__)

class ThreeSixFiveScoresClient:
    """
    Client for 365Scores Internal Web API.
    Provides advanced stats like xG and shot maps not available in standard free APIs.
    """
    def __init__(self):
        self.base_url = "https://webapi.365scores.com"
        self.headers = {
            "Referer": "https://www.365scores.com/",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept": "application/json"
        }

    async def _make_request(self, path: str, params: Dict = None):
        url = f"{self.base_url}{path}"
        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                res = await client.get(url, headers=self.headers, params=params)
                if res.status_code == 200:
                    return res.json()
                logger.warning(f"365Scores API {path} returned {res.status_code}")
                return None
        except Exception as e:
            logger.error(f"365Scores Request failed to {path}: {e}")
            return None

    async def search(self, query: str) -> Optional[Dict]:
        """Search for teams, leagues, or players to get their 365Scores IDs."""
        return await self._make_request("/web/search/", {"text": query, "lang": "1"})

    async def get_match_details(self, game_id: int) -> Optional[Dict]:
        """Get full match details including xG, stats, and incidents."""
        return await self._make_request("/content/v2/game/", {"gameId": game_id, "lang": "1"})

    async def get_team_fixtures(self, team_id: int) -> Optional[Dict]:
        """Get recent and upcoming fixtures for a team."""
        # Note: 365Scores often uses different paths for team content
        return await self._make_request(f"/content/v2/stats/competitor/", {
            "competitorId": team_id,
            "lang": "1",
            "withGameStats": "true"
        })

    def extract_xg(self, match_data: Dict) -> Dict[str, float]:
        """
        Extracts Expected Goals (xG) from match data.
        Returns {'home': float, 'away': float}
        """
        try:
            # 365Scores usually puts advanced stats in actualGameStatistics
            stats = match_data.get('actualGameStatistics', [])
            xg_data = next((s for s in stats if s.get('name') == 'Expected Goals (xG)'), None)
            
            if not xg_data:
                # Fallback: check the general stats in the game object
                game_stats = match_data.get('games', [{}])[0].get('stats', [])
                xg_data = next((s for s in game_stats if s.get('name') == 'Expected Goals (xG)'), None)

            if xg_data:
                return {
                    'home': float(xg_data.get('home', 0)),
                    'away': float(xg_data.get('away', 0))
                }
        except Exception as e:
            logger.error(f"Error extracting xG: {e}")
        
        return {'home': 0.0, 'away': 0.0}

    async def find_match_id(self, home_team: str, away_team: str) -> Optional[int]:
        """
        Finds the 365Scores Game ID for a specific matchup.
        """
        search_results = await self.search(f"{home_team} {away_team}")
        if not search_results or 'games' not in search_results:
            return None
        
        # Try to find a match where both team names are similar
        for game in search_results.get('games', []):
            game_home = ""
            game_away = ""
            
            # Map IDs to names from the competitors list in the response
            competitors = {c['id']: c['name'] for c in search_results.get('competitors', [])}
            game_home = competitors.get(game.get('homeCompetitorId'), "").lower()
            game_away = competitors.get(game.get('awayCompetitorId'), "").lower()
            
            if home_team.lower() in game_home or game_home in home_team.lower():
                if away_team.lower() in game_away or game_away in away_team.lower():
                    return game.get('id')
        
        return None
