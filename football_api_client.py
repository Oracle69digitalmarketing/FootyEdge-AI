import os
import requests

class FootballAPIClient:
    def __init__(self, api_key: str = None):
        self.api_key = api_key or os.environ.get('RAPIDAPI_KEY')
        self.base_url = "https://api-football-v1.p.rapidapi.com/v3"
        self.headers = {
            'x-rapidapi-key': self.api_key,
            'x-rapidapi-host': 'api-football-v1.p.rapidapi.com'
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
        return self._make_request("teams", params={"search": query})

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
        season = datetime.now().year
        return self._make_request("standings", params={"league": league_id, "season": season})

    def list_players_by_team(self, team_id: int):
        # Requires a season parameter
        from datetime import datetime
        season = datetime.now().year
        return self._make_request("players", params={"team": team_id, "season": season})

    def get_player_detail(self, player_id: int):
        from datetime import datetime
        season = datetime.now().year
        return self._make_request("players", params={"id": player_id, "season": season})
        
    def search_players(self, query: str):
        from datetime import datetime
        season = datetime.now().year
        return self._make_request("players", params={"search": query, "season": season})
