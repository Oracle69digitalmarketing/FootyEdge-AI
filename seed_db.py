import os
from dotenv import load_dotenv
from supabase import create_client, Client
from datetime import datetime, timedelta, timezone

# Load environment variables
load_dotenv()

# Initialize Supabase Client
SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_SERVICE_KEY") or os.environ.get("SUPABASE_KEY")
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

def seed_database():
    print("🚀 Seeding database with dummy data...")
    
    # 0. Seed dummy teams first
    teams = [
        {"id": "1", "name": "Team A", "league_name": "Test League"},
        {"id": "2", "name": "Team B", "league_name": "Test League"},
        {"id": "3", "name": "Team C", "league_name": "Test League"},
        {"id": "4", "name": "Team D", "league_name": "Test League"},
        {"id": "5", "name": "Team E", "league_name": "Test League"},
        {"id": "6", "name": "Team F", "league_name": "Test League"},
    ]
    for t in teams:
        supabase.table("teams").upsert(t).execute()

    # 1. Seed some dummy matches
    matches = [
        {"home_team_id": "1", "away_team_id": "2", "home_goals": 2, "away_goals": 1, "match_date": (datetime.now(timezone.utc) - timedelta(days=1)).isoformat()},
        {"home_team_id": "3", "away_team_id": "4", "home_goals": 0, "away_goals": 0, "match_date": (datetime.now(timezone.utc) - timedelta(days=2)).isoformat()},
        {"home_team_id": "5", "away_team_id": "6", "home_goals": 1, "away_goals": 3, "match_date": (datetime.now(timezone.utc) - timedelta(days=3)).isoformat()},
    ]
    
    match_ids = []
    for m in matches:
        res = supabase.table("matches").insert(m).execute()
        if res.data:
            match_ids.append(res.data[0]['id'])
    
    # 2. Seed corresponding predictions
    predictions = [
        {"match_id": match_ids[0], "home_team": "Team A", "away_team": "Team B", "best_bet_selection": "Home Win", "best_bet_odds": 1.95, "best_bet_market": "3-Way Result", "actual_result": "Home Win"},
        {"match_id": match_ids[1], "home_team": "Team C", "away_team": "Team D", "best_bet_selection": "Home Win", "best_bet_odds": 2.10, "best_bet_market": "3-Way Result", "actual_result": "Draw"},
        {"match_id": match_ids[2], "home_team": "Team E", "away_team": "Team F", "best_bet_selection": "Away Win", "best_bet_odds": 1.85, "best_bet_market": "3-Way Result", "actual_result": "Away Win"},
    ]
    
    for p in predictions:
        supabase.table("predictions").insert(p).execute()
        
    print("✅ Seed completed!")

if __name__ == "__main__":
    seed_database()
