import os
import hashlib
import numpy as np
import pandas as pd
import soccerdata as sd
import requests
from datetime import datetime
from scipy.optimize import minimize
from scipy.stats import poisson
from supabase import create_client, Client

# Initialize Environment Elements
SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY")
ODDS_API_KEY = os.environ.get("ODDS_API_KEY")
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

LEAGUES = [
    "ENG-Premier League", "ESP-La Liga", "GER-Bundesliga", "ITA-Serie A", 
    "FRA-Ligue 1", "NED-Eredivisie", "POR-Primeira Liga", "USA-Major League Soccer",
    "INT-World Cup", "INT-Champions League", "INT-Euro"
]
CURRENT_SEASON = "25-26" 

ODDS_API_LEAGUE_MAP = {
    "ENG-Premier League": "soccer_epl",
    "ESP-La Liga": "soccer_spain_la_liga",
    "GER-Bundesliga": "soccer_germany_bundesliga",
    "ITA-Serie A": "soccer_italy_serie_a",
    "FRA-Ligue 1": "soccer_france_ligue_one",
    "USA-Major League Soccer": "soccer_usa_mls",
    "INT-Champions League": "soccer_uefa_champs_league",
    "INT-World Cup": "soccer_fifa_world_cup"
}

def generate_deterministic_id(name: str) -> int:
    """Generates a consistent BIGINT ID from string tokens to avoid 404 conflicts."""
    hash_obj = hashlib.sha256(name.encode('utf-8'))
    return int(hash_obj.hexdigest()[:12], 16)

def fetch_live_odds(league_key: str):
    """Fetches real-time market data directly from The Odds API."""
    if not ODDS_API_KEY or not league_key:
        return {}
    url = f"https://the-odds-api.com/v4/sports/{league_key}/odds/"
    params = {"apiKey": ODDS_API_KEY, "regions": "uk,us", "markets": "h2h,totals", "oddsFormat": "decimal"}
    try:
        response = requests.get(url, params=params)
        if response.status_code == 200:
            return {f"{g['home_team']} vs {g['away_team']}": g for g in response.json()}
    except Exception:
        pass
    return {}

def solve_poisson_strengths(df_matches):
    """Calculates custom team performance strengths via maximum likelihood estimation."""
    df_clean = df_matches.dropna(subset=['home_score', 'away_score'])
    if len(df_clean) < 5:
        return {}
    
    teams = pd.concat([df_clean['home_team'], df_clean['away_team']]).unique()
    n_teams = len(teams)
    team_map = {team: i for i, team in enumerate(teams)}
    
    def loss_function(params):
        att = params[:n_teams]
        df = params[n_teams:2*n_teams]
        home_adv = params[-1]
        log_likelihood = 0
        for _, row in df_clean.iterrows():
            h_idx = team_map[row['home_team']]
            a_idx = team_map[row['away_team']]
            lambda_home = np.exp(att[h_idx] + df[a_idx] + home_adv)
            lambda_away = np.exp(att[a_idx] + df[h_idx])
            log_likelihood += poisson.logpmf(row['home_score'], lambda_home)
            log_likelihood += poisson.logpmf(row['away_score'], lambda_away)
        return -log_likelihood

    init_params = np.zeros(2 * n_teams + 1)
    res = minimize(loss_function, init_params, method='BFGS')
    
    if not res.success:
        return {}
    return {team: {"attack": float(np.exp(res.x[idx])), "defense": float(np.exp(res.x[n_teams + idx]))} for team, idx in team_map.items()}

