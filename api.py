from fastapi import APIRouter, FastAPI, HTTPException
from pydantic import BaseModel, Field
from typing import List, Dict, Any
import logging
import os
from supabase import create_client, Client

from predictor import FootyEdgePredictor

# --- App Setup ---
app = FastAPI(
    title="FootyEdge AI - Production Betting Analysis",
    version="3.0.0",
    description="Provides sophisticated, production-ready match predictions and betting analysis."
)
router = APIRouter(prefix="/api")

predictor = FootyEdgePredictor()

# --- Supabase Client ---
supabase_url = os.environ.get("SUPABASE_URL")
supabase_key = os.environ.get("SUPABASE_KEY")
supabase: Client = create_client(supabase_url, supabase_key) if supabase_url and supabase_key else None

logger = logging.getLogger(__name__)

# --- Pydantic Models ---
class PredictRequest(BaseModel):
    home_team: str
    away_team: str
    odds: Dict[str, float] = Field(..., example={
        "home_win": 1.85, "draw": 3.40, "away_win": 4.20,
        "Over 2.5": 1.90, "Under 2.5": 1.90,
        "BTTS Yes": 1.75, "BTTS No": 2.05
    })

class AnalyzeBetRequest(BaseModel):
    home_team: str
    away_team: str
    market: str
    selection: str
    odds: float

# --- API Endpoints ---
@app.get("/")
def root():
    return {"message": "FootyEdge AI API is running."}

@router.post("/predict", summary="Generate predictions using live odds")
async def predict(request: PredictRequest):
    """
    Generates a full prediction for a match and identifies value bets
    based on the live odds you provide.
    """
    try:
        prediction = await predictor.predict_match(request.home_team, request.away_team, request.odds)
        return prediction
    except (ValueError, ConnectionError) as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"An unexpected error occurred: {e}")
        raise HTTPException(status_code=500, detail="An internal server error occurred.")

@router.post("/analyze-bet", summary="Analyze a custom bet you provide")
async def analyze_bet(request: AnalyzeBetRequest):
    """
    Analyzes a user-defined bet to determine if it has positive Expected Value (+EV).
    """
    try:
        analysis = await predictor.analyze_custom_bet(
            home_team=request.home_team,
            away_team=request.away_team,
            market=request.market,
            selection=request.selection,
            odds=request.odds
        )
        return analysis
    except (ValueError, ConnectionError) as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"An unexpected error occurred during custom bet analysis: {e}")
        raise HTTPException(status_code=500, detail="An internal server error occurred.")

@router.get("/recent-predictions", summary="Get the last N predictions")
async def recent_predictions(limit: int = 10):
    """
    Retrieves the most recent predictions recorded in the database.
    """
    if not supabase:
        raise HTTPException(status_code=503, detail="Database connection not configured.")
    try:
        response = supabase.table("predictions").select("*").order("created_at", desc=True).limit(limit).execute()
        if response.data:
            return response.data
        return []
    except Exception as e:
        logger.error(f"Error fetching recent predictions: {e}")
        raise HTTPException(status_code=500, detail="Could not fetch recent predictions.")


@router.get("/value-bets", summary="Get value bets from the database")
async def get_value_bets(status: str = 'active'):
    """
    Retrieves value bets from the database, optionally filtering by status.
    """
    if not supabase:
        raise HTTPException(status_code=503, detail="Database connection not configured.")
    try:
        query = supabase.table("value_bets").select("*").order("ev", desc=True)
        if status != 'all':
            query = query.eq("status", status)
        
        response = query.execute()

        if response.data:
            return response.data
        return []
    except Exception as e:
        logger.error(f"Error fetching value bets: {e}")
        raise HTTPException(status_code=500, detail="Could not fetch value bets.")

@router.get("/scan-value-bets", summary="Scans for all available value bets in upcoming matches.")
async def scan_value_bets():
    """
    Scans for all available value bets in upcoming matches across major leagues.
    This is a long-running task.
    """
    try:
        all_value_bets = await predictor.find_all_value_bets()
        return all_value_bets
    except Exception as e:
        logger.error(f"Error finding all value bets: {e}")
        raise HTTPException(status_code=500, detail="Could not find value bets.")


@router.get("/teams/{team_name}", summary="Get detailed team statistics and history")
async def team_stats(team_name: str):
    """
    Retrieves detailed statistics and rating history for a specific team.
    """
    if not supabase:
        raise HTTPException(status_code=503, detail="Database connection not configured.")
    try:
        # Get current team stats
        team_response = supabase.table("teams").select("*").eq("name", team_name).single().execute()
        
        if not team_response.data:
            raise HTTPException(status_code=404, detail=f"Team '{team_name}' not found.")

        team_data = team_response.data

        # Get historical ratings
        history_response = supabase.table("team_ratings_history").select("rating_date, elo_rating, attack_strength, defense_strength").eq("team_id", team_data['id']).order("rating_date", desc=True).limit(30).execute()
        
        team_data['ratings_history'] = history_response.data if history_response.data else []
        
        return team_data
    except Exception as e:
        logger.error(f"Error fetching team stats for {team_name}: {e}")
        raise HTTPException(status_code=500, detail="Could not fetch team statistics.")

app.include_router(router)
