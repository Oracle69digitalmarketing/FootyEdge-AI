from fastapi import APIRouter, FastAPI, HTTPException
from pydantic import BaseModel, Field
from typing import List, Dict, Any
import logging
import os
from supabase import create_client, Client
from datetime import datetime

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

class UpdateBetStatusRequest(BaseModel):
    status: str

class TelegramBroadcastRequest(BaseModel):
    prediction: Dict[str, Any]
    valueBet: Dict[str, Any]
    isPremium: bool

class AccaSelection(BaseModel):
    match_id: int
    market: str
    odds: float
    selection: str

class AccaRecordRequest(BaseModel):
    user_id: str
    selections: List[AccaSelection]
    total_odds: float
    stake: float
    potential_return: float
    bookmaker: str

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

@router.patch("/value-bets/{bet_id}", summary="Update the status of a value bet")
async def update_value_bet_status(bet_id: str, request: UpdateBetStatusRequest):
    if not supabase:
        raise HTTPException(status_code=503, detail="Database not configured.")
    
    if request.status not in ['won', 'lost']:
        raise HTTPException(status_code=400, detail="Invalid status. Must be 'won' or 'lost'.")

    response = supabase.table("value_bets").update({"status": request.status}).eq("id", bet_id).execute()

    if not response.data:
        raise HTTPException(status_code=404, detail=f"Bet with id {bet_id} not found.")

    return response.data

@router.get("/teams/{team_name}", summary="Get detailed team statistics and history")
async def team_stats(team_name: str):
    if not supabase: raise HTTPException(status_code=503, detail="Database not configured.")
    team_response = supabase.table("teams").select("*").eq("name", team_name).single().execute()
    if not team_response.data: raise HTTPException(status_code=404, detail=f"Team '{team_name}' not found.")
    team_data = team_response.data
    history_response = supabase.table("team_ratings_history").select("rating_date, elo_rating, attack_strength, defense_strength").eq("team_id", team_data['id']).order("rating_date", desc=True).limit(30).execute()
    team_data['ratings_history'] = history_response.data or []
    return team_data

# --- Premium Endpoints ---
@router.get("/premium/performance", summary="Get premium signal performance metrics")
async def get_premium_performance():
    # Placeholder for fetching real performance data
    return {
        "avg_confidence": 87.4,
        "roi_30d": 14.2,
        "win_rate": 72.1
    }

@router.get("/premium/telegram-config", summary="Get premium Telegram alert configuration")
async def get_premium_telegram_config():
    # Placeholder for fetching real Telegram config
    return {
        "status": "active",
        "channel_id": "@footyedge_premium",
        "alerts_enabled": True
    }

@router.get("/premium/upcoming-matches", summary="Get upcoming high-value matches for premium members")
async def get_premium_upcoming_matches():
    # Placeholder for fetching real upcoming matches
    return [
        {"id": "match1", "home_team": "Team A", "away_team": "Team B", "edge": "+10.5%", "time_until": "2h 30m"},
        {"id": "match2", "home_team": "Team C", "away_team": "Team D", "edge": "+8.2%", "time_until": "4h 15m"},
        {"id": "match3", "home_team": "Team E", "away_team": "Team F", "edge": "+11.1%", "time_until": "5h 00m"},
    ]

# --- Admin Endpoints ---
@router.get("/admin/stats", summary="Get admin dashboard statistics")
async def get_admin_stats():
    # Placeholder for fetching real admin stats
    return {
        "total_users": 1284,
        "premium_subs": 412,
        "daily_revenue": 84200,
        "bot_health": 100
    }

@router.get("/admin/activity", summary="Get recent system activity logs")
async def get_admin_activity():
    # Placeholder for fetching real activity logs
    return [
        {"time": "14:22", "event": "Premium Signal Broadcasted", "status": "success"},
        {"time": "14:15", "event": "New Subscription: Weekly Plan", "status": "success"},
        {"time": "13:58", "event": "AI Engine: Deep Scan Completed", "status": "info"},
        {"time": "13:42", "event": "Telegram Webhook: Message Delivered", "status": "success"}
    ]

@router.post("/telegram/broadcast", summary="Broadcast a message to Telegram channel")
async def telegram_broadcast(request: TelegramBroadcastRequest):
    # Placeholder for actual Telegram integration
    logger.info(f"Broadcasting to Telegram: Prediction {request.prediction.get('home_team')} vs {request.prediction.get('away_team')}, Value: {request.valueBet.get('selection')}")
    return {"success": True, "message": "Broadcast simulated successfully."}

# --- Acca Endpoints ---
@router.post("/accas/record", summary="Record a user's accumulator bet")
async def record_acca(request: AccaRecordRequest):
    if not supabase:
        raise HTTPException(status_code=503, detail="Database not configured.")
    
    # Store the acca selections in a simplified format for now
    # In a real app, you'd want to store each selection individually and link them
    acca_data = {
        "user_id": request.user_id,
        "selections_json": [s.dict() for s in request.selections], # Store as JSON
        "total_odds": request.total_odds,
        "stake": request.stake,
        "potential_return": request.potential_return,
        "bookmaker": request.bookmaker,
        "created_at": datetime.now().isoformat(),
        "status": "pending" # Default status
    }

    response = supabase.table("accas").insert(acca_data).execute()

    if response.data:
        return {"success": True, "message": "Acca recorded successfully!", "data": response.data[0]}
    else:
        raise HTTPException(status_code=500, detail="Failed to record acca.")


# --- External API Endpoints (Phase 1) ---
@router.get("/search/teams", summary="Search for teams")
async def search_teams_ext(q: str):
    return football_client.search_teams(q)

@router.get("/search/players", summary="Search for players")
async def search_players_ext(q: str):
    return football_client.search_players(q)

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