def run_pipeline():
    print("⚽ Initiating Open Source Core Predictive Analytics Engine...")
    
    for league in LEAGUES:
        try:
            print(f"🔄 Executing loop sequence for league context: {league}")
            # Note: league mapping to soccerdata needs attention if not direct
            league_short = league.split('-')[1] if '-' in league else league
            render_tmp_cache = os.path.join("/tmp", "soccerdata_cache"); fbref = sd.FBref(leagues=league_short, seasons=CURRENT_SEASON, data_dir=render_tmp_cache)
            schedule = fbref.read_schedule().reset_index()
            if schedule.empty:
                continue
                
            schedule['match_date'] = pd.to_datetime(schedule['date'])
            team_strengths = solve_poisson_strengths(schedule)
            live_odds_book = fetch_live_odds(ODDS_API_LEAGUE_MAP.get(league))
            
            # Sync Teams Table Loop
            unique_teams = pd.concat([schedule['home_team'], schedule['away_team']]).unique()
            for team_name in unique_teams:
                ts = team_strengths.get(team_name, {"attack": 1.0, "defense": 1.0})
                supabase.table("teams").upsert({
                    "id": generate_deterministic_id(team_name), "name": team_name, "league_name": league,
                    "attack_strength": ts["attack"], "defense_strength": ts["defense"], "updated_at": datetime.utcnow().isoformat()
                }).execute()
            
            # Sync Matches & Process Calculations Loop
            for _, row in schedule.iterrows():
                h_id = generate_deterministic_id(row['home_team'])
                a_id = generate_deterministic_id(row['away_team'])
                
                match_payload = {
                    "home_team_id": h_id, "away_team_id": a_id, "match_date": row['match_date'].isoformat(),
                    "league": league, "season": CURRENT_SEASON,
                    "home_goals": int(row['home_score']) if pd.notna(row['home_score']) else None,
                    "away_goals": int(row['away_score']) if pd.notna(row['away_score']) else None,
                }
                match_res = supabase.table("matches").upsert(match_payload, on_conflict="home_team_id,away_team_id,match_date").execute()
                if not match_res.data:
                    continue
                db_match_id = match_res.data[0]['id'] # Access returning sequence index
                
                # Check for Upcoming Matches to Predict
                if pd.isna(row['home_score']) and team_strengths:
                    h_ts = team_strengths.get(row['home_team'], {"attack": 1.0, "defense": 1.0})
                    a_ts = team_strengths.get(row['away_team'], {"attack": 1.0, "defense": 1.0})
                    
                    mu_h = h_ts["attack"] * a_ts["defense"] * 1.12
                    mu_a = a_ts["attack"] * h_ts["defense"]
                    
                    max_g = 10
                    grid = np.outer(poisson.pmf(range(max_g), mu_h), poisson.pmf(range(max_g), mu_a))
                    
                    p_home = float(np.sum(np.tril(grid, -1)))
                    p_draw = float(np.sum(np.diag(grid)))
                    p_away = float(np.sum(np.triu(grid, 1)))
                    
                    # Store Model Output
                    pred_payload = {
                        "match_id": db_match_id, "home_team": row['home_team'], "away_team": row['away_team'],
                        "home_prob": p_home, "draw_prob": p_draw, "away_prob": p_away,
                        "home_xg": float(mu_h), "away_xg": float(mu_a), "model_version": "v2.0-poisson-all"
                    }
                    
                    # Extract Market Odds and Filter Positive Expected Value Models
                    odds_data = live_odds_book.get(f"{row['home_team']} vs {row['away_team']}")
                    best_market, best_selection, final_odds, final_ev = None, None, None, -1.0
                    
                    if odds_data and 'bookmakers' in odds_data and odds_data['bookmakers']:
                        best_bookie = odds_data['bookmakers'][0]
                        h2h_market = next((m for m in best_bookie['markets'] if m['key'] == 'h2h'), None)
                        
                        if h2h_market:
                            odds_home = next((o['price'] for o in h2h_market['outcomes'] if o['name'] == row['home_team']), 1.0)
                            ev_home = (p_home * odds_home) - 1
                            if ev_home > final_ev:
                                final_ev, final_odds, best_market, best_selection = ev_home, odds_home, "3-Way Result", "Home Win"
                    
                    pred_payload.update({
                        "best_bet_market": best_market or "3-Way Result",
                        "best_bet_selection": best_selection or "Home Win",
                        "best_bet_odds": final_odds or 2.0
                    })
                    pred_res = supabase.table("predictions").insert(pred_payload).execute()
                    
                    if final_ev > 0.03 and pred_res.data:
                        supabase.table("value_bets").insert({
                            "prediction_id": pred_res.data[0]['id'], "match_id": db_match_id,
                            "home_team": row['home_team'], "away_team": row['away_team'],
                            "market": best_market, "selection": best_selection, "odds": final_odds, "ev": final_ev
                        }).execute()
                        
        except Exception as e:
            print(f"⚠️ Loop Exception caught on league context {league}: {str(e)}")
            continue
            
    print("✅ Complete Loop Execution Sequence Finished Safely.")

if __name__ == "__main__":
    run_pipeline()
