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
        if "free-api-live-football-data" in self.rapidapi_host:
            # Try multiple common endpoint names for searching teams
            for ep in ["football-get-teams-by-name", "football-get-teams-by-league", "get-teams"]:
                res = self._make_request(ep, params={"name": query, "search": query, "league": query})
                if res.get('response'): return res
            return self._make_request("football-get-teams-by-name", params={"name": query})

        res = self._make_request("teams", params={"search": query})
        if (res.get('error') or not res.get('response')) and "v3" not in self.base_url:
            res = self._make_request("v3/teams", params={"search": query})
        return res

    def get_team_detail(self, team_id: int):
        endpoint = "football-get-team-info" if "free-api-live-football-data" in self.rapidapi_host else "teams"
        return self._make_request(endpoint, params={"id": team_id, "team_id": team_id})

    def list_leagues(self):
        endpoint = "football-get-all-leagues" if "free-api-live-football-data" in self.rapidapi_host else "leagues"
        return self._make_request(endpoint)

    def get_league_detail(self, league_id: int):
        endpoint = "football-get-league-info" if "free-api-live-football-data" in self.rapidapi_host else "leagues"
        return self._make_request(endpoint, params={"id": league_id, "league_id": league_id})

    def search_leagues(self, query: str):
        endpoint = "football-get-all-leagues" if "free-api-live-football-data" in self.rapidapi_host else "leagues"
        return self._make_request(endpoint, params={"search": query, "name": query})

    def get_matches_by_date(self, date: str):
        if "free-api-live-football-data" in self.rapidapi_host:
            # Try both 'match_date' and 'date' parameters
            return self._make_request("football-get-matches-by-date", params={"match_date": date, "date": date})
        return self._make_request("fixtures", params={"date": date})

    def get_odds_by_event_id(self, event_id: int):
        endpoint = "football-get-odds-by-match" if "free-api-live-football-data" in self.rapidapi_host else "odds"
        return self._make_request(endpoint, params={"fixture": event_id, "match_id": event_id})

    def get_stats_by_event_id(self, event_id: int):
        endpoint = "football-get-stats-by-match" if "free-api-live-football-data" in self.rapidapi_host else "fixtures/statistics"
        return self._make_request(endpoint, params={"fixture": event_id, "match_id": event_id})

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
        if "free-api-live-football-data" in self.rapidapi_host:
            return self._make_request("football-get-players-by-team", params={"search": query})

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
