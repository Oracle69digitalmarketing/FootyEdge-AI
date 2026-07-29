import os
import hashlib
import numpy as np
import pandas as pd
import soccerdata as sd
import requests
from datetime import datetime, timezone
from scipy.stats import poisson
from supabase import create_client, Client
import logging

from agents.goal_distribution_agent import GoalDistributionAgent
from agents.kelly_agent import KellyAgent

# Setup Logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("pipeline")

# Initialize Shared Agents
goal_agent = GoalDistributionAgent()
kelly_agent = KellyAgent()

# Initialize Environment Elements
SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_SERVICE_KEY") or os.environ.get("SUPABASE_KEY")
ODDS_API_KEY = os.environ.get("ODDS_API_KEY")

if not SUPABASE_URL or not SUPABASE_KEY:
    logger.warning("SUPABASE_URL and SUPABASE_KEY not set. Pipeline will run in limited mode.")
    # No-op or mock logic could go here
else:
    supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# Active international and domestic target registry matrix
LEAGUES = [
    "ENG-Premier League", "ESP-La Liga", "GER-Bundesliga", "ITA-Serie A",
    "FRA-Ligue 1", "INT-World Cup", "INT-Euro"
]
CURRENT_SEASON = "2425" # Using 2425 as current active season format for soccerdata

ODDS_API_LEAGUE_MAP = {
    "ENG-Premier League": "soccer_epl",
    "ESP-La Liga": "soccer_spain_la_liga",
    "GER-Bundesliga": "soccer_germany_bundesliga",
    "ITA-Serie A": "soccer_italy_serie_a",
    "FRA-Ligue 1": "soccer_france_ligue_one",
    "INT-World Cup": "soccer_fifa_world_cup"
}

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def generate_deterministic_id(name: str) -> int:
    hash_obj = hashlib.sha256(name.encode('utf-8'))
    return int(hash_obj.hexdigest()[:12], 16)

def fetch_market_odds(league_key: str):
    """Fetches real-time market data directly from The Odds API."""
    if not ODDS_API_KEY or not league_key: return {}
    url = f"https://api.the-odds-api.com/v4/sports/{league_key}/odds/"
    try:
        res = requests.get(url, params={"apiKey": ODDS_API_KEY, "regions": "uk,us", "markets": "h2h,totals", "oddsFormat": "decimal"})
        if res.status_code == 200:
            return {f"{g['home_team']} vs {g['away_team']}": g for g in res.json()}
    except Exception: pass
    return {}

def compute_ewma_form_factors(df_matches, alpha=0.35):
    """
    Feature: Exponentially Weighted Moving Average (EWMA).
    Gives a 35% heavier mathematical model weight to recent matches over distant ones.
    """
    df_sorted = df_matches.dropna(subset=['home_score', 'away_score']).sort_values(by='date', ascending=True)
    teams = pd.concat([df_sorted['home_team'], df_sorted['away_team']]).unique()
    form_registry = {team: {"att": 1.0, "def": 1.0} for team in teams}

    for _, row in df_sorted.iterrows():
        h, a = row['home_team'], row['away_team']
        h_score, a_score = float(row['home_score']), float(row['away_score'])

        # Calculate recent game variations against baseline model expectations
        h_perf_att = h_score / 1.35
        a_perf_def = h_score / 1.15
        a_perf_att = a_score / 1.15
        h_perf_line_def = a_score / 1.35

        # Apply exponential decay update constraints rule
        form_registry[h]["att"] = (alpha * h_perf_att) + ((1 - alpha) * form_registry[h]["att"])
        form_registry[h]["def"] = (alpha * h_perf_line_def) + ((1 - alpha) * form_registry[h]["def"])
        form_registry[a]["att"] = (alpha * a_perf_att) + ((1 - alpha) * form_registry[a]["att"])
        form_registry[a]["def"] = (alpha * a_perf_def) + ((1 - alpha) * form_registry[a]["def"])

    return form_registry

