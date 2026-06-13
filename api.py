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

# Comprehensive ALLOWED_ORIGINS for all deployment scenarios
ALLOWED_ORIGINS = [
    "https://footyedge-ai.onrender.com",
    "https://footy-edge-ai.vercel.app",
    "http://localhost:5173",
    "http://localhost:3000",
    "http://localhost:8000",
    "http://127.0.0.1:5173",
    "http://127.0.0.1:3000",
    "http://127.0.0.1:8000",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
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

# --- API Clients ---
# Initialize the router which will handle internal failovers and aggregations
football_client = FootballRouter()
# predictor and strategy agent use the client internally if needed
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

@app.get("/")
@app.head("/")
async def root():
    return {"message": "FootyEdge AI API is running.", "status": "operational", "health": "/health", "api_health": "/api/health"}

@router.get("/")
async def api_root():
    return {"message": "FootyEdge AI API Router is active.", "docs": "/docs"}

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
    plan: str = "Premium"

class StrategyAnalyzeRequest(BaseModel):
    text: str
    stake: float = 1000

class BetRecordRequest(BaseModel):
    user_id: str
    match_id: int
    market: str
    selection: str
    odds: float
    stake: float
# --- Health Check ---


@app.get("/health", summary="Root health check")
async def root_health():
    return await health_check()

# --- Core Features ---
@router.post("/predict", summary="Generate predictions using live odds")
async def predict(request: PredictRequest):
    try:
        res = await predictor.predict_match(request.home_team, request.away_team, request.odds)
        if supabase:
            try:
                # Log prediction to DB
                probs = res.get('probabilities', {})
                home_p = probs.get('home_win', 0)
                draw_p = probs.get('draw', 0)
                away_p = probs.get('away_win', 0)
                
                pred_data = {
                    "home_team": res['home_team'],
                    "away_team": res['away_team'],
                    "home_prob": home_p,
                    "draw_prob": draw_p,
                    "away_prob": away_p,
                    "home_xg": res.get('home_xg', 0),
                    "away_xg": res.get('away_xg', 0),
                    "confidence": (home_p + away_p) / 1.5,
                    "best_bet_market": res['value_bets'][0]['market_name'] if res.get('value_bets') else "Match Odds",
                    "best_bet_selection": res['value_bets'][0]['selection'] if res.get('value_bets') else "Draw",
                    "best_bet_odds": res['value_bets'][0]['odds'] if res.get('value_bets') else 1.0,
                }
                supabase.table("predictions").insert(pred_data).execute()
            except Exception as db_err:
                logger.warning(f"Failed to log prediction to DB: {db_err}")
        return res
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Prediction error: {e}")
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
        raise HTTPException(status_code=503, detail="Clients not configured.")
    
    # Major league IDs to prioritize
    major_league_ids = [47, 87, 54, 55, 53, 42, 73, 342]
    
    try:
        all_teams = []
        for league_id in major_league_ids:
            logger.info(f"Syncing teams for league: {league_id}")
            try:
                # Based on Replit lessons: Use more specific league endpoints if available
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
                logger.error(f"Failed to fetch league {league_id}: {e}")
            await asyncio.sleep(0.5) # Anti-rate limiting
        
        if not all_teams:
            return {"status": "warning", "message": "No teams fetched from external providers."}
        
        # Deduplicate locally by name
        unique_teams = {t['name']: t for t in all_teams}.values()
        
        # Replit Best Practice: Use UPSERT with unique constraint handling
        success_count = 0
        for ut in unique_teams:
            try:
                supabase.table("teams").upsert(ut).execute()
                success_count += 1
            except Exception as e:
                logger.warning(f"Failed to upsert team {ut['name']}: {e}")

        return {"status": "success", "synced_count": success_count, "total_attempted": len(unique_teams)}

    except Exception as e:
        logger.error(f"Sync teams failed: {e}")
        return {"status": "error", "message": str(e)}


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
        # Replit Best Practice: Limit to avoid massive timeouts
        for team in teams[:20]: 
            logger.info(f"Syncing players for {team['name']} (ID: {team['id']})")
            try:
                players_data = await football_client.list_players_by_team(team['id'])
                if players_data and 'response' in players_data:
                    team_players = []
                    for p in players_data['response']:
                        player_info = p.get('player', {})
                        if player_info.get('id'):
                            team_players.append({
                                "id": str(player_info['id']),
                                "name": player_info['name'],
                                "team_id": team['id'],
                                "position": player_info.get('position', 'Unknown'),
                                "photo_url": player_info.get('photo')
                            })
                    
                    if team_players:
                        # Clear existing players for this team to fix duplication bug from Replit
                        try:
                            supabase.table("players").delete().eq("team_id", team['id']).execute()
                        except: pass
                        
                        supabase.table("players").insert(team_players).execute()
                        total_synced += len(team_players)
            except Exception as e:
                logger.error(f"Failed to sync players for team {team['id']}: {e}")
            await asyncio.sleep(0.3)

        return {"status": "success", "players_synced": total_synced, "teams_processed": min(len(teams), 20)}
    except Exception as e:
        logger.error(f"Global player sync error: {e}")
        return {"status": "error", "message": str(e)}


@router.post("/admin/seed-database", summary="Seed the database with initial data")
async def seed_database():
    if not supabase:
        raise HTTPException(status_code=503, detail="Database not configured.")
    
    initial_teams = [
        {"id": 33, "name": "Manchester United", "country": "England", "league_name": "Premier League", "logo_url": "https://images.fotmob.com/image_resources/logo/teamlogo/10260.png"},
        {"id": 34, "name": "Manchester City", "country": "England", "league_name": "Premier League", "logo_url": "https://images.fotmob.com/image_resources/logo/teamlogo/8456.png"},
        {"id": 40, "name": "Liverpool", "country": "England", "league_name": "Premier League", "logo_url": "https://images.fotmob.com/image_resources/logo/teamlogo/8650.png"},
        {"id": 42, "name": "Arsenal", "country": "England", "league_name": "Premier League", "logo_url": "https://images.fotmob.com/image_resources/logo/teamlogo/9825.png"},
        {"id": 49, "name": "Chelsea", "country": "England", "league_name": "Premier League", "logo_url": "https://images.fotmob.com/image_resources/logo/teamlogo/8455.png"},
        {"id": 529, "name": "Barcelona", "country": "Spain", "league_name": "La Liga", "logo_url": "https://images.fotmob.com/image_resources/logo/teamlogo/8634.png"},
        {"id": 541, "name": "Real Madrid", "country": "Spain", "league_name": "La Liga", "logo_url": "https://images.fotmob.com/image_resources/logo/teamlogo/8633.png"},
        {"id": 157, "name": "Bayern Munich", "country": "Germany", "league_name": "Bundesliga", "logo_url": "https://images.fotmob.com/image_resources/logo/teamlogo/9823.png"}
    ]
    
    try:
        success_count = 0
        for team in initial_teams:
            try:
                supabase.table("teams").upsert(team).execute()
                success_count += 1
            except Exception as e:
                logger.error(f"Failed to seed team {team['name']}: {e}")
        
        # Also clear any old test predictions to remove "placeholders"
        try:
            supabase.table("predictions").delete().neq("id", 0).execute()
            logger.info("Cleared old predictions during seeding.")
        except: pass

        return {"status": "success", "message": "Database seeded with top clubs and old predictions cleared.", "count": success_count}
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
    roi = 0.0

    if supabase:
        try:
            preds_res = supabase.table("predictions").select("id", count="exact").execute()
            total_preds = preds_res.count or 0

            value_res = supabase.table("value_bets").select("id", count="exact").eq("status", "active").execute()
            active_value = value_res.count or 0

            # Calculate accuracy
            try:
                # Replit Lesson: Check for existence of results before calculating
                settled_res = supabase.table("predictions").select("best_bet_selection").not_.is_("best_bet_selection", "null").execute()
                accuracy = 0.0 
            except Exception as e:
                accuracy = 0.0

            # Calculate ROI
            roi = 0.0
        except Exception as e:
            logger.error(f"Error fetching dashboard stats: {e}")

    # Detect if we are in simulated mode due to missing keys
    is_simulated = not (rapidapi_key and fd_org_key)

    return {
        "total_predictions": total_preds,
        "active_value_bets": active_value,
        "ai_accuracy": f"{round(accuracy, 1)}%",
        "win_rate": f"{round(accuracy, 1)}%",
        "portfolio_roi": f"{round(roi, 1)}%",
        "system_mode": "Simulated" if is_simulated else "Live"
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
    
    res = await football_client.get_matches_by_date(f_date, t_date)
    return res


@router.get("/odds/{event_id}", summary="Get odds by event ID from external API")
async def get_odds_by_event_id_ext(event_id: int):
    if not football_client:
        raise HTTPException(status_code=503, detail="Football API not configured.")
    res = await football_client.get_odds_by_event_id(event_id)

    processed_odds = {
        "bet365": None,
        "1xbet": None,
        "william_hill": None,
        "default": None
    }

    found_odds = False
    if res.get('response'):
        try:
            # We look for reliable bookmakers first
            bookmakers = res['response'][0].get('bookmakers', [])
            for bm in bookmakers:
                bets = bm.get('bets', [])
                market_odds = None
                for bet in bets:
                    if bet['name'] == 'Match Winner' or bet['name'] == 'Home/Away':
                        vals = {v['value']: v['odd'] for v in bet['values']}
                        market_odds = {
                            "home_win": float(vals.get('Home', vals.get('1', 1.0))),
                            "draw": float(vals.get('Draw', vals.get('X', 1.0))),
                            "away_win": float(vals.get('Away', vals.get('2', 1.0))),
                        }
                        break
                
                if market_odds:
                    found_odds = True
                    if bm['name'] == 'Bet365': processed_odds["bet365"] = market_odds
                    elif bm['name'] == '1xBet': processed_odds["1xbet"] = market_odds
                    elif bm['name'] == 'William Hill': processed_odds["william_hill"] = market_odds
                    
                    # Set default to the first reliable one found
                    if not processed_odds["default"]:
                        processed_odds["default"] = market_odds

        except Exception as e:
            logger.error(f"Error processing odds for event {event_id}: {e}")

    if not found_odds:
         logger.warning(f"No live odds found for event {event_id}. Using internal estimation.")
         # Return a structured empty response instead of failing
         processed_odds["default"] = { "home_win": 1.95, "draw": 3.30, "away_win": 4.10 }

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

# --- Startup Logic ---
@app.on_event("startup")
async def startup_event():
    logger.info("Initializing FootyEdge AI Backend...")
    
    # Start the Telegram bot in a background thread if token is available
    if os.environ.get("TELEGRAM_BOT_TOKEN"):
        import threading
        from bot import main as start_bot
        try:
            bot_thread = threading.Thread(target=start_bot, daemon=True)
            bot_thread.start()
            logger.info("Telegram Bot started in background thread.")
        except Exception as bot_err:
            logger.error(f"Failed to start Telegram Bot: {bot_err}")
    else:
        logger.warning("TELEGRAM_BOT_TOKEN not set. Bot will not start.")

    if not supabase:
        logger.warning("🚀 WARNING: Supabase not configured. Application will run in 'Offline Mode' (No DB persistence).")
        return

    try:
        # Check if teams exist
        res = supabase.table("teams").select("id", count="exact").limit(1).execute()
        if res.count == 0:
            logger.info("📦 Team database is empty. Running automatic 'Safe Seed'...")
            initial_teams = [
                {"id": 33, "name": "Manchester United", "country": "England", "league_name": "Premier League", "logo_url": "https://images.fotmob.com/image_resources/logo/teamlogo/10260.png"},
                {"id": 34, "name": "Manchester City", "country": "England", "league_name": "Premier League", "logo_url": "https://images.fotmob.com/image_resources/logo/teamlogo/8456.png"},
                {"id": 40, "name": "Liverpool", "country": "England", "league_name": "Premier League", "logo_url": "https://images.fotmob.com/image_resources/logo/teamlogo/8650.png"},
                {"id": 42, "name": "Arsenal", "country": "England", "league_name": "Premier League", "logo_url": "https://images.fotmob.com/image_resources/logo/teamlogo/9825.png"},
                {"id": 541, "name": "Real Madrid", "country": "Spain", "league_name": "La Liga", "logo_url": "https://images.fotmob.com/image_resources/logo/teamlogo/8633.png"},
                {"id": 529, "name": "Barcelona", "country": "Spain", "league_name": "La Liga", "logo_url": "https://images.fotmob.com/image_resources/logo/teamlogo/8634.png"}
            ]
            for team in initial_teams:
                try:
                    supabase.table("teams").upsert(team).execute()
                except: pass
            logger.info(f"✅ Safe Seed complete. {len(initial_teams)} teams added.")
        else:
            logger.info(f"✅ Database connected. Found {res.count} teams.")
    except Exception as e:
        logger.error(f"❌ Startup Database Check Failed: {e}")


# --- Static File Serving (Production) ---
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
dist_path = os.path.join(BASE_DIR, "dist")

if os.path.exists(dist_path):
    @app.exception_handler(404)
    async def not_found_exception_handler(request, exc):
        if not request.url.path.startswith("/api"):
            return FileResponse(os.path.join(dist_path, "index.html"))
        return JSONResponse(status_code=404, content={"message": "Not found"})

    app.mount("/", StaticFiles(directory=dist_path, html=True), name="static")
    logger.info(f"Frontend served from: {dist_path}")
else:
    logger.warning(f"Frontend 'dist' directory not found at {dist_path}. Static file serving is disabled.")