import os
import hashlib
import numpy as np
import pandas as pd
import soccerdata as sd
import requests
import logging
from datetime import datetime
from scipy.optimize import minimize
from scipy.stats import poisson
from supabase import create_client, Client

# Initialize Logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("prediction_pipeline")

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
    except Exception as e:
        logger.error(f"❌ Error fetching live odds: {e}")
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
    logger.info("⚽ Initiating Open Source Core Predictive Analytics Engine...")
    
    for league in LEAGUES:
        try:
            logger.info(f"🔄 Executing loop sequence for league context: {league}")
            
            league_short = league.split('-')[1] if '-' in league else league
            render_tmp_cache = os.path.join("/tmp", "soccerdata_cache")
            
            # Ensure cache dir exists and is writable
            os.makedirs(render_tmp_cache, exist_ok=True)
            
            fbref = sd.FBref(leagues=league_short, seasons=CURRENT_SEASON, data_dir=render_tmp_cache)
            schedule = fbref.read_schedule().reset_index()
            
            if schedule.empty:
                logger.warning(f"⚠️ No schedule data found for {league}.")
                continue
                
            schedule['match_date'] = pd.to_datetime(schedule['date'])
            team_strengths = solve_poisson_strengths(schedule)
            live_odds_book = fetch_live_odds(ODDS_API_LEAGUE_MAP.get(league))
            
            # Sync Teams Table Loop
            unique_teams = pd.concat([schedule['home_team'], schedule['away_team']]).unique()
            for team_name in unique_teams:
                ts = team_strengths.get(team_name, {"attack": 1.0, "defense": 1.0})
                try:
                    data = {
                        "id": generate_deterministic_id(team_name), "name": team_name, "league_name": league,
                        "attack_strength": ts["attack"], "defense_strength": ts["defense"], "updated_at": datetime.utcnow().isoformat()
                    }
                    res = supabase.table("teams").upsert(data).execute()
                    if not res.data:
                        logger.error(f"❌ Failed upsert for team: {team_name}")
                except Exception as e:
                    logger.error(f"❌ Exception during team upsert for {team_name}: {e}")
            
            # Sync Matches & Process Calculations Loop
            for _, row in schedule.iterrows():
                try:
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
                        logger.warning(f"⚠️ Match not upserted: {row['home_team']} vs {row['away_team']}")
                        continue
                        
                    db_match_id = match_res.data[0]['id']
                    
                    # ... [prediction and value bet logic] ...
                    
                except Exception as e:
                    logger.error(f"❌ Error processing match {row['home_team']} vs {row['away_team']}: {e}")
                        
        except Exception as e:
            logger.error(f"⚠️ Loop Exception caught on league context {league}: {str(e)}", exc_info=True)
            continue
            
    logger.info("✅ Complete Loop Execution Sequence Finished Safely.")

if __name__ == "__main__":
    run_pipeline()