def run_pipeline():
    logger.info("🚀 Initiating Production Multi-Market Analytics Optimization Pipeline...")
    render_cache = os.path.join("/tmp", "soccerdata_cache")

    for league in LEAGUES:
        try:
            logger.info(f"📦 Processing {league} data feeds...")
            fbref = sd.FBref(leagues=league, seasons=CURRENT_SEASON, data_dir=render_cache)
            schedule = fbref.read_schedule()

            if schedule is None or schedule.empty:
                logger.warning(f"No schedule found for {league}")
                continue

            schedule = schedule.reset_index()
            schedule['match_date'] = pd.to_datetime(schedule['date'])

            # Compute advanced performance form weights
            team_strengths = compute_ewma_form_factors(schedule)
            odds_feed = fetch_market_odds(ODDS_API_LEAGUE_MAP.get(league))

            for _, row in schedule.iterrows():
                h_name, a_name = row['home_team'], row['away_team']
                h_id = str(generate_deterministic_id(h_name))
                a_id = str(generate_deterministic_id(a_name))

                # Auto-Seed teams tables dynamically to resolve dependencies
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

                    h_form = team_strengths.get(h_name, {"att": 1.45, "def": 1.15})
                    a_form = team_strengths.get(a_name, {"att": 1.45, "def": 1.15})

                    # Compute expected goals grid using dynamic EWMA form factors
                    mu_h = h_form["att"] * a_form["def"] * 1.14
                    mu_a = a_form["att"] * h_form["def"]

                    # Use shared GoalDistributionAgent (AR-008)
                    dist = goal_agent.calculate(mu_h, mu_a)
                    p_home = dist.home_win_prob
                    p_draw = dist.draw_prob
                    p_away = dist.away_win_prob
                    p_over_25 = dist.over_under["2.5"]
                    p_btts_yes = dist.both_teams_score

                    # Helper to get current market price
                    def get_market_price(market_key, selection_name, point=None):
                        match_odds = odds_feed.get(f"{h_name} vs {a_name}")
                        if not match_odds or 'bookmakers' not in match_odds: return None
                        
                        for bookmaker in match_odds['bookmakers']:
                            for market in bookmaker.get('markets', []):
                                if market['key'] == market_key:
                                    for outcome in market.get('outcomes', []):
                                        if outcome['name'] == selection_name:
                                            if point is None or outcome.get('point') == point:
                                                return float(outcome['price'])
                        return None

                    # MARKET 4: Spreads (calculate prob of covering)
                    # Note: Simplified spread analysis
                    p_home_spread = float(np.sum(np.tril(grid, -1))) + float(np.sum(np.diag(grid))) # Win or Draw covers +0.5
                    
                    # Update best selection logic using actual market prices
                    potential_bets = [
                        {"market": "3-Way Result", "sel": "Home Win", "prob": p_home, "price": get_market_price('h2h', h_name)},
                        {"market": "3-Way Result", "sel": "Away Win", "prob": p_away, "price": get_market_price('h2h', a_name)},
                        {"market": "Over/Under 2.5", "sel": "Over 2.5 Goals", "prob": p_over_25, "price": get_market_price('totals', 'Over', 2.5)},
                    ]
                    
                    # Filter for bets where market price is available
                    valid_bets = [b for b in potential_bets if b['price']]
                    
                    best_bet = max(valid_bets, key=lambda x: (x['prob'] * x['price']) - 1) if valid_bets else potential_bets[0]
                    
                    best_market = best_bet['market']
                    best_selection = best_bet['sel']
                    best_prob = best_bet['prob']
                    actual_odds = best_bet['price'] or 1.95

                    # Calculate Kelly Stake (CR-014)
                    kelly_stake = kelly_agent.calculate_stake(best_prob, actual_odds)

                    # Insert full multi-market probability payload
                    pred_res = supabase.table("predictions").insert({
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
                        "best_bet_odds": actual_odds,
                        "kelly_percentage": kelly_stake,
                        "over_2_5_prob": p_over_25,
                        "btts_prob": p_btts_yes,
                        "created_at": datetime.now(timezone.utc).isoformat()
                    }).execute()

                    # CLOSING LINE VALUE TRACKER (CLV)
                    ev_edge = (best_prob * actual_odds) - 1

                    if ev_edge > 0.03 and pred_res.data:
                        supabase.table("value_bets").insert({
                            "prediction_id": pred_res.data[0]['id'], "match_id": db_match_id,
                            "home_team": h_name, "away_team": a_name,
                            "market": best_market, "selection": best_selection,
                            "odds": actual_odds, "ev": ev_edge, 
                            "kelly_percentage": kelly_stake,
                            "status": "active",
                            "created_at": datetime.now(timezone.utc).isoformat()
                        }).execute()

        except Exception as e:
            logger.error(f"⚠️ League sync interruption loop warning ({league}): {str(e)}")
            continue

    logger.info("✅ All Multiple Betting Markets Processed and Synced!")

if __name__ == "__main__":
    run_pipeline()
