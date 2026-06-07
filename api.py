from fastapi import APIRouter, FastAPI, HTTPException, Request, Response
from fastapi.middleware.cors import CORSMiddleware
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
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

from predictor import FootyEdgePredictor
from football_api_client import FootballAPIClient
from football_data_org_client import FootballDataOrgClient
from football_router import FootballRouter
from agents.strategy_agent import StrategyAgent

# --- App Setup ---
app = FastAPI(
    title="FootyEdge AI - Production Betting Analysis",
    version="3.0.0",
    description="Provides sophisticated, production-ready match predictions and betting analysis."
)

# I'm updating the ALLOWED_ORIGINS to be more robust
ALLOWED_ORIGINS = [
    "https://footyedge-ai.onrender.com",
    "https://footy-edge-ai.vercel.app",
    "http://localhost:5173",
    "http://localhost:3000",
    "http://localhost:8000",
    "http://127.0.0.1:5173",
    "http://127.0.0.1:3000",
    "http://127.0.0.1:8000",
    "*" # Temporary wildcard to confirm connectivity
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=False, # Must be False if "*" is in origins
    allow_methods=["*"],
    allow_headers=["*"],
)

router = APIRouter(prefix="/api")
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# --- Environment Variable Checks & Client Initialization ---
supabase_url = os.environ.get("SUPABASE_URL") or os.environ.get("VITE_SUPABASE_URL")
supabase_key = (
    os.environ.get("SUPABASE_SERVICE_KEY") or 
    os.environ.get("SUPABASE_KEY") or 
    os.environ.get("SUPABASE_ANON_KEY") or
    os.environ.get("VITE_SUPABASE_ANON_KEY")
)
rapidapi_key = os.environ.get("RAPIDAPI_KEY") or os.environ.get("RAPID_API_KEY")
fd_org_key = os.environ.get("FOOTBALL_DATA_API_KEY") or os.environ.get("FOOTBALL_DATA_KEY")
sportradar_key = os.environ.get("SPORTRADAR_API_KEY")

if not supabase_url or not supabase_key:
    logger.warning("Supabase environment variables not found. Database client will not be available.")
    supabase = None
else:
    try:
        supabase = create_client(supabase_url, supabase_key)
    except Exception as e:
        logger.error(f"Failed to initialize Supabase client: {e}")
        supabase = None

# Initialize clients even if keys are missing from env, as they might have internal fallbacks or handles
fd_client = FootballDataOrgClient() if fd_org_key else None
rapid_client = FootballAPIClient() # This one has an internal fallback

# football_client remains for legacy compatibility, now using the router
football_client = FootballRouter(fd_client, rapid_client)

predictor = FootyEdgePredictor()
strategy_agent = StrategyAgent()

@app.middleware("http")
async def log_requests(request, call_next):
    logger.info(f"API Request: {request.method} {request.url.path}")
    return await call_next(request)

if not rapidapi_key:
    logger.warning("RAPIDAPI_KEY is not set. RapidAPI features disabled.")
if not fd_org_key:
    logger.warning("FOOTBALL_DATA_API_KEY is not set. Football-Data.org features disabled.")
if not sportradar_key:
    logger.warning("SPORTRADAR_API_KEY is not set. Sportradar features disabled.")
if not supabase_url or not supabase_key:
    logger.warning("Supabase environment variables are not set. Database features will be unavailable.")

@router.get("/health")
async def health_check():
    return {
        "status": "operational",
        "supabase_connected": supabase is not None,
        "football_api_configured": football_client is not None,
        "rapid_api_key_present": rapidapi_key is not None,
        "football_data_key_present": fd_org_key is not None,
        "environment": "production" if os.environ.get("RENDER") or os.environ.get("VERCEL") else "development"
    }

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

class StrategyAnalyzeRequest(BaseModel):
    text: str
    stake: float = 1000

