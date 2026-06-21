import os
import pandas as pd
from supabase import create_client, Client
import logging

# Initialize Supabase
SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_SERVICE_KEY") or os.environ.get("SUPABASE_KEY")
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def run_historical_backtest():
    logger.info("📊 Fetching historical match data and predictions for validation...")

    # 1. Pull data arrays from database layers
    pred_res = supabase.table("predictions").select("*").execute()
    match_res = supabase.table("matches").select("id, home_goals, away_goals, league").execute()

    if not pred_res.data or not match_res.data:
        logger.warning("⚠️ Insufficient historical data found in tables to evaluate performance metrics.")
        return

    preds_df = pd.DataFrame(pred_res.data)
    matches_df = pd.DataFrame(match_res.data).rename(columns={"id": "match_id"})

    # 2. Merge predictions with real historical match outcomes
    df = pd.merge(preds_df, matches_df, on="match_id", how="inner")

    # Clean rows that haven't been played yet
    df = df.dropna(subset=["home_goals", "away_goals"])

    if df.empty:
        logger.warning("⚠️ No completed matches found to verify model accuracy.")
        return

    # 3. Determine actual match results
    def calculate_actual_result(row):
        if row['home_goals'] > row['away_goals']: return "Home Win"
        elif row['home_goals'] == row['away_goals']: return "Draw"
        else: return "Away Win"

    df['actual_outcome'] = df.apply(calculate_actual_result, axis=1)
    df['is_correct'] = df['best_bet_selection'] == df['actual_outcome']

    # 4. Compute Financial Metrics (Assuming a flat stake of $100 per selection)
    FLAT_STAKE = 100.0
    total_bets = len(df)
    total_investment = total_bets * FLAT_STAKE

    def calculate_pnl(row):
        if row['is_correct']:
            return (FLAT_STAKE * row['best_bet_odds']) - FLAT_STAKE
        return -FLAT_STAKE

    df['pnl'] = df.apply(calculate_pnl, axis=1)

    total_pnl = df['pnl'].sum()
    roi = (total_pnl / total_investment) * 100 if total_investment > 0 else 0
    accuracy = (df['is_correct'].sum() / total_bets) * 100 if total_bets > 0 else 0

    # 5. Output Summary
    print("\n===========================================")
    print("      FOOTYEDGE AI PERFORMANCE METRICS     ")
    print("===========================================")
    print(f"Total Matches Tracked and Evaluated: {total_bets}")
    print(f"Overall Prediction Accuracy Rating: {accuracy:.2f}%")
    print(f"Net Financial Performance (PnL):    ${total_pnl:,.2f}")
    print(f"Total Capital ROI Percentage:      {roi:.2f}%")
    print("===========================================\n")

    return {
        "total_bets": total_bets,
        "accuracy": accuracy,
        "pnl": total_pnl,
        "roi": roi
    }

if __name__ == "__main__":
    run_historical_backtest()
