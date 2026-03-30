import os
import requests
from datetime import datetime

class FootballAPIClient:
    def __init__(self, api_key: str = None):
        self.api_key = api_key or os.environ.get('RAPIDAPI_KEY')
        self.host = "api-football-v1.p.rapidapi.com" 
        self.base_url = f"https://{self.host}/v3"
        self.headers = {
            'x-rapidapi-key': self.api_key,
            'x-rapidapi-host': self.host
        }

    def _make_request(self, endpoint, params=None):
        if not self.api_key:
            return {"error": "RapidAPI key not configured."}
        try:
            response = requests.get(f"{self.base_url}/{endpoint}", headers=self.headers, params=params)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            return {"error": str(e), "status_code": e.response.status_code if e.response else 500}

    def search_teams(self, query: str):
        res = self._make_request("teams", params={"search": query})
        if (res.get('error') or not res.get('response')) and "v3" not in self.base_url:
            res = self._make_request("v3/teams", params={"search": query})
        return res

    def get_team_detail(self, team_id: int):
        return self._make_request("teams", params={"id": team_id})

    def list_leagues(self):
        return self._make_request("leagues", params={"type": "league", "season": str(datetime.now().year -1)})

    def get_league_detail(self, league_id: int):
        return self._make_request("leagues", params={"id": league_id})
        
    def get_teams_by_league(self, league_id: int):
        """
        Fetches all teams for a specific league and the current season.
        This is a new method required for the team sync feature.
        """
        season = datetime.now().year
        return self._make_request("teams", params={"league": str(league_id), "season": str(season)})

    def search_leagues(self, query: str):
        return self._make_request("leagues", params={"search": query, "name": query})

    def get_matches_by_date(self, date: str):
        return self._make_request("fixtures", params={"date": date})

    def get_odds_by_event_id(self, event_id: int):
        return self._make_request("odds", params={"fixture": event_id})

    def get_stats_by_event_id(self, event_id: int):
        return self._make_request("fixtures/statistics", params={"fixture": event_id})

    def get_h2h(self, team1_id: int, team2_id: int):
        h2h_str = f"{team1_id}-{team2_id}"
        return self._make_request("fixtures/headtohead", params={"h2h": h2h_str})

    def get_standings(self, league_id: int):
        season = datetime.now().year
        return self._make_request("standings", params={"league": str(league_id), "season": str(season)})

    def list_players_by_team(self, team_id: int):
        season = datetime.now().year
        return self._make_request("players", params={"team": str(team_id), "season": str(season)})

    def get_player_detail(self, player_id: int):
        season = datetime.now().year
        return self._make_request("players", params={"id": str(player_id), "season": str(season)})
        
    def search_players(self, query: str):
        season = datetime.now().year
        res = self._make_request("players", params={"search": query, "season": str(season)})
        if not res.get('response') or len(res['response']) == 0:
            res = self._make_request("players", params={"search": query, "season": str(season - 1)})
        return res
