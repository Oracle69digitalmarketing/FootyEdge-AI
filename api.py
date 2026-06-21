import os
import numpy as np
from datetime import datetime, timedelta
from fastapi import APIRouter, Depends, HTTPException, Query, Header, BackgroundTasks
from supabase import create_client, Client
from pydantic import BaseModel
from prediction_pipeline import run_pipeline

router = APIRouter()
# ... (rest of imports and setup)
def get_supabase_client():
    return supabase

@router.get("/api/daily-picks")
@router.get("/api/daily-picks/")
async def get_user_filtered_predictions(
    timeline: str = Query("daily", description="Options: daily, weekly, custom"),
    from_date: str = Query(None, alias="from_date", description="YYYY-MM-DD"),
    to_date: str = Query(None, alias="to_date", description="YYYY-MM-DD"),
    supabase: Client = Depends(get_supabase_client)
):
    """
    Unified User Prediction Feed. 
    Accepts from_date and to_date parameters to prevent duplicate match rendering across tabs.
    """
    now = datetime.utcnow()
    query_start = now.strftime("%Y-%m-%d 00:00:00")
    query_end = now.strftime("%Y-%m-%d 23:59:59")
    
    if timeline == "weekly":
        one_week_later = now + timedelta(days=7)
        query_end = one_week_later.strftime("%Y-%m-%d 23:59:59")
    elif timeline == "custom" and from_date and to_date:
        query_start = f"{from_date} 00:00:00"
        query_end = f"{to_date} 23:59:59"
        
    try:
        # Fetch target matches within selected date parameters
        matches_res = supabase.table("matches") \
            .select("id, match_date, league") \
            .gte("match_date", query_start) \
            .lte("match_date", query_end) \
            .execute()
            
        if not matches_res.data:
            return []
            
        match_ids = [m['id'] for m in matches_res.data]
        
        # Pull calculations from predictions array matrix
        preds_res = supabase.table("predictions") \
            .select("*") \
            .in_("match_id", match_ids) \
            .execute()
            
        return preds_res.data
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch timeline predictions: {str(e)}")

@router.get("/api/teams")
@router.get("/api/teams/")
async def get_production_teams(supabase: Client = Depends(get_supabase_client)):
    """Returns actual teams built by soccerdata, sorted alphabetically."""
    res = supabase.table("teams").select("*").order("name", asc=True).execute()
    return res.data

@router.get("/api/players")
@router.get("/api/players/")
async def get_production_players(supabase: Client = Depends(get_supabase_client)):
    """Read-only actual players feed, removing the 'Database Not Initialized' overlay error."""
    res = supabase.table("players").select("*, teams(name, logo_url)").limit(100).execute()
    return res.data

@router.get("/api/value-bets")
async def get_value_bets_dashboard(supabase: Client = Depends(get_supabase_client)):
    """Fetches high EV advantages directly from Supabase cache tables."""
    res = supabase.table("value_bets").select("*").eq("status", "active").order("ev", desc=True).execute()
    return res.data

@router.get("/api/acca-builder")
async def get_automated_accumulator_ticket(supabase: Client = Depends(get_supabase_client)):
    """
    Greedy Combinator Algorithm.
    Queries active value advantages and packs the top 3 items into a high-yield combined Acca slip.
    """
    try:
        res = supabase.table("value_bets")             .select("id, home_team, away_team, market, selection, odds, ev")             .eq("status", "active")             .order("ev", desc=True)             .limit(3)             .execute()
            
        if not res.data or len(res.data) < 2:
            return {"status": "insufficient_data", "combined_odds": 1.0, "selections": []}
            
        selections = res.data
        # Multiply odds sequentially to calculate the combined accumulator multiplier
        combined_odds = float(np.prod([item['odds'] for item in selections]))
        
        return {
            "status": "success",
            "combined_odds": round(combined_odds, 2),
            "selections": selections
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Acca Combinator computation failed: {str(e)}")

@router.get("/api/public-ledger")
async def get_public_accuracy_audit_trail(supabase: Client = Depends(get_supabase_client)):
    """
    Public Transparency Audit Ledger.
    Returns settled outcomes to verify accuracy and build trust with users.
    """
    try:
        res = supabase.table("predictions")             .select("id, home_team, away_team, best_bet_market, best_bet_selection, best_bet_odds, actual_result")             .not_.is_("actual_result", "null")             .order("created_at", desc=True)             .limit(50)             .execute()
        return res.data
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch public accuracy audit trail: {str(e)}")

@router.get("/api/cron-trigger")
async def manual_cron_trigger(
    background_tasks: BackgroundTasks, 
    x_cron_token: str = Header(None) # Looks for a custom header key
):
    # Retrieve a secure passphrase token from your system environment
    CRON_SECRET = os.environ.get("CRON_SECRET_TOKEN", "default_secure_pass_123")
    
    if x_cron_token != CRON_SECRET:
        raise HTTPException(status_code=401, detail="Unauthorized execution vector.")
        
    background_tasks.add_task(run_pipeline)
    return {"status": "queued"}
