import os
import requests

class FootballAPIClient:
    def __init__(self, api_key: str = None):
        self.api_key = api_key or os.environ.get('RAPIDAPI_KEY')
        self.rapidapi_host = os.environ.get('RAPIDAPI_HOST', 'free-api-live-football-data.p.rapidapi.com')
        self.base_url = f"https://{self.rapidapi_host}"
        self.headers = {
            'x-rapidapi-key': self.api_key,
            'x-rapidapi-host': self.rapidapi_host
        }

    def _make_request(self, endpoint, params=None):
        if not self.api_key:
            raise ValueError("RapidAPI key not configured.")
        try:
            response = requests.get(f"{self.base_url}/{endpoint}", headers=self.headers, params=params)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            # You might want to log the error here
            return {"error": str(e)}

    def search_teams(self, query: str):
        res = self._make_request("teams", params={"search": query})
        if (res.get('error') or not res.get('response')) and "v3" not in self.base_url:
            # Try with v3 prefix if base request failed
            res = self._make_request("v3/teams", params={"search": query})
        return res

    def get_team_detail(self, team_id: int):
        return self._make_request(f"teams", params={"id": team_id})

    def list_leagues(self):
        return self._make_request("leagues")

    def get_league_detail(self, league_id: int):
        return self._make_request(f"leagues", params={"id": league_id})

    def search_leagues(self, query: str):
        return self._make_request("leagues", params={"search": query})

    def get_matches_by_date(self, date: str):
        return self._make_request("fixtures", params={"date": date})

    def get_odds_by_event_id(self, event_id: int):
        return self._make_request("odds", params={"fixture": event_id})

    def get_stats_by_event_id(self, event_id: int):
        return self._make_request(f"fixtures/statistics", params={"fixture": event_id})

    def get_h2h(self, team1_id: int, team2_id: int):
        # The h2h parameter format is 'ID-ID'
        h2h_str = f"{team1_id}-{team2_id}"
        return self._make_request("fixtures/headtohead", params={"h2h": h2h_str})

    def get_standings(self, league_id: int):
        # Requires a season parameter, let's assume current year
        from datetime import datetime
        season = datetime.now().year - 1
        return self._make_request("standings", params={"league": league_id, "season": season})

    def list_players_by_team(self, team_id: int):
        # Requires a season parameter
        from datetime import datetime
        season = datetime.now().year - 1
        return self._make_request("players", params={"team": team_id, "season": season})

    def get_player_detail(self, player_id: int):
        from datetime import datetime
        season = datetime.now().year - 1
        return self._make_request("players", params={"id": player_id, "season": season})
        
    def search_players(self, query: str):
        # Searching players often works better without a season or with current season
        from datetime import datetime
        season = datetime.now().year
        res = self._make_request("players", params={"search": query, "season": season})
        if (not res.get('response') or len(res['response']) == 0) and "v3" not in self.base_url:
             res = self._make_request("v3/players", params={"search": query, "season": season})

        if not res.get('response') or len(res['response']) == 0:
            # Try previous season if current returns nothing
            res = self._make_request("players", params={"search": query, "season": season - 1})
        return res
