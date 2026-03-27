import os
import requests

class FootballAPIClient:
    def __init__(self, api_key: str = None):
        self.api_key = api_key or os.environ.get('RAPIDAPI_KEY')
        self.base_url = "https://free-api-live-football-data.p.rapidapi.com"
        self.headers = {
            'x-rapidapi-key': self.api_key,
            'x-rapidapi-host': 'free-api-live-football-data.p.rapidapi.com'
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
        return self._make_request("search-teams", params={"q": query})

    def get_team_detail(self, team_id: int):
        return self._make_request(f"team-detail-by-team-id/{team_id}")

    def list_leagues(self):
        return self._make_request("leagues-list-all")

    def get_league_detail(self, league_id: int):
        return self._make_request(f"league-detail-by-league-id/{league_id}")

    def search_leagues(self, query: str):
        return self._make_request("search-leagues", params={"q": query})

    def get_matches_by_date(self, date: str):
        return self._make_request("matches-events-by-date", params={"date": date})

    def get_odds_by_event_id(self, event_id: int):
        return self._make_request(f"odds-match-events-by-event-id/{event_id}")

    def get_stats_by_event_id(self, event_id: int):
        return self._make_request(f"statistics-event-by-event-id/{event_id}")

    def get_h2h(self, team1_id: int, team2_id: int):
        return self._make_request("head-to-head-by-teams", params={"team1_id": team1_id, "team2_id": team2_id})

    def get_standings(self, league_id: int):
        return self._make_request(f"standings-by-league-id/{league_id}")

    def list_players_by_team(self, team_id: int):
        return self._make_request(f"players-list-all-by-team-id/{team_id}")

    def get_player_detail(self, player_id: int):
        return self._make_request(f"player-detail-by-player-id/{player_id}")
