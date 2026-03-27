from fastapi import APIRouter, FastAPI, HTTPException
from pydantic import BaseModel, Field
from typing import List, Dict, Any
import logging
import os
from supabase import create_client, Client

from predictor import FootyEdgePredictor
from football_api_client import FootballAPIClient

# --- App Setup ---
app = FastAPI(
    title="FootyEdge AI - Production Betting Analysis",
    version="3.0.0",
    description="Provides sophisticated, production-ready match predictions and betting analysis."
)
router = APIRouter(prefix="/api")

# --- Clients ---
predictor = FootyEdgePredictor()
football_client = FootballAPIClient()

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

# --- Core Features ---
@router.post("/predict", summary="Generate predictions using live odds")
async def predict(request: PredictRequest):
    return await predictor.predict_match(request.home_team, request.away_team, request.odds)

@router.post("/analyze-bet", summary="Analyze a custom bet you provide")
async def analyze_bet(request: AnalyzeBetRequest):
    return await predictor.analyze_custom_bet(
        home_team=request.home_team,
        away_team=request.away_team,
        market=request.market,
        selection=request.selection,
        odds=request.odds
    )

@router.get("/scan-value-bets", summary="Scans for all available value bets in upcoming matches.")
async def scan_value_bets():
    return await predictor.find_all_value_bets()

# --- Database Endpoints ---
@router.get("/recent-predictions", summary="Get the last N predictions")
async def recent_predictions(limit: int = 10):
    if not supabase: raise HTTPException(status_code=503, detail="Database not configured.")
    response = supabase.table("predictions").select("*").order("created_at", desc=True).limit(limit).execute()
    return response.data or []

@router.get("/value-bets", summary="Get value bets from the database")
async def get_value_bets(status: str = 'active'):
    if not supabase: raise HTTPException(status_code=503, detail="Database not configured.")
    query = supabase.table("value_bets").select("*").order("ev", desc=True)
    if status != 'all':
        query = query.eq("status", status)
    response = query.execute()
    return response.data or []

@router.get("/teams/{team_name}", summary="Get detailed team statistics and history")
async def team_stats(team_name: str):
    if not supabase: raise HTTPException(status_code=503, detail="Database not configured.")
    team_response = supabase.table("teams").select("*").eq("name", team_name).single().execute()
    if not team_response.data: raise HTTPException(status_code=404, detail=f"Team '{team_name}' not found.")
    team_data = team_response.data
    history_response = supabase.table("team_ratings_history").select("rating_date, elo_rating, attack_strength, defense_strength").eq("team_id", team_data['id']).order("rating_date", desc=True).limit(30).execute()
    team_data['ratings_history'] = history_response.data or []
    return team_data

# --- External API Endpoints (Phase 1) ---
@router.get("/search/teams", summary="Search for teams")
async def search_teams_ext(q: str):
    return football_client.search_teams(q)

@router.get("/teams/{team_id}/detail", summary="Get team details from external API")
async def get_team_detail_ext(team_id: int):
    return football_client.get_team_detail(team_id)

@router.get("/leagues", summary="List all leagues from external API")
async def list_leagues_ext():
    return football_client.list_leagues()

@router.get("/leagues/{league_id}/detail", summary="Get league details from external API")
async def get_league_detail_ext(league_id: int):
    return football_client.get_league_detail(league_id)

@router.get("/search/leagues", summary="Search for leagues in external API")
async def search_leagues_ext(q: str):
    return football_client.search_leagues(q)

# --- External API Endpoints (Phase 2) ---
@router.get("/matches", summary="Get matches by date from external API")
async def get_matches_by_date_ext(date: str):
    return football_client.get_matches_by_date(date)

@router.get("/odds/{event_id}", summary="Get odds by event ID from external API")
async def get_odds_by_event_id_ext(event_id: int):
    return football_client.get_odds_by_event_id(event_id)

@router.get("/stats/{event_id}", summary="Get statistics by event ID from external API")
async def get_stats_by_event_id_ext(event_id: int):
    return football_client.get_stats_by_event_id(event_id)

# --- External API Endpoints (Phase 3) ---
@router.get("/h2h", summary="Get head-to-head between two teams")
async def get_h2h(team1_id: int, team2_id: int):
    return football_client.get_h2h(team1_id, team2_id)

@router.get("/standings/{league_id}", summary="Get league standings")
async def get_standings(league_id: int):
    return football_client.get_standings(league_id)

@router.get("/teams/{team_id}/players", summary="List all players for a team")
async def list_players_by_team(team_id: int):
    return football_client.list_players_by_team(team_id)

@router.get("/players/{player_id}", summary="Get player details")
async def get_player_detail(player_id: int):
    return football_client.get_player_detail(player_id)


app.include_router(router)
