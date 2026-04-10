from fastapi import APIRouter, FastAPI, HTTPException, Request, Response
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel, Field
from typing import List, Dict, Any, Optional
import logging
import os
import httpx
from supabase import create_client, Client
from datetime import datetime, timedelta, timezone
import asyncio
from predictor import FootyEdgePredictor
from football_api_client import FootballAPIClient

# --- App Setup ---
app = FastAPI(
    title="FootyEdge AI - Production Betting Analysis",
    version="3.0.0",
    description="Provides sophisticated, production-ready match predictions and betting analysis."
)
router = APIRouter(prefix="/api")
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# --- Environment Variable Checks & Client Initialization ---
supabase_url = os.environ.get("SUPABASE_URL")
supabase_key = os.environ.get("SUPABASE_KEY")
rapidapi_key = os.environ.get("RAPIDAPI_KEY")

if not supabase_url or not supabase_key:
    logger.warning("Supabase environment variables not found. Database client will not be available.")
    supabase = None
else:
    supabase = create_client(supabase_url, supabase_key)

if not rapidapi_key:
    logger.warning("RapidAPI key not found. Football API client will not be available.")
    football_client = None
else:
    football_client = FootballAPIClient()

predictor = FootyEdgePredictor()

@app.middleware("http")
async def log_requests(request, call_next):
    logger.info(f"API Request: {request.method} {request.url.path}")
    return await call_next(request)

if not os.environ.get("RAPIDAPI_KEY"):
    logger.warning("RAPIDAPI_KEY is not set. Player and Team search will not work.")
if not os.environ.get("SUPABASE_URL") or not os.environ.get("SUPABASE_KEY"):
    logger.warning("Supabase environment variables are not set. Database features will be unavailable.")

