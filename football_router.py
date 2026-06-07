import logging
from typing import Dict, List, Any, Optional
from football_api_client import FootballAPIClient
from football_data_org_client import FootballDataOrgClient
from sofascore_client import SofascoreClient
from agents.three_six_five_scores import ThreeSixFiveScoresClient

logger = logging.getLogger(__name__)

class FootballRouter:
    """
    Routes football data requests between football-data.org (Major Leagues),
    RapidAPI (Others), and Sofascore (Deep Stats/H2H).
    """
    def __init__(self, fd_client: FootballDataOrgClient, rapid_client: FootballAPIClient):
        self.fd_client = fd_client
        self.rapid_client = rapid_client
        self.sofascore = SofascoreClient()
        self.three_six_five = ThreeSixFiveScoresClient()
        
        # Leagues that football-data.org handles well on the free tier
        self.MAJOR_LEAGUE_CODES = ["PL", "PD", "BL1", "SA", "FL1", "CL", "EL", "DED", "PPL", "WC", "EC"]
        self.MAJOR_LEAGUE_IDS = [2021, 2014, 2002, 2019, 2015, 2001, 2003, 2017, 2013, 2016, 2000, 2018]

    def _get_client(self, league_id_or_code: Any) -> Any:
        """Determines which client to use based on the league."""
        if not self.fd_client:
            return self.rapid_client
        if not self.rapid_client:
            return self.fd_client
            
        # Check if it's a major league code or ID
        if str(league_id_or_code).upper() in self.MAJOR_LEAGUE_CODES or league_id_or_code in self.MAJOR_LEAGUE_IDS:
            return self.fd_client
            
        # Default to RapidAPI for everything else (Smaller leagues like Nigeria)
        return self.rapid_client

    async def get_matches_by_date(self, date_from: str, date_to: str = None, league_id: Any = None) -> Dict:
        """Fetches matches, routing to FD for major leagues if specified."""
        if league_id:
            client = self._get_client(league_id)
            return await client.get_matches_by_date(date_from, date_to)
        
        # If no specific league, we might want to combine or prefer one.
        # Usually, FD gives a better 'global' feed for majors, 
        # but RapidAPI has MORE leagues.
        if self.rapid_client:
            return await self.rapid_client.get_matches_by_date(date_from, date_to)
        return await self.fd_client.get_matches_by_date(date_from, date_to)

    async def get_standings(self, league_id: Any):
        client = self._get_client(league_id)
        return await client.get_standings(str(league_id))

    async def get_teams_by_league(self, league_id: Any):
        client = self._get_client(league_id)
        return await client.get_teams_by_league(league_id)

    async def list_leagues(self):
        # We might want to merge lists, but for now, RapidAPI has the most comprehensive list
        if self.rapid_client:
            return await self.rapid_client.list_leagues()
        return await self.fd_client.list_leagues()

    async def search_leagues(self, query: str):
        if self.rapid_client:
            return await self.rapid_client.search_leagues(query)
        return await self.fd_client.search_leagues(query)

    async def search_teams(self, query: str):
        if self.rapid_client:
            return await self.rapid_client.search_teams(query)
        return await self.fd_client.search_teams(query)

    async def search_players(self, query: str):
        if self.rapid_client:
            return await self.rapid_client.search_players(query)
        return await self.fd_client.search_players(query)

    async def get_team_fixtures(self, team_id: Any, last: int = 10):
        # This is tricky because team_ids differ. 
        # For now, we try both or rely on the primary client.
        if self.fd_client:
            res = await self.fd_client.get_team_fixtures(team_id, last)
            if res and res.get('response'):
                return res
        if self.rapid_client:
            return await self.rapid_client.get_team_fixtures(team_id, last)
        return {"response": []}

    def get_365scores_match_url(self, home_team: str, away_team: str) -> str:
        return self.three_six_five.get_365scores_match_url(home_team, away_team)