@router.post("/analyze-strategy", summary="Analyze a natural language betting strategy")
async def analyze_strategy_endpoint(req: StrategyAnalyzeRequest):
    selections = strategy_agent.parse_strategy(req.text)
    analysis = strategy_agent.analyze(selections, req.stake)
    return analysis

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
        "rapidapi": "configured" if rapidapi_key else "missing (using fallback)",
        "football_data_org": "configured" if fd_org_key else "missing",
        "sportradar": "configured" if sportradar_key else "missing",
        "external_resources": ["365scores", "sofascore"],
        "router_active": "yes" if isinstance(football_client, FootballRouter) else "no"
    }


@app.get("/health", summary="Root health check")
async def root_health():
    return await health_check()

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
    except Exception as e:
        logger.error(f"Error in scan_value_bets: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# --- Database Endpoints ---
@router.get("/dashboard/stats", summary="Get overall platform statistics")
async def get_dashboard_stats():
    total_preds = 0
    active_value = 0
    accuracy = 0.0

    if supabase:
        try:
            preds_res = supabase.table("predictions").select("id", count="exact").execute()
            total_preds = preds_res.count or 0

            value_res = supabase.table("value_bets").select("id", count="exact").eq("status", "active").execute()
            active_value = value_res.count or 0

            try:
                settled_res = supabase.table("predictions").select("best_bet_selection, actual_result").not_.is_("actual_result", "null").execute()
                if settled_res.data:
                    correct = sum(1 for p in settled_res.data if p.get('best_bet_selection') == p.get('actual_result'))
                    accuracy = (correct / len(settled_res.data)) * 100
                else:
                    accuracy = 0.0
            except Exception as schema_err:
                logger.warning(f"Accuracy calc failed: {schema_err}")
                accuracy = 0.0
        except Exception as e:
            logger.error(f"Error fetching dashboard stats: {e}")

    return {
        "total_predictions": total_preds,
        "active_value_bets": active_value,
        "ai_accuracy": f"{round(accuracy, 1)}%" if accuracy > 0 else "N/A"
    }

@router.get("/teams", summary="Get all teams from database")
async def get_teams(league: Optional[str] = None):
    if not supabase:
        raise HTTPException(status_code=503, detail="Database not configured.")
    query = supabase.table("teams").select("*")
    if league:
        query = query.eq("league_name", league)
    response = query.order("name").execute()
    return response.data or []


@router.get("/teams/{team_id}", summary="Get detailed team info from DB")
async def get_team_detail_db(team_id: int):
    if not supabase:
        raise HTTPException(status_code=503, detail="Database not configured.")
    
    # Get team basic info
    team_res = supabase.table("teams").select("*").eq("id", team_id).single().execute()
    if not team_res.data:
        raise HTTPException(status_code=404, detail="Team not found")
    
    # Get players
    players_res = supabase.table("players").select("*").eq("team_id", team_id).execute()
    
    return {
        "team": team_res.data,
        "players": players_res.data or []
    }


@router.get("/daily-picks", summary="Get AI predictions for a date range")
async def get_daily_picks(from_date: Optional[str] = None, to_date: Optional[str] = None):
    if not from_date:
        from_date = datetime.now().strftime("%Y-%m-%d")
    if not to_date:
        to_date = from_date

    try:
        # 1. Fetch matches for the range
        matches_data = await football_client.get_matches_by_date(from_date, to_date)
        match_list = matches_data.get('response', [])
        
        # Note: Matches are already sorted by league priority in football_client
        
        results = []
        # Increase limit to 30 to show more popular games
        for m in match_list[:30]: 
            home = m['teams']['home']['name']
            away = m['teams']['away']['name']
            
            # Check if prediction exists in DB (if connected)
            pred_data = None
            if supabase:
                try:
                    pred_res = supabase.table("predictions").select("*").eq("home_team", home).eq("away_team", away).order("created_at", desc=True).limit(1).execute()
                    pred_data = pred_res.data
                except Exception as db_err:
                    logger.warning(f"DB Prediction lookup failed: {db_err}")
            
            if pred_data:
                results.append(pred_data[0])
            else:
                try:
                    # Provide default odds for daily picks generator
                    default_odds = {
                        "home_win": 1.90, "draw": 3.30, "away_win": 4.20,
                        "Over 2.5": 1.90, "Under 2.5": 1.90,
                        "BTTS Yes": 1.80, "BTTS No": 2.00
                    }
                    # Attempt to generate new prediction
                    prediction = await predictor.predict_match(home, away, default_odds)
                    results.append(prediction)
                except Exception as e:
                    logger.error(f"Failed to predict {home} vs {away}: {e}")

        return results
    except Exception as e:
        logger.error(f"Daily picks failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


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


# --- Premium Endpoints ---
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
        raise HTTPException(status_code=503, detail="Clients not configured. Check environment variables.")
    
    # Predefined major league IDs (using RapidAPI IDs as default)
    major_league_ids = [47, 87, 54, 55, 53, 42, 73, 342] # PL, LaLiga, Bundesliga, Serie A, Ligue 1, UCL, UEL, NPFL
    
    try:
        leagues_data = await football_client.list_leagues()
        # Safety check: if leagues_data is None or malformed
        if not leagues_data or 'response' not in leagues_data:
            logger.warning("list_leagues returned empty/invalid data. Using major_league_ids only.")
            leagues_to_sync = major_league_ids
        else:
            league_items = leagues_data.get('response', [])
            found_league_ids = [item.get('league', {}).get('id') for item in league_items if item.get('league', {}).get('id')]
            leagues_to_sync = list(set(found_league_ids + major_league_ids))[:20]
        
        all_teams = []
        for league_id in leagues_to_sync:
            logger.info(f"Fetching teams for league ID: {league_id}")
            try:
                teams_data = await football_client.get_teams_by_league(league_id)
                if teams_data and 'response' in teams_data:
                    for team_item in teams_data['response']:
                        team_info = team_item.get('team', {})
                        if team_info.get('id') and team_info.get('name'):
                            all_teams.append({
                                "id": str(team_info['id']),
                                "name": team_info['name'],
                                "country": team_info.get('country') or 'Unknown',
                                "league_name": team_item.get('league', {}).get('name', 'Unknown'),
                                "logo_url": team_info.get('crest', team_info.get('logo'))
                            })
            except Exception as e:
                logger.error(f"Failed to fetch teams for league {league_id}: {e}")
                continue # Proceed to next league
            await asyncio.sleep(0.5) 
        
        if not all_teams:
            return JSONResponse(status_code=500, content={"status": "error", "detail": "No teams found from external API."})
        
        unique_teams = {t['name']: t for t in all_teams}.values()
        
        upsert_response = supabase.table("teams").upsert(list(unique_teams), on_conflict="name").execute()
        return {"status": "success", "synced_count": len(upsert_response.data) if upsert_response.data else 0}
    except Exception as e:
        logger.error(f"Sync teams failed: {e}")
        return JSONResponse(status_code=500, content={"status": "error", "detail": f"Sync failed: {str(e)}"})


@router.post("/admin/sync-players", summary="Sync players for existing teams in database")
async def sync_players():
    if not football_client or not supabase:
        raise HTTPException(status_code=503, detail="Clients not configured. Check environment variables.")
    
    try:
        # Get all teams from DB
        teams_res = supabase.table("teams").select("id, name").execute()
        teams = teams_res.data or []
        
        if not teams:
            return JSONResponse(status_code=400, content={"status": "error", "detail": "No teams found in database. Sync teams first."})

        total_synced = 0
        for team in teams:
            logger.info(f"Syncing players for {team['name']} (ID: {team['id']})")
            try:
                players_data = await football_client.list_players_by_team(team['id'])
                
                if players_data and 'response' in players_data:
                    player_list = players_data.get('response', [])
                    if isinstance(player_list, dict) and 'players' in player_list: # Some formats
                        player_list = player_list['players']
                    
                    db_players = []
                    for p in player_list[:25]: # Limit per team
                        db_players.append({
                            "external_id": str(p.get('id')),
                            "team_id": team['id'],
                            "name": p.get('name'),
                            "position": p.get('position'),
                            "nationality": p.get('country') or p.get('nationality'),
                            "age": p.get('age'),
                            "photo_url": f"https://images.fotmob.com/image_resources/playerimages/{p.get('id')}.png" if p.get('id') else None
                        })
                    
                    if db_players:
                        supabase.table("players").upsert(db_players, on_conflict="name, team_id").execute()
                        total_synced += len(db_players)
            except Exception as e:
                logger.error(f"Failed to sync players for team {team['id']}: {e}")
            
            await asyncio.sleep(0.4) # Avoid rate limiting
            
        return {"status": "success", "synced_count": total_synced}
    except Exception as e:
        logger.error(f"Sync players failed: {e}")
        return JSONResponse(status_code=500, content={"status": "error", "detail": f"Sync failed: {str(e)}"})


@router.post("/admin/seed-database", summary="Seed the database with initial data")
async def seed_database():
    if not supabase:
        raise HTTPException(status_code=503, detail="Database not configured.")
    
    initial_teams = [
        {"id": 10260, "name": "Manchester United", "country": "England", "league_name": "Premier League", "logo_url": "https://images.fotmob.com/image_resources/logo/teamlogo/10260.png"},
        {"id": 10261, "name": "Newcastle", "country": "England", "league_name": "Premier League", "logo_url": "https://images.fotmob.com/image_resources/logo/teamlogo/10261.png"},
        {"id": 8650, "name": "Liverpool", "country": "England", "league_name": "Premier League", "logo_url": "https://images.fotmob.com/image_resources/logo/teamlogo/8650.png"},
        {"id": 9825, "name": "Arsenal", "country": "England", "league_name": "Premier League", "logo_url": "https://images.fotmob.com/image_resources/logo/teamlogo/9825.png"},
        {"id": 8456, "name": "Manchester City", "country": "England", "league_name": "Premier League", "logo_url": "https://images.fotmob.com/image_resources/logo/teamlogo/8456.png"},
        {"id": 8634, "name": "Barcelona", "country": "Spain", "league_name": "La Liga", "logo_url": "https://images.fotmob.com/image_resources/logo/teamlogo/8634.png"},
        {"id": 8633, "name": "Real Madrid", "country": "Spain", "league_name": "La Liga", "logo_url": "https://images.fotmob.com/image_resources/logo/teamlogo/8633.png"},
    ]
    
    try:
        response = supabase.table("teams").upsert(initial_teams, on_conflict="name").execute()
        return {"status": "success", "message": "Database seeded.", "count": len(response.data or [])}
    except Exception as e:
        logger.error(f"Seeding failed: {e}")
        return JSONResponse(status_code=500, content={"status": "error", "detail": f"Seeding failed: {str(e)}"})


@router.get("/admin/stats", summary="Get admin dashboard statistics")
async def get_admin_stats():
    if not supabase:
        raise HTTPException(status_code=503, detail="Database not configured.")
    
    users_response = supabase.table("profiles").select("id", count="exact").execute()
    premium_users_response = supabase.table("profiles").select("id", count="exact").eq("is_premium", True).execute()
    
    total_premium = premium_users_response.count or 0
    estimated_daily_revenue = (total_premium * 35000) / 30
    
    try:
        logs_response = supabase.table("agent_logs").select("success").order("created_at", desc=True).limit(100).execute()
        if logs_response.data:
            success_count = sum(log['success'] for log in logs_response.data)
            bot_health = (success_count / len(logs_response.data)) * 100
        else:
            bot_health = 100.0
    except Exception:
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
    try:
        response = supabase.table("activity_log").select("*").order("created_at", desc=True).limit(limit).execute()
        return response.data or []
    except Exception:
        return []


@router.get("/dashboard/stats", summary="Get overall platform statistics")
async def get_dashboard_stats():
    total_preds = 0
    active_value = 0
    accuracy = 0.0

    if supabase:
        try:
            preds_res = supabase.table("predictions").select("id", count="exact").execute()
            total_preds = preds_res.count or 0

            value_res = supabase.table("value_bets").select("id", count="exact").eq("status", "active").execute()
            active_value = value_res.count or 0

            # Calculate accuracy from settled predictions
            # actual_result should match best_bet_selection for a 'win'
            try:
                # Use a safer select, or handle if the column doesn't exist
                settled_res = supabase.table("predictions").select("best_bet_selection, actual_result").not_.is_("actual_result", "null").execute()
                if settled_res.data:
                    correct = sum(1 for p in settled_res.data if p.get('best_bet_selection') == p.get('actual_result'))
                    accuracy = (correct / len(settled_res.data)) * 100
                else:
                    accuracy = 0.0
            except Exception as schema_err:
                # If the column doesn't exist, we just skip accuracy calculation instead of erroring
                if "actual_result" in str(schema_err) or "column" in str(schema_err):
                    logger.info("Accuracy calculation skipped: column actual_result missing.")
                else:
                    logger.warning(f"Accuracy calc failed: {schema_err}")
                accuracy = 0.0
        except Exception as e:
            logger.error(f"Error fetching dashboard stats: {e}")

    return {
        "total_predictions": total_preds,
        "active_value_bets": active_value,
        "ai_accuracy": f"{round(accuracy, 1)}%" if accuracy > 0 else "N/A"
    }


@router.get("/external/365scores/stats", summary="Get detailed stats from 365Scores")
async def get_365scores_stats(home_team: str, away_team: str):
    try:
        game_id = await predictor.three_six_five_client.find_match_id(home_team, away_team)
        if not game_id:
            return {"error": "Match not found on 365Scores"}
        
        data = await predictor.three_six_five_client.get_match_details(game_id)
        if not data:
            return {"error": "Failed to retrieve match details"}
            
        return {
            "game_id": game_id,
            "xg": predictor.three_six_five_client.extract_xg(data),
            "stats": data.get('games', [{}])[0].get('stats', []),
            "incidents": data.get('games', [{}])[0].get('incidents', []),
            "shot_map": data.get('chartEvents', {}).get('events', [])
        }
    except Exception as e:
        logger.error(f"Error fetching 365Scores stats: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/external/365scores", summary="Get 365scores external link")
async def get_365scores_link(home_team: Optional[str] = None, away_team: Optional[str] = None):
    """
    Returns the 365scores URL. If home_team and away_team are provided, 
    it returns a search URL for the match.
    """
    if home_team and away_team:
        return {"url": football_client.get_365scores_match_url(home_team, away_team)}
    return {"url": "https://www.365scores.com/football"}


@router.get("/external/sofascore/h2h", summary="Get deep H2H from Sofascore")
async def get_sofascore_h2h(team1_id: int, team2_id: int):
    """
    Fetches head-to-head history using Sofascore IDs.
    """
    if not football_client:
        raise HTTPException(status_code=503, detail="Football API not configured.")
    
    res = await football_client.sofascore.get_h2h_events(team1_id, team2_id)
    if not res:
        raise HTTPException(status_code=404, detail="H2H data not found on Sofascore.")
    return res


@router.get("/external/sofascore/search/teams", summary="Search Sofascore teams")
async def search_sofascore_teams(q: str):
    if not football_client:
        raise HTTPException(status_code=503, detail="Football API not configured.")
    return await football_client.sofascore.search_teams(q)


@router.get("/external/sofascore/search/players", summary="Search Sofascore players")
async def search_sofascore_players(q: str):
    if not football_client:
        raise HTTPException(status_code=503, detail="Football API not configured.")
    return await football_client.sofascore.search_players(q)


@router.post("/telegram/broadcast", summary="Broadcast a message to Telegram channel")
async def telegram_broadcast(request: TelegramBroadcastRequest):
    bot_token = os.environ.get("TELEGRAM_BOT_TOKEN")
    chat_id = os.environ.get("TELEGRAM_CHAT_ID", "@footyedge_signals")

    if not bot_token:
        logger.warning("TELEGRAM_BOT_TOKEN not set. Simulating broadcast.")
        return {"success": True, "message": "Simulated: Bot token missing."}

    message = f"⚽ *{request.prediction.get('home_team')} vs {request.prediction.get('away_team')}*\n\n"
    message += f"🎯 *Value Bet Found!*\n"
    message += f"Selection: {request.valueBet.get('selection')}\n"
    message += f"Odds: {request.valueBet.get('odds')}\n"

    if request.isPremium:
        message = "💎 *PREMIUM SIGNAL*\n" + message
        chat_id = os.environ.get("TELEGRAM_PREMIUM_CHAT_ID", "@footyedge_premium")

    try:
        async with httpx.AsyncClient() as client:
            res = await client.post(
                f"https://api.telegram.org/bot{bot_token}/sendMessage",
                json={"chat_id": chat_id, "text": message, "parse_mode": "Markdown"}
            )
            if res.status_code == 200:
                return {"success": True, "message": "Broadcast sent successfully!"}
            else:
                logger.error(f"Telegram API error: {res.text}")
                return {"success": False, "error": res.text}
    except Exception as e:
        logger.error(f"Failed to broadcast: {e}")
        return {"success": False, "error": str(e)}


# --- Bet Endpoints ---
@router.get("/bets/user/{user_id}", summary="Get bets for a specific user")
async def get_user_bets(user_id: str):
    if not supabase:
        raise HTTPException(status_code=503, detail="Database not configured.")
    response = supabase.table("user_bets").select("*").eq("user_id", user_id).order("created_at", desc=True).execute()
    return response.data or []


@router.get("/players", summary="Get all players from database")
async def get_players(team_id: Optional[int] = None, limit: int = 50):
    if not supabase:
        raise HTTPException(status_code=503, detail="Database not configured.")
    query = supabase.table("players").select("*, teams(name, logo_url)")
    if team_id:
        query = query.eq("team_id", team_id)
    response = query.order("name").limit(limit).execute()
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
async def get_matches_by_date_ext(from_date: Optional[str] = None, to_date: Optional[str] = None, date: Optional[str] = None):
    if not football_client:
        raise HTTPException(status_code=503, detail="Football API not configured.")
    
    # Support legacy 'date' param or new from_date/to_date
    f_date = from_date or date or datetime.now().strftime("%Y-%m-%d")
    t_date = to_date or f_date
    
    # Validation: Ensure date range is valid
    try:
        if datetime.strptime(f_date, "%Y-%m-%d") > datetime.strptime(t_date, "%Y-%m-%d"):
            # Swap if wrong order
            f_date, t_date = t_date, f_date
    except ValueError:
        logger.warning(f"Invalid date format received: {f_date} or {t_date}")
    
    return await football_client.get_matches_by_date(f_date, t_date)


@router.get("/odds/{event_id}", summary="Get odds by event ID from external API")
async def get_odds_by_event_id_ext(event_id: int):
    if not football_client:
        raise HTTPException(status_code=503, detail="Football API not configured.")
    res = await football_client.get_odds_by_event_id(event_id)

    # Initialize with empty structure - no hardcoded fallbacks
    processed_odds = {
        "bet9ja": None,
        "sportybet": None,
        "1xbet": None,
        "default": None
    }

    found_odds = False
    if res.get('response'):
        try:
            # We try to find a reliable bookmaker like Bet365 or 1xBet
            bookmakers = res['response'][0].get('bookmakers', [])
            for bm in bookmakers:
                if bm['name'] in ('Bet365', '1xBet', 'Marathonbet', 'William Hill', '888Sport', 'Unibet'):
                    bets = bm.get('bets', [])
                    for bet in bets:
                        if bet['name'] == 'Match Winner':
                            vals = {v['value']: v['odd'] for v in bet['values']}
                            current_odds = {
                                "home_win": float(vals.get('Home', 1.0)),
                                "draw": float(vals.get('Draw', 1.0)),
                                "away_win": float(vals.get('Away', 1.0)),
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

    if not found_odds:
         logger.warning(f"No live odds found for event {event_id}. Real-time data unavailable.")

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
    @app.exception_handler(404)
    async def not_found_exception_handler(request, exc):
        if not request.url.path.startswith("/api"):
            return FileResponse("dist/index.html")
        return JSONResponse(status_code=404, content={"message": "Not found"})

    app.mount("/", StaticFiles(directory="dist", html=True), name="static")
else:
    logger.info("Frontend 'dist' directory not found. Static file serving is disabled.")
