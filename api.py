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
sr_key = os.environ.get("SPORTRADAR_API_KEY")

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
# For personal use, we solely use the Sportradar (soccer data) provider.
football_client = FootballAPIClient()
# predictor and strategy agent use the client internally if needed
predictor = FootyEdgePredictor(football_client=football_client)
strategy_agent = StrategyAgent()

@app.middleware("http")
async def log_requests(request, call_next):
    logger.info(f"API Request: {request.method} {request.url.path}")
    return await call_next(request)

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

class BetRecordRequest(BaseModel):
    user_id: str
    match_id: int
    market: str
    selection: str
    odds: float
    stake: float

# --- Health Check ---

@router.get("/health")
async def health_check():
    return {
        "status": "operational",
        "supabase_connected": supabase is not None,
        "football_api_configured": football_client is not None,
        "sportradar_key_present": sr_key is not None,
        "environment": "personal"
    }

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
                pred_data = {
                    "home_team": res['home_team'],
                    "away_team": res['away_team'],
                    "home_prob": res['home_prob'],
                    "draw_prob": res['draw_prob'],
                    "away_prob": res['away_prob'],
                    "home_xg": res['home_xg'],
                    "away_xg": res['away_xg'],
                    "confidence": (res['home_prob'] + res['away_prob']) / 1.5,
                    "best_bet_market": res['value_bets'][0]['market_name'] if res['value_bets'] else "Match Odds",
                    "best_bet_selection": res['value_bets'][0]['selection'] if res['value_bets'] else "Draw",
                    "best_bet_odds": res['value_bets'][0]['odds'] if res['value_bets'] else 1.0,
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

@router.post("/analyze-strategy", summary="Analyze a natural language betting strategy")
async def analyze_strategy_endpoint(req: StrategyAnalyzeRequest):
    selections = strategy_agent.parse_strategy(req.text)
    analysis = strategy_agent.analyze(selections, req.stake)
    return analysis

# --- Database Endpoints ---
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
                settled_res = supabase.table("predictions").select("best_bet_selection, actual_result").not_.is_("actual_result", "null").execute()
                if settled_res.data:
                    correct = sum(1 for p in settled_res.data if p.get('best_bet_selection') == p.get('actual_result'))
                    accuracy = (correct / len(settled_res.data)) * 100
            except: pass

            # Calculate ROI from user bets
            try:
                bets_res = supabase.table("user_bets").select("stake, profit_loss").not_.is_("profit_loss", "null").execute()
                if bets_res.data:
                    total_staked = sum(b.get('stake') or 0 for b in bets_res.data)
                    total_profit = sum(b.get('profit_loss') or 0 for b in bets_res.data)
                    if total_staked > 0:
                        roi = (total_profit / total_staked) * 100
            except: pass
        except Exception as e:
            logger.error(f"Error fetching dashboard stats: {e}")

    return {
        "total_predictions": total_preds,
        "active_value_bets": active_value,
        "ai_accuracy": f"{round(accuracy, 1)}%" if accuracy > 0 else "N/A",
        "win_rate": f"{round(accuracy, 1)}%" if accuracy > 0 else "N/A",
        "portfolio_roi": f"{round(roi, 1)}%"
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
        
        results = []
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


# --- Admin Endpoints ---
@router.post("/admin/sync-teams", summary="Sync teams from external API to Supabase")
async def sync_teams():
    if not football_client or not supabase:
        raise HTTPException(status_code=503, detail="Clients not configured.")
    
    try:
        leagues_data = await football_client.list_leagues()
        all_teams = []
        for l_item in leagues_data.get('response', [])[:5]: # Limit for personal use
            league_id = l_item.get('league', {}).get('id')
            logger.info(f"Syncing teams for league: {league_id}")
            # Simplified for Sportradar
            pass
        
        return {"status": "success", "message": "Manual sync needed for Sportradar specific IDs"}

    except Exception as e:
        logger.error(f"Sync teams failed: {e}")
        return {"status": "error", "message": str(e)}


@router.post("/admin/sync-players", summary="Sync players for existing teams in database")
async def sync_players():
    return {"status": "success", "message": "Player sync disabled for trial account"}


@router.post("/admin/seed-database", summary="Seed the database with initial data")
async def seed_database():
    if not supabase:
        raise HTTPException(status_code=503, detail="Database not configured.")
    
    initial_teams = [
        {'id': 'sr:competitor:42', 'name': 'Arsenal', 'country': 'England', 'league_name': 'Premier League'},
        {'id': 'sr:competitor:44', 'name': 'Liverpool', 'country': 'England', 'league_name': 'Premier League'},
        {'id': 'sr:competitor:17', 'name': 'Manchester City', 'country': 'England', 'league_name': 'Premier League'},
    ]
    
    try:
        success_count = 0
        for team in initial_teams:
            try:
                supabase.table("teams").upsert(team, on_conflict="id").execute()
                success_count += 1
            except Exception as e:
                logger.error(f"Failed to seed team {team['name']}: {e}")
        return {"status": "success", "message": "Database seeded.", "count": success_count}
    except Exception as e:
        logger.error(f"Seeding failed: {e}")
        return JSONResponse(status_code=500, content={"status": "error", "detail": f"Seeding failed: {str(e)}"})


@router.get("/admin/stats", summary="Get admin dashboard statistics")
async def get_admin_stats():
    return {"total_users": 1, "premium_subs": 1, "daily_revenue": 0, "bot_health": 100.0}


@router.post("/telegram/broadcast", summary="Broadcast a message to Telegram channel")
async def telegram_broadcast(request: TelegramBroadcastRequest):
    bot_token = os.environ.get("TELEGRAM_BOT_TOKEN")
    chat_id = os.environ.get("TELEGRAM_CHAT_ID", "@footyedge_signals")

    if not bot_token:
        logger.warning("TELEGRAM_BOT_TOKEN not set. Simulating broadcast.")
        return {"success": True, "message": "Simulated: Bot token missing."}

    message = f"⚽ *{request.prediction.get('home_team')} vs {request.prediction.get('away_team')}*\n\n"
    message += f"🎯 *Selection: {request.valueBet.get('selection')}*\n"
    message += f"Odds: {request.valueBet.get('odds')}\n"

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
async def get_players(team_id: Optional[str] = None, limit: int = 50):
    if not supabase:
        raise HTTPException(status_code=503, detail="Database not configured.")
    query = supabase.table("players").select("*, teams(name)")
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
@router.get("/leagues", summary="List all leagues from external API")
async def list_leagues_ext():
    return await football_client.list_leagues()


@router.get("/matches", summary="Get matches by date from external API")
async def get_matches_by_date_ext(from_date: Optional[str] = None, to_date: Optional[str] = None, date: Optional[str] = None):
    f_date = from_date or date or datetime.now().strftime("%Y-%m-%d")
    t_date = to_date or f_date
    res = await football_client.get_matches_by_date(f_date, t_date)
    return res


@router.get("/stats/{event_id}", summary="Get statistics by event ID from external API")
async def get_stats_by_event_id_ext(event_id: str):
    return await football_client.get_stats_by_event_id(event_id)


# --- Include Router ---
app.include_router(router)


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