# --- Pydantic Models ---
class PredictRequest(BaseModel):
    home_team: str
    away_team: str
    odds: Dict[str, float] = Field(default={
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

class SubscribeRequest(BaseModel):
    userId: str
    plan: str

class BetRecordRequest(BaseModel):
    user_id: str
    match_id: int
    market: str
    selection: str
    odds: float
    stake: float


# --- Root Endpoints ---
@app.get("/")
@app.head("/")
def root():
    return {"message": "FootyEdge AI API is running."}


# --- Health Check ---
@router.get("/health", summary="Health check for service and environment variables")
async def health_check():
    """Provides a health check for Render and verifies environment variable setup."""
    return {
        "status": "healthy",
        "supabase": "configured" if supabase else "missing",
        "rapidapi": "configured" if rapidapi_key else "missing",
        "rapidapi_host": os.environ.get('RAPIDAPI_HOST', 'free-api-live-football-data.p.rapidapi.com')
    }


# --- Core Features ---
@router.post("/predict", summary="Generate predictions using live odds")
async def predict(request: PredictRequest):
    try:
        return await predictor.predict_match(request.home_team, request.away_team, request.odds)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Prediction failed: {str(e)}")


@router.post("/analyze-bet", summary="Analyze a custom bet you provide")
async def analyze_bet(request: AnalyzeBetRequest):
    try:
        return await predictor.analyze_custom_bet(
            home_team=request.home_team,
            away_team=request.away_team,
            market=request.market,
            selection=request.selection,
            odds=request.odds
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/scan-value-bets", summary="Scans for all available value bets in upcoming matches.")
async def scan_value_bets():
    if not football_client:
        raise HTTPException(status_code=503, detail="Football API not configured.")
    try:
        return await predictor.find_all_value_bets()
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


# --- Database Endpoints ---
@router.get("/recent-predictions", summary="Get the last N predictions")
async def recent_predictions(limit: int = 10):
    if not supabase:
        raise HTTPException(status_code=503, detail="Database not configured.")
    response = supabase.table("predictions").select("*").order("created_at", desc=True).limit(limit).execute()
    return response.data or []


@router.get("/value-bets", summary="Get value bets from the database")
async def get_value_bets(status: str = 'active'):
    if not supabase:
        raise HTTPException(status_code=503, detail="Database not configured.")
    query = supabase.table("value_bets").select("*").order("ev", desc=True)
    if status == 'live':
        query = query.eq("status", "active").filter("match_timestamp", "gt", datetime.now().isoformat())
    elif status != 'all':
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
    if not supabase:
        raise HTTPException(status_code=503, detail="Database not configured.")
    team_response = supabase.table("teams").select("*").eq("name", team_name).single().execute()
    if not team_response.data:
        raise HTTPException(status_code=404, detail=f"Team '{team_name}' not found.")
    team_data = team_response.data
    history_response = supabase.table("team_ratings_history").select(
        "rating_date, elo_rating, attack_strength, defense_strength"
    ).eq("team_id", team_data['id']).order("rating_date", desc=True).limit(30).execute()
    team_data['ratings_history'] = history_response.data or []
    return team_data


# --- Premium Endpoints ---
@router.get("/premium/performance", summary="Get premium signal performance metrics")
async def get_premium_performance():
    if not supabase:
        raise HTTPException(status_code=503, detail="Database not configured.")
    
    thirty_days_ago = (datetime.now() - timedelta(days=30)).isoformat()
    bets_response = supabase.table("value_bets").select("stake_units, status, odds").filter(
        "created_at", "gte", thirty_days_ago
    ).in_("status", ["won", "lost"]).execute()
    
    total_staked = 0
    net_profit = 0
    if bets_response.data:
        for bet in bets_response.data:
            stake = bet.get('stake_units', 1)
            total_staked += stake
            if bet['status'] == 'won':
                net_profit += (stake * bet['odds']) - stake
            else:
                net_profit -= stake
    
    roi_30d = (net_profit / total_staked) * 100 if total_staked > 0 else 0
    
    win_rate_response = supabase.table("value_bets").select("status").in_("status", ["won", "lost"]).execute()
    won_bets = [b for b in win_rate_response.data if b['status'] == 'won'] if win_rate_response.data else []
    win_rate = (len(won_bets) / len(win_rate_response.data)) * 100 if win_rate_response.data else 0
    
    predictions_response = supabase.table("predictions").select("confidence").execute()
    avg_confidence = 0
    if predictions_response.data:
        avg_confidence = sum([p['confidence'] for p in predictions_response.data]) / len(predictions_response.data)
    
    return {
        "avg_confidence": round(avg_confidence * 100, 2),
        "roi_30d": round(roi_30d, 2),
        "win_rate": round(win_rate, 2)
    }


@router.get("/premium/telegram-config", summary="Get premium Telegram alert configuration")
async def get_premium_telegram_config():
    return {
        "status": "active",
        "channel_id": "@footyedge_premium",
        "alerts_enabled": True
    }


@router.get("/premium/upcoming-matches", summary="Get upcoming high-value matches for premium members")
async def get_premium_upcoming_matches(limit: int = 5):
    if not supabase:
        raise HTTPException(status_code=503, detail="Database not configured.")
    response = supabase.table("value_bets").select("*").eq("status", "active").order("ev", desc=True).limit(limit).execute()
    return response.data or []


@router.post("/premium/subscribe", summary="Subscribe a user to a premium plan")
async def subscribe(request: SubscribeRequest):
    if not supabase:
        raise HTTPException(status_code=503, detail="Database not configured.")
    response = supabase.table("profiles").update({"is_premium": True}).eq("id", request.userId).execute()
    if not response.data:
        raise HTTPException(status_code=404, detail=f"User with id {request.userId} not found.")
    return {"success": True, "message": f"Successfully subscribed to {request.plan}!"}


# --- Admin Endpoints ---
@router.post("/admin/sync-teams", summary="Sync teams from external API to Supabase")
async def sync_teams():
    if not football_client or not supabase:
        raise HTTPException(status_code=503, detail="Clients not configured.")
    
    leagues_data = await football_client.list_leagues()
    if not leagues_data or 'response' not in leagues_data:
        raise HTTPException(status_code=500, detail="Failed to fetch leagues from external API.")
    
    all_teams = []
    for league_item in leagues_data['response']:
        league_id = league_item.get('league', {}).get('id')
        league_name = league_item.get('league', {}).get('name')
        country = league_item.get('country', {}).get('name')
        if not league_id:
            continue
        
        logger.info(f"Fetching teams for league: {league_name} ({league_id})")
        teams_data = await football_client.get_teams_by_league(league_id)
        if teams_data and 'response' in teams_data:
            for team_item in teams_data['response']:
                team_info = team_item.get('team', {})
                if team_info.get('id') and team_info.get('name'):
                    all_teams.append({
                        "id": team_info['id'],
                        "name": team_info['name'],
                        "country": team_info.get('country'),
                        "logo_url": team_info.get('logo'),
                        "league_name": league_name,
                    })
        await asyncio.sleep(1)
    
    if not all_teams:
        raise HTTPException(status_code=500, detail="No teams found from external API.")
    
    upsert_response = supabase.table("teams").upsert(all_teams).execute()
    if upsert_response.data:
        return {"status": "success", "synced_count": len(upsert_response.data)}
    else:
        raise HTTPException(status_code=500, detail="Failed to upsert teams to Supabase.")


@router.get("/admin/stats", summary="Get admin dashboard statistics")
async def get_admin_stats():
    if not supabase:
        raise HTTPException(status_code=503, detail="Database not configured.")
    
    users_response = supabase.table("profiles").select("id", count="exact").execute()
    premium_users_response = supabase.table("profiles").select("id", count="exact").eq("is_premium", True).execute()
    
    total_premium = premium_users_response.count or 0
    estimated_daily_revenue = (total_premium * 35000) / 30
    
    logs_response = supabase.table("agent_logs").select("success").order("created_at", desc=True).limit(100).execute()
    if logs_response.data:
        success_count = sum(log['success'] for log in logs_response.data)
        bot_health = (success_count / len(logs_response.data)) * 100
    else:
        bot_health = 100.0
    
    return {
        "total_users": users_response.count,
        "premium_subs": premium_users_response.count,
        "daily_revenue": round(estimated_daily_revenue, 2),
        "bot_health": round(bot_health, 2)
    }


@router.get("/admin/activity", summary="Get recent system activity logs")
async def get_admin_activity(limit: int = 10):
    if not supabase:
        raise HTTPException(status_code=503, detail="Database not configured.")
    response = supabase.table("activity_log").select("*").order("created_at", desc=True).limit(limit).execute()
    return response.data or []


@router.post("/telegram/broadcast", summary="Broadcast a message to Telegram channel")
async def telegram_broadcast(request: TelegramBroadcastRequest):
    logger.info(f"Broadcasting to Telegram: Prediction {request.prediction.get('home_team')} vs {request.prediction.get('away_team')}, Value: {request.valueBet.get('selection')}")
    return {"success": True, "message": "Broadcast simulated successfully."}


# --- Bet Endpoints ---
@router.get("/bets/user/{user_id}", summary="Get bets for a specific user")
async def get_user_bets(user_id: str):
    if not supabase:
        raise HTTPException(status_code=503, detail="Database not configured.")
    response = supabase.table("user_bets").select("*").eq("user_id", user_id).order("created_at", desc=True).execute()
    return response.data or []


@router.post("/bets/record", summary="Record a user's bet")
async def record_bet(request: BetRecordRequest):
    if not supabase:
        raise HTTPException(status_code=503, detail="Database not configured.")
    bet_data = {
        "user_id": request.user_id,
        "match_id": request.match_id,
        "market": request.market,
        "selection": request.selection,
        "odds": request.odds,
        "stake": request.stake,
        "potential_win": request.odds * request.stake,
        "status": "pending",
        "created_at": datetime.now().isoformat()
    }
    response = supabase.table("user_bets").insert(bet_data).execute()
    if response.data:
        return {"success": True, "message": "Bet recorded successfully!", "data": response.data[0]}
    else:
        raise HTTPException(status_code=500, detail="Failed to record bet.")


# --- Acca Endpoints ---
@router.post("/accas/record", summary="Record a user's accumulator bet")
async def record_acca(request: AccaRecordRequest):
    if not supabase:
        raise HTTPException(status_code=503, detail="Database not configured.")
    acca_data = {
        "user_id": request.user_id,
        "selections_json": [s.dict() for s in request.selections],
        "total_odds": request.total_odds,
        "stake": request.stake,
        "potential_return": request.potential_return,
        "bookmaker": request.bookmaker,
        "created_at": datetime.now().isoformat(),
        "status": "pending"
    }
    response = supabase.table("accas").insert(acca_data).execute()
    if response.data:
        return {"success": True, "message": "Acca recorded successfully!", "data": response.data[0]}
    else:
        raise HTTPException(status_code=500, detail="Failed to record acca.")


# --- External API Endpoints ---
@router.get("/search/teams", summary="Search for teams")
async def search_teams_ext(q: str):
    if not football_client:
        raise HTTPException(status_code=503, detail="Football API not configured.")
    return await football_client.search_teams(q)


@router.get("/search/players", summary="Search for players")
async def search_players_ext(q: str):
    if not football_client:
        raise HTTPException(status_code=503, detail="Football API not configured.")
    return await football_client.search_players(q)


@router.get("/teams/{team_id}/detail", summary="Get team details from external API")
async def get_team_detail_ext(team_id: int):
    if not football_client:
        raise HTTPException(status_code=503, detail="Football API not configured.")
    return await football_client.get_team_detail(team_id)


@router.get("/leagues", summary="List all leagues from external API")
async def list_leagues_ext():
    if not football_client:
        raise HTTPException(status_code=503, detail="Football API not configured.")
    return await football_client.list_leagues()


@router.get("/leagues/{league_id}/detail", summary="Get league details from external API")
async def get_league_detail_ext(league_id: int):
    if not football_client:
        raise HTTPException(status_code=503, detail="Football API not configured.")
    return await football_client.get_league_detail(league_id)


@router.get("/search/leagues", summary="Search for leagues in external API")
async def search_leagues_ext(q: str):
    if not football_client:
        raise HTTPException(status_code=503, detail="Football API not configured.")
    return await football_client.search_leagues(q)


@router.get("/matches", summary="Get matches by date from external API")
async def get_matches_by_date_ext(date: str):
    if not football_client:
        raise HTTPException(status_code=503, detail="Football API not configured.")
    return await football_client.get_matches_by_date(date)


@router.get("/odds/{event_id}", summary="Get odds by event ID from external API")
async def get_odds_by_event_id_ext(event_id: int):
    if not football_client:
        raise HTTPException(status_code=503, detail="Football API not configured.")
    res = await football_client.get_odds_by_event_id(event_id)

    # Initialize with sensible default/fallback odds structure (market average approx)
    processed_odds = {
        "bet9ja": {"home_win": 1.95, "draw": 3.40, "away_win": 4.10, "booking_prefix": "B9"},
        "sportybet": {"home_win": 1.98, "draw": 3.45, "away_win": 4.05, "booking_prefix": "SB"},
        "1xbet": {"home_win": 2.01, "draw": 3.50, "away_win": 3.95, "booking_prefix": "1X"},
        "default": {"home_win": 1.90, "draw": 3.30, "away_win": 4.20, "booking_prefix": "FE"}
    }

    if res.get('response'):
        try:
            # We try to find a reliable bookmaker like Bet365 or 1xBet
            bookmakers = res['response'][0].get('bookmakers', [])
            found_odds = False
            for bm in bookmakers:
                if bm['name'] in ('Bet365', '1xBet', 'Marathonbet', 'William Hill', '888Sport', 'Unibet'):
                    bets = bm.get('bets', [])
                    for bet in bets:
                        if bet['name'] == 'Match Winner':
                            vals = {v['value']: v['odd'] for v in bet['values']}
                            current_odds = {
                                "home_win": float(vals.get('Home', 1.90)),
                                "draw": float(vals.get('Draw', 3.30)),
                                "away_win": float(vals.get('Away', 4.20)),
                                "booking_prefix": "FE"
                            }
                            processed_odds["default"] = current_odds
                            # Use found odds for local bookmakers as well if no specific ones found
                            for bkey in ["bet9ja", "sportybet", "1xbet"]:
                                processed_odds[bkey] = current_odds.copy()
                                processed_odds[bkey]["booking_prefix"] = bkey[:2].upper()
                            found_odds = True
                            break
                if found_odds: break
        except Exception as e:
            logger.error(f"Error processing odds for event {event_id}: {e}")

    if not res.get('response') or not found_odds:
         logger.warning(f"No live odds found for event {event_id}. Returning sensible average defaults.")

    return processed_odds


@router.get("/stats/{event_id}", summary="Get statistics by event ID from external API")
async def get_stats_by_event_id_ext(event_id: int):
    if not football_client:
        raise HTTPException(status_code=503, detail="Football API not configured.")
    return await football_client.get_stats_by_event_id(event_id)


@router.get("/h2h", summary="Get head-to-head between two teams")
async def get_h2h(team1_id: int, team2_id: int):
    if not football_client:
        raise HTTPException(status_code=503, detail="Football API not configured.")
    return await football_client.get_h2h(team1_id, team2_id)


@router.get("/standings/{league_id}", summary="Get league standings")
async def get_standings(league_id: int):
    if not football_client:
        raise HTTPException(status_code=503, detail="Football API not configured.")
    return await football_client.get_standings(league_id)


@router.get("/teams/{team_id}/players", summary="List all players for a team")
async def list_players_by_team(team_id: int):
    if not football_client:
        raise HTTPException(status_code=503, detail="Football API not configured.")
    return await football_client.list_players_by_team(team_id)


@router.get("/players/{player_id}", summary="Get player details")
async def get_player_detail(player_id: int):
    if not football_client:
        raise HTTPException(status_code=503, detail="Football API not configured.")
    return await football_client.get_player_detail(player_id)


# --- Include Router ---
app.include_router(router)


# --- Static File Serving (Production) ---
if os.path.exists("dist"):
    app.mount("/", StaticFiles(directory="dist", html=True), name="static")
    
    @app.exception_handler(404)
    async def not_found_exception_handler(request, exc):
        if not request.url.path.startswith("/api"):
            return FileResponse("dist/index.html")
        return JSONResponse(status_code=404, content={"message": "Not found"})
else:
    logger.info("Frontend 'dist' directory not found. Static file serving is disabled.")
