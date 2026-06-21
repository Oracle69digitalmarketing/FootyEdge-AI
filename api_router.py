import os
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, Query
from supabase import create_client, Client
from pydantic import BaseModel
from typing import List, Dict, Any, Optional

router = APIRouter()

# Initialize Supabase Client
SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_SERVICE_KEY") or os.environ.get("SUPABASE_KEY")
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

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
    now = datetime.now(timezone.utc)
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

        m_ids = [m['id'] for m in matches_res.data]

        # Pull calculations from predictions array matrix
        preds_res = supabase.table("predictions") \
            .select("*") \
            .in_("match_id", m_ids) \
            .execute()

        return preds_res.data
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch timeline predictions: {str(e)}")

@router.get("/api/teams")
@router.get("/api/teams/")
async def get_production_teams(supabase: Client = Depends(get_supabase_client)):
    """Returns actual teams sorted alphabetically."""
    res = supabase.table("teams").select("*").order("name").execute()
    return res.data

@router.get("/api/players")
@router.get("/api/players/")
async def get_production_players(supabase: Client = Depends(get_supabase_client)):
    """Read-only actual players feed."""
    res = supabase.table("players").select("*, teams(name)").limit(100).execute()
    return res.data

@router.get("/api/value-bets")
async def get_value_bets_dashboard(supabase: Client = Depends(get_supabase_client)):
    """Fetches high EV advantages directly from Supabase cache tables."""
    res = supabase.table("value_bets").select("*").eq("status", "active").order("ev", desc=True).execute()
    return res.data
