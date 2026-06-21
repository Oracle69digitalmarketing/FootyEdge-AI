import os
import logging
import soccerdata as sd
import pandas as pd
from datetime import datetime, timedelta, timezone
from supabase import create_client, Client

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("settle_bets")

SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_SERVICE_KEY") or os.environ.get("SUPABASE_KEY")
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

LEAGUES = ["ENG-Premier League", "ESP-La Liga", "GER-Bundesliga", "ITA-Serie A", "FRA-Ligue 1"]
CURRENT_SEASON = "2425"

def run_settlement():
    logger.info("🏁 Initiating automated bet settlement routine...")
    yesterday = (datetime.now(timezone.utc) - timedelta(days=1)).strftime("%Y-%m-%d")

    for league in LEAGUES:
        try:
            # 1. Scrape yesterday's actual results
            fbref = sd.FBref(leagues=league, seasons=CURRENT_SEASON)
            schedule = fbref.read_schedule().reset_index()

            if schedule.empty:
                continue

            # Filter down to matches played yesterday with valid scores
            schedule['match_date_str'] = pd.to_datetime(schedule['date']).dt.strftime("%Y-%m-%d")
            completed_games = schedule[(schedule['match_date_str'] == yesterday) & schedule['home_score'].notna()]

            for _, row in completed_games.iterrows():
                # Query our database to find this specific active match row
                match_query = supabase.table("matches") \
                    .select("id") \
                    .eq("league", league) \
                    .gte("match_date", f"{yesterday} 00:00:00") \
                    .lte("match_date", f"{yesterday} 23:59:59") \
                    .execute()

                if not match_query.data:
                    continue

                for match_record in match_query.data:
                    m_id = match_record['id']
                    h_goals = int(row['home_score'])
                    a_goals = int(row['away_score'])

                    # 2. Update the goals directly in the matches table
                    supabase.table("matches").update({
                        "home_goals": h_goals,
                        "away_goals": a_goals
                    }).eq("id", m_id).execute()

                    # Determine exact outcome string
                    if h_goals > a_goals: actual_outcome = "Home Win"
                    elif h_goals == a_goals: actual_outcome = "Draw"
                    else: actual_outcome = "Away Win"

                    # 3. Pull predictions tied to this match to mark success metrics
                    pred_query = supabase.table("predictions").select("*").eq("match_id", m_id).execute()

                    for pred in pred_query.data:
                        is_win = (pred['best_bet_selection'] == actual_outcome)

                        supabase.table("predictions").update({
                            "actual_result": actual_outcome,
                            "prediction_error": 0.0 if is_win else 1.0
                        }).eq("id", pred['id']).execute()

                        # 4. If it exists in value_bets, update its status
                        supabase.table("value_bets").update({
                            "status": "won" if is_win else "lost"
                        }).eq("prediction_id", pred['id']).execute()

                    logger.info(f"✅ Settled match ID {m_id}: {row['home_team']} {h_goals}-{a_goals} {row['away_team']}")

        except Exception as e:
            logger.error(f"⚠️ Error settling league context {league}: {str(e)}")
            continue

if __name__ == "__main__":
    run_settlement()
