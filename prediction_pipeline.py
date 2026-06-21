import os
import hashlib
import numpy as np
import pandas as pd
import soccerdata as sd
from datetime import datetime, timezone
from scipy.stats import poisson
from supabase import create_client, Client
import logging

# Initialize Environment Elements
SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_SERVICE_KEY") or os.environ.get("SUPABASE_KEY")
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# Active international and domestic target registry matrix
LEAGUES = [
    "ENG-Premier League", "ESP-La Liga", "GER-Bundesliga", "ITA-Serie A",
    "FRA-Ligue 1", "INT-World Cup", "INT-Euro"
]
CURRENT_SEASON = "2425"

def generate_deterministic_id(name: str) -> int:
    hash_obj = hashlib.sha256(name.encode('utf-8'))
    return int(hash_obj.hexdigest()[:12], 16)

def run_pipeline():
    print("🚀 Initiating Multi-Market Analytics Optimization Pipeline...")
    render_cache = os.path.join("/tmp", "soccerdata_cache")

    for league in LEAGUES:
        try:
            print(f"📦 Extracting fixture arrays for: {league}")
            fbref = sd.FBref(leagues=league, seasons=CURRENT_SEASON, data_dir=render_cache)
            schedule = fbref.read_schedule()

            if schedule is None or schedule.empty:
                continue

            schedule = schedule.reset_index()
            schedule['match_date'] = pd.to_datetime(schedule['date'])

            for _, row in schedule.iterrows():
                h_name, a_name = row['home_team'], row['away_team']
                h_id = str(generate_deterministic_id(h_name))
                a_id = str(generate_deterministic_id(a_name))

                # Auto-Seed teams tables dynamically to resolve 404 dependencies
                supabase.table("teams").upsert({"id": h_id, "name": h_name, "league_name": league}).execute()
                supabase.table("teams").upsert({"id": a_id, "name": a_name, "league_name": league}).execute()

                match_payload = {
                    "home_team_id": h_id, "away_team_id": a_id, "match_date": row['match_date'].isoformat(),
                    "league": league, "season": CURRENT_SEASON,
                    "home_goals": int(row['home_score']) if pd.notna(row['home_score']) else None,
                    "away_goals": int(row['away_score']) if pd.notna(row['away_score']) else None,
                }
                match_res = supabase.table("matches").upsert(match_payload, on_conflict="home_team_id,away_team_id,match_date").execute()

                if pd.isna(row['home_score']) and match_res.data:
                    db_match_id = match_res.data[0]['id']

                    # Core expected values solver proxies
                    mu_h, mu_a = 1.55, 1.20
                    max_g = 10
                    grid = np.outer(poisson.pmf(range(max_g), mu_h), poisson.pmf(range(max_g), mu_a))

                    # MARKET 1: 3-Way Match Winner (Home, Draw, Away)
                    p_home = float(np.sum(np.tril(grid, -1)))
                    p_draw = float(np.sum(np.diag(grid)))
                    p_away = float(np.sum(np.triu(grid, 1)))

                    # MARKET 2: Over/Under 2.5 Goals
                    p_under_25 = float(np.sum([grid[i, j] for i in range(max_g) for j in range(max_g) if i + j < 2.5]))
                    p_over_25 = 1.0 - p_under_25

                    # MARKET 3: Both Teams to Score (BTTS Yes)
                    p_btts_yes = float(np.sum(grid[1:, 1:]))

                    # Determine which market holds the strongest mathematical edge
                    best_market = "3-Way Result"
                    best_selection = "Home Win"
                    best_prob = p_home

                    if p_over_25 > best_prob and p_over_25 > 0.60:
                        best_market = "Over/Under 2.5"
                        best_selection = "Over 2.5 Goals"
                        best_prob = p_over_25
                    elif p_btts_yes > best_prob and p_btts_yes > 0.65:
                        best_market = "Both Teams to Score"
                        best_selection = "BTTS - Yes"
                        best_prob = p_btts_yes

                    # Insert full multi-market probability payload array rows into Supabase
                    supabase.table("predictions").insert({
                        "match_id": db_match_id,
                        "home_team": h_name,
                        "away_team": a_name,
                        "home_prob": p_home,
                        "draw_prob": p_draw,
                        "away_prob": p_away,
                        "home_xg": mu_h,
                        "away_xg": mu_a,
                        "confidence": best_prob,
                        "best_bet_market": best_market,
                        "best_bet_selection": best_selection,
                        "best_bet_odds": 1.95,
                        "created_at": datetime.now(timezone.utc).isoformat()
                    }).execute()

        except Exception as e:
            print(f"⚠️ League sync interruption loop warning ({league}): {str(e)}")
            continue

    print("✅ All Multiple Betting Markets Processed and Synced!")

if __name__ == "__main__":
    run_pipeline()
