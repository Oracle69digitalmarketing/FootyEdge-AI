import os
import httpx
import logging
from typing import Dict, List, Any, Optional

logger = logging.getLogger(__name__)

class SofascoreClient:
    """
    Client for Sofascore API on RapidAPI (sofascore.p.rapidapi.com)
    Provides deep match stats, H2H, and player ratings.
    """
    def __init__(self):
        self.rapidapi_key = os.environ.get('RAPIDAPI_KEY') or os.environ.get('RAPID_API_KEY')
        self.rapid_host = "sofascore.p.rapidapi.com"
        self.headers = {
            'x-rapidapi-key': self.rapidapi_key,
            'x-rapidapi-host': self.rapid_host,
            'Content-Type': 'application/json'
        }
        self.base_url = f"https://{self.rapid_host}"

    async def _make_request(self, endpoint: str, params: Dict = None):
        url = f"{self.base_url}/{endpoint.lstrip('/')}"
        try:
            async with httpx.AsyncClient(timeout=20.0) as client:
                res = await client.get(url, headers=self.headers, params=params)
                if res.status_code == 200:
                    return res.json()
                logger.warning(f"Sofascore API at {url} returned {res.status_code}: {res.text}")
                return None
        except Exception as e:
            logger.error(f"Sofascore request failed to {url}: {e}")
            return None

    async def get_h2h_events(self, team1_id: int, team2_id: int):
        """
        Fetches head-to-head events between two teams.
        Note: Requires Sofascore team IDs.
        """
        return await self._make_request("matches/get-h2h-events", {
            "teamId1": team1_id,
            "teamId2": team2_id
        })

    async def get_match_details(self, match_id: int):
        """Fetches full details for a match."""
        return await self._make_request("matches/get-details", {"matchId": match_id})

    async def get_match_statistics(self, match_id: int):
        """Fetches detailed statistics for a match."""
        return await self._make_request("matches/get-statistics", {"matchId": match_id})

    async def get_match_lineups(self, match_id: int):
        """Fetches lineups and player ratings for a match."""
        return await self._make_request("matches/get-lineups", {"matchId": match_id})

    async def search_teams(self, query: str):
        """Search for teams to get Sofascore IDs."""
        return await self._make_request("teams/search", {"query": query})

    async def search_players(self, query: str):
        """Search for players to get Sofascore IDs."""
        return await self._make_request("players/search", {"query": query})
