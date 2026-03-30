import os
import requests
from datetime import datetime

class FootballAPIClient:
    def __init__(self, api_key: str = None):
        self.api_key = api_key or os.environ.get('RAPIDAPI_KEY')
<<<<<<< HEAD
        # One of the PR descriptions mentions 'free-api-live-football-data', but all other indicators point to 'api-football-v1'
        self.host = "api-football-v1.p.rapidapi.com" 
        self.base_url = f"https://{self.host}/v3"
        self.headers = {
            'x-rapidapi-key': self.api_key,
            'x-rapidapi-host': self.host
=======
        self.rapidapi_host = os.environ.get('RAPIDAPI_HOST', 'free-api-live-football-data.p.rapidapi.com')
        self.base_url = f"https://{self.rapidapi_host}"
        self.headers = {
            'x-rapidapi-key': self.api_key,
            'x-rapidapi-host': self.rapidapi_host
>>>>>>> df9570acc20caae45bcf56a4de34681b26d1bc6c
        }

    def _make_request(self, endpoint, params=None):
        if not self.api_key:
            # In a real app, you might have a fallback to a free tier or cached data
            return {"error": "RapidAPI key not configured."}
        try:
            response = requests.get(f"{self.base_url}/{endpoint}", headers=self.headers, params=params)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            # You might want to log the error here
            return {"error": str(e), "status_code": e.response.status_code if e.response else 500}

    def search_teams(self, query: str):
        res = self._make_request("teams", params={"search": query})
        if (res.get('error') or not res.get('response')) and "v3" not in self.base_url:
            # Try with v3 prefix if base request failed
            res = self._make_request("v3/teams", params={"search": query})
        return res

    def get_team_detail(self, team_id: int):
<<<<<<< HEAD
        return self._make_request("teams", params={"id": team_id})

    def list_leagues(self):
        # We only want top-tier leagues for quality data
        return self._make_request("leagues", params={"type": "league", "season": str(datetime.now().year -1)})

    def get_league_detail(self, league_id: int):
        return self._make_request("leagues", params={"id": league_id})
        
    def get_teams_by_league(self, league_id: int):
        """
        Fetches all teams for a specific league and the current season.
        This is a new method required for the team sync feature.
        """
        season = datetime.now().year
        # The API might need the previous season depending on when in the year this is run
        return self._make_request("teams", params={"league": str(league_id), "season": str(season)})

=======
        endpoint = "football-get-team-info" if "free-api-live-football-data" in self.rapidapi_host else "teams"
        return self._make_request(endpoint, params={"id": team_id, "team_id": team_id})

    def list_leagues(self):
        endpoint = "football-get-all-leagues" if "free-api-live-football-data" in self.rapidapi_host else "leagues"
        return self._make_request(endpoint)

    def get_league_detail(self, league_id: int):
        endpoint = "football-get-league-info" if "free-api-live-football-data" in self.rapidapi_host else "leagues"
        return self._make_request(endpoint, params={"id": league_id, "league_id": league_id})
>>>>>>> df9570acc20caae45bcf56a4de34681b26d1bc6c

    def search_leagues(self, query: str):
        endpoint = "football-get-all-leagues" if "free-api-live-football-data" in self.rapidapi_host else "leagues"
        return self._make_request(endpoint, params={"search": query, "name": query})

    def get_matches_by_date(self, date: str):
<<<<<<< HEAD
        # The API expects YYYY-MM-DD format
        return self._make_request("fixtures", params={"date": date})

    def get_odds_by_event_id(self, event_id: int):
        # The API refers to matches/events as 'fixtures'
        return self._make_request("odds", params={"fixture": event_id})

    def get_stats_by_event_id(self, event_id: int):
        return self._make_request("fixtures/statistics", params={"fixture": event_id})
=======
        if "free-api-live-football-data" in self.rapidapi_host:
            # Try multiple common endpoint names and parameter combinations
            for ep in ["football-get-matches-by-date", "get-matches-by-date", "fixtures"]:
                res = self._make_request(ep, params={"match_date": date, "date": date})
                if res.get('response'): return res
            return self._make_request("football-get-matches-by-date", params={"match_date": date})
        return self._make_request("fixtures", params={"date": date})

    def get_odds_by_event_id(self, event_id: int):
        endpoint = "football-get-odds-by-match" if "free-api-live-football-data" in self.rapidapi_host else "odds"
        return self._make_request(endpoint, params={"fixture": event_id, "match_id": event_id})

    def get_stats_by_event_id(self, event_id: int):
        endpoint = "football-get-stats-by-match" if "free-api-live-football-data" in self.rapidapi_host else "fixtures/statistics"
        return self._make_request(endpoint, params={"fixture": event_id, "match_id": event_id})
>>>>>>> df9570acc20caae45bcf56a4de34681b26d1bc6c

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
<<<<<<< HEAD
        season = datetime.now().year
        return self._make_request("players", params={"search": query, "season": str(season)})
=======
        # Searching players often works better without a season or with current season
        from datetime import datetime
        season = datetime.now().year
        res = self._make_request("players", params={"search": query, "season": season})
        if not res.get('response') or len(res['response']) == 0:
            # Try previous season if current returns nothing
            res = self._make_request("players", params={"search": query, "season": season - 1})
        return res
>>>>>>> df9570acc20caae45bcf56a4de34681b26d1bc6c
