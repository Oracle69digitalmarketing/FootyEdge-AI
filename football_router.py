import logging
from typing import Dict, List, Any, Optional
from football_api_client import FootballAPIClient
from football_data_org_client import FootballDataOrgClient
from sofascore_client import SofascoreClient
from agents.three_six_five_scores import ThreeSixFiveScoresClient

logger = logging.getLogger(__name__)

class FootballRouter:
    """
    Orchestrates multiple football data providers, ensuring maximum availability.
    """
    def __init__(self, fd_client: FootballDataOrgClient = None, rapid_client: FootballAPIClient = None):
        self.fd_client = fd_client or FootballDataOrgClient()
        self.rapid_client = rapid_client or FootballAPIClient()
        self.sofascore = SofascoreClient()
        self.three_six_five = ThreeSixFiveScoresClient()

    async def get_matches_by_date(self, date_from: str, date_to: str = None, league_id: Any = None) -> Dict:
        """Fetches matches, aggregating from all available clients."""
        all_matches = []
        
        # Try standalone FD client first for speed and reliability for majors
        if self.fd_client:
            try:
                res = await self.fd_client.get_matches_by_date(date_from, date_to)
                if res and res.get('response'):
                    all_matches.extend(res['response'])
            except Exception as e:
                logger.error(f"Router: FD client failed: {e}")

        # Try RapidAPI aggregator
        if self.rapid_client:
            try:
                res = await self.rapid_client.get_matches_by_date(date_from, date_to)
                if res and res.get('response'):
                    all_matches.extend(res['response'])
            except Exception as e:
                logger.error(f"Router: Rapid client failed: {e}")

        # Deduplicate and prioritize major leagues
        unique_matches = {}
        # Major league IDs across providers
        MAJOR_LEAGUES = [47, 87, 54, 55, 53, 42, 73, 2021, 2014, 2019, 2015, 2002, 2001]
        
        for m in all_matches:
            # Create a unique key based on team names and date if ID is not reliable
            fid = m.get('fixture', {}).get('id')
            if not fid:
                h = m.get('teams', {}).get('home', {}).get('name', 'H')
                a = m.get('teams', {}).get('away', {}).get('name', 'A')
                d = m.get('fixture', {}).get('date', 'D')
                fid = f"{h}-{a}-{d}"

            if fid not in unique_matches:
                # Assign priority: 1 for major, 2 for others
                lid = m.get('league', {}).get('id')
                priority = 1 if lid in MAJOR_LEAGUES or any(kw in m.get('league', {}).get('name', '').lower() for kw in ['premier', 'la liga', 'bundesliga', 'serie a', 'champions league']) else 2
                m['priority'] = priority
                unique_matches[fid] = m

        sorted_matches = sorted(unique_matches.values(), key=lambda x: (x.get('priority', 2), x.get('fixture', {}).get('date', '')))
        return {"response": sorted_matches}
    async def get_standings(self, league_id: Any):
        # Prefer FD for major standings
        try:
            res = await self.fd_client.get_standings(str(league_id))
            if res and res.get('response'): return res
        except: pass
        return await self.rapid_client.get_standings(str(league_id))

    async def get_teams_by_league(self, league_id: Any):
        try:
            res = await self.fd_client.get_teams_by_league(str(league_id))
            if res and res.get('response'): return res
        except: pass
        return await self.rapid_client.get_teams_by_league(league_id)

    async def list_leagues(self):
        """Aggregates leagues from all clients."""
        all_leagues = []
        if self.fd_client:
            try:
                res = await self.fd_client.list_leagues()
                if res and res.get('response'):
                    all_leagues.extend(res['response'])
            except: pass
        if self.rapid_client:
            try:
                res = await self.rapid_client.list_leagues()
                if res and res.get('response'):
                    all_leagues.extend(res['response'])
            except: pass

        # Deduplicate by ID
        unique = {}
        for l in all_leagues:
            lid = l.get('league', {}).get('id')
            if lid and lid not in unique:
                unique[lid] = l
        return {"response": list(unique.values())}
    async def search_leagues(self, query: str):
        if self.rapid_client:
            return await self.rapid_client.search_leagues(query)
        return await self.fd_client.search_leagues(query)

    async def search_teams(self, query: str):
        return await self.rapid_client.search_teams(query)

    async def search_players(self, query: str):
        return await self.rapid_client.search_players(query)

    async def get_team_fixtures(self, team_id: Any, last: int = 10):
        # We try RapidAPI first as it has better coverage for team fixtures
        res = await self.rapid_client.get_team_fixtures(team_id, last)
        if res and res.get('response'): return res
        return await self.fd_client.get_team_fixtures(team_id, last)

    async def get_odds_by_event_id(self, event_id: Any):
        return await self.rapid_client.get_odds_by_event_id(event_id)

    async def get_stats_by_event_id(self, event_id: Any):
        return await self.rapid_client.get_stats_by_event_id(event_id)

    async def get_h2h(self, team1_id: Any, team2_id: Any):
        return await self.rapid_client.get_h2h(team1_id, team2_id)

    async def list_players_by_team(self, team_id: Any):
        return await self.rapid_client.list_players_by_team(team_id)

    async def get_player_detail(self, player_id: Any):
        return await self.rapid_client.get_player_detail(player_id)

    async def get_team_detail(self, team_id: Any):
        return await self.rapid_client.get_team_detail(team_id)

    async def get_league_detail(self, league_id: Any):
        return await self.rapid_client.get_league_detail(league_id)

    def get_365scores_match_url(self, home_team: str, away_team: str) -> str:
        return self.three_six_five.get_365scores_match_url(home_team, away_team)
