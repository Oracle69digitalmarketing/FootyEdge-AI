import logging
import os
from fastapi import FastAPI, BackgroundTasks, Query, Depends, HTTPException, APIRouter, Header
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel, Field
from typing import List, Dict, Any, Optional
from supabase import create_client, Client
from datetime import datetime, timedelta, timezone
import asyncio
import pandas as pd
import numpy as np
from contextlib import asynccontextmanager
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

from prediction_pipeline import run_pipeline
from backup_manager import run_database_backup
from settle_bets import run_settlement
from env_guard import EnvGuardError, require_destructive_approval
from football_api_client import FootballAPIClient
from agents.strategy_agent import StrategyAgent
from player_team_membership import attach_current_teams

# Entitlements (8F)
from entitlements import (
    EntitlementResult,
    require_capability,
    require_role,
    get_entitlements,
    CAP_VALUE_BETS,
    CAP_ACCA_BUILDER,
    CAP_PORTFOLIO,
    CAP_AI_STRATEGY_ANALYSIS,
    CAP_PREDICTIONS,
    CAP_TEAMS,
    CAP_PLAYERS,
    CAP_DASHBOARD,
    CAP_MATCH_INTELLIGENCE,
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("main")

# Scheduler setup
scheduler = BackgroundScheduler()

@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("⏰ Waking up internal application cron engines...")

    # Task 1: Run prediction loops nightly at 2:00 AM
    scheduler.add_job(
        run_pipeline,
        trigger=CronTrigger(hour=2, minute=0),
        id="nightly_prediction_sync",
        replace_existing=True
    )

    # Task 2: Settle yesterday's results daily at 5:00 AM
    scheduler.add_job(
        run_settlement,
        trigger=CronTrigger(hour=5, minute=0),
        id="daily_settlement",
        replace_existing=True
    )

    # Task 3: Weekly database snapshot every Sunday at 3:00 AM
    scheduler.add_job(
        run_database_backup,
        trigger=CronTrigger(day_of_week="sun", hour=3, minute=0),
        id="weekly_database_backup",
        replace_existing=True
    )

    # Player sync scheduling is intentionally NOT registered here.
    # The sync implementation in player_sync remains available for an
    # explicitly authorized manual/backfill trigger only; automatic
    # nightly player syncs are disabled while membership data integrity
    # is investigated. Prediction, settlement, and backup jobs above
    # are unchanged.

    scheduler.start()
    yield
    scheduler.shutdown()

app = FastAPI(lifespan=lifespan, title="FootyEdge AI Production Engine", version="5.4.0")

ALLOWED_ORIGINS = ["*"]
app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Clients
SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_SERVICE_KEY") or os.environ.get("SUPABASE_KEY")

class MockSupabase:
    _storage = {}
    def table(self, name):
        if name not in self._storage: self._storage[name] = []
        return MockSupabaseTable(name, self._storage[name])
    def auth(self):
        class MockAuth:
            def get_user(self, *args, **kwargs): return None
        return MockAuth()

class MockSupabaseTable:
    def __init__(self, name, data_list):
        self.name = name
        self.data_list = data_list
        self.filters = []

    def select(self, *args, **kwargs): return self
    def insert(self, data):
        if isinstance(data, list):
            for d in data: self.data_list.append(d.copy())
        else:
            self.data_list.append(data.copy())
        return self
    def update(self, *args, **kwargs): return self
    def delete(self, *args, **kwargs): return self
    def eq(self, column, value):
        self.filters.append((column, value))
        return self
    def neq(self, *args, **kwargs): return self
    def gte(self, *args, **kwargs): return self
    def lte(self, *args, **kwargs): return self
    def in_(self, *args, **kwargs): return self
    def order(self, *args, **kwargs): return self
    def limit(self, *args, **kwargs): return self
    def execute(self):
        filtered_data = []
        for d in self.data_list:
            match = True
            for col, val in self.filters:
                if d.get(col) != val:
                    match = False
                    break
            if match:
                filtered_data.append(d)
        
        class MockResult:
            def __init__(self, data):
                self.data = data
                self.count = len(data)
        return MockResult(filtered_data)

if SUPABASE_URL and SUPABASE_KEY:
    try:
        supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
        logger.info("✅ Supabase client initialized.")
    except Exception as e:
        logger.error(f"❌ Failed to initialize Supabase: {e}")
        supabase = MockSupabase()
else:
    logger.warning("⚠️ SUPABASE_URL/KEY missing. Using MockSupabase.")
    supabase = MockSupabase()

football_client = FootballAPIClient()
strategy_agent = StrategyAgent()

def get_supabase_client():
    return supabase

# Models
class StrategyAnalyzeRequest(BaseModel):
    text: str
    stake: float = 1000

class PredictRequest(BaseModel):
    home_team: str
    away_team: str
    odds: Dict[str, float] = Field(default={})

class BetRecordRequest(BaseModel):
    # NOTE: no user_id field. Bet ownership is derived exclusively from
    # the verified JWT identity (10.1A). Any client-supplied owner value
    # in the body is ignored by pydantic and never consulted.
    match_id: Optional[int] = None
    market: str
    selection: str
    odds: float
    stake: float

# API Router
router = APIRouter()

@router.get("/api/health")
async def health_check():
    return {
        "status": "operational",
        "supabase_connected": not isinstance(supabase, MockSupabase),
        "scheduler_running": scheduler.running,
        "environment": "production"
    }

@router.get("/api/cron-trigger")
async def manual_cron_trigger(
    background_tasks: BackgroundTasks,
    x_cron_token: str = Header(None)
):
    """Secure endpoint to manually trigger the prediction pipeline."""
    CRON_SECRET = os.environ.get("CRON_SECRET_TOKEN", "default_secure_pass_123")
    if x_cron_token != CRON_SECRET:
        raise HTTPException(status_code=401, detail="Unauthorized execution vector.")

    background_tasks.add_task(run_pipeline)
    return {"status": "queued"}

@router.get("/api/daily-picks")
@router.get("/api/daily-picks/")
async def get_user_filtered_predictions(
    timeline: str = Query("daily", description="Options: daily, weekly, custom"),
    from_date: str = Query(None, alias="from_date", description="YYYY-MM-DD"),
    to_date: str = Query(None, alias="to_date", description="YYYY-MM-DD"),
    _ent: EntitlementResult = Depends(require_capability(CAP_PREDICTIONS)),
    supabase: Client = Depends(get_supabase_client)
):
    """
    Unified User Prediction Feed.
    Accepts from_date and to_date parameters to prevent duplicate match rendering.
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
        matches_res = supabase.table("matches") \
            .select("id, match_date, league") \
            .gte("match_date", query_start) \
            .lte("match_date", query_end) \
            .execute()

        if not matches_res.data:
            # Provide sample data if empty/mock
            if isinstance(supabase, MockSupabase):
                return [{
                    "id": 1, "match_id": 1, "home_team": "Sample FC", "away_team": "United Utd",
                    "best_bet_selection": "Home Win", "best_bet_odds": 2.10, "home_prob": 0.55,
                    "away_prob": 0.20, "draw_prob": 0.25, "ev": 0.155, "kelly_stake_percentage": 5.0
                }]
            return []

        m_ids = [m['id'] for m in matches_res.data]
        preds_res = supabase.table("predictions").select("*").in_("match_id", m_ids).execute()
        
        results = []
        for p in (preds_res.data or []):
            p_dict = dict(p)
            # Use stored kelly_percentage if available, otherwise fallback to legacy field name
            p_dict["kelly_stake_percentage"] = p.get("kelly_percentage") or 0.0
            results.append(p_dict)
            
        return results
    except Exception as e:
        logger.error(f"Prediction fetch error: {e}")
        return []

@router.get("/api/teams")
@router.get("/api/teams/")
async def get_production_teams(
    _ent: EntitlementResult = Depends(require_capability(CAP_TEAMS)),
    supabase: Client = Depends(get_supabase_client)
):
    """Returns actual teams sorted alphabetically."""
    res = supabase.table("teams").select("*").order("name").execute()
    if not res.data and isinstance(supabase, MockSupabase):
        return [{"id": 1, "name": "Arsenal", "league_name": "Premier League"}, {"id": 2, "name": "Chelsea", "league_name": "Premier League"}]
    return res.data

@router.get("/api/teams/{team_id}")
async def get_team_detail(
    team_id: int,
    _ent: EntitlementResult = Depends(require_capability(CAP_TEAMS)),
    supabase: Client = Depends(get_supabase_client)
):
    res = supabase.table("teams").select("*").eq("id", team_id).execute()
    if not res.data and isinstance(supabase, MockSupabase):
        return {"id": team_id, "name": "Mock Team", "country": "England", "league_name": "Premier League"}
    if not res.data: raise HTTPException(status_code=404, detail="Team not found")
    return res.data[0]

@router.get("/api/search/teams")
async def search_teams(
    q: str = Query(...),
    _ent: EntitlementResult = Depends(require_capability(CAP_TEAMS)),
    supabase: Client = Depends(get_supabase_client)
):
    # Simple mock search
    res = supabase.table("teams").select("*").execute()
    teams = res.data or []
    if isinstance(supabase, MockSupabase):
        teams = [{"id": 1, "name": "Arsenal"}, {"id": 2, "name": "Chelsea"}]
    return [t for t in teams if q.lower() in t['name'].lower()]

@router.get("/api/players")
@router.get("/api/players/")
async def get_production_players(
    _ent: EntitlementResult = Depends(require_capability(CAP_PLAYERS)),
    supabase: Client = Depends(get_supabase_client)
):
    """Read-only actual players feed.

    Current team ("teams") is resolved from player_team_history
    (history-authoritative membership), not players.team_id. A player
    with no history resolves to "teams": None (UI "Free Agent").
    """
    res = supabase.table("players").select("*").limit(100).execute()
    if not res.data and isinstance(supabase, MockSupabase):
        return [{"id": 1, "name": "Bukayo Saka", "teams": {"name": "Arsenal"}}]
    return await attach_current_teams(supabase, res.data or [])

@router.get("/api/players/{player_id}")
async def get_player_detail(
    player_id: int,
    _ent: EntitlementResult = Depends(require_capability(CAP_PLAYERS)),
    supabase: Client = Depends(get_supabase_client)
):
    """Read-only player detail; team resolved from membership history."""
    res = supabase.table("players").select("*").eq("id", player_id).execute()
    if not res.data and isinstance(supabase, MockSupabase):
        return {"id": player_id, "name": "Mock Player", "teams": {"name": "Arsenal"}}
    if not res.data: raise HTTPException(status_code=404, detail="Player not found")
    merged = await attach_current_teams(supabase, [res.data[0]])
    return merged[0]

@router.get("/api/value-bets")
async def get_value_bets_dashboard(
    _ent: EntitlementResult = Depends(require_capability(CAP_VALUE_BETS)),
    supabase: Client = Depends(get_supabase_client)
):
    """Fetches high EV advantages directly from Supabase."""
    res = supabase.table("value_bets").select("*").eq("status", "active").order("ev", desc=True).execute()
    if not res.data and isinstance(supabase, MockSupabase):
        return [{
            "id": "vb1", "home_team": "Liverpool", "away_team": "Man City", "market": "1x2",
            "selection": "Home Win", "odds": 2.50, "our_probability": 0.45, "ev": 0.125,
            "recommended_stake_percentage": 2.5, "tier": "Hot 🔥", "created_at": datetime.now().isoformat()
        }]
    return res.data

@router.get("/api/bets/user/{user_id}")
async def get_user_bets(
    user_id: str,
    _ent: EntitlementResult = Depends(require_capability(CAP_PORTFOLIO)),
    supabase: Client = Depends(get_supabase_client)
):
    # Production contract: user_bets is the canonical table (no `bets` table in prod).
    # Ownership is JWT-bound (10.1A): the path id is accepted for route
    # compatibility but NEVER authorizes access. A caller may only read
    # their own bets; any other id is denied outright.
    if str(user_id) != str(_ent.user_id):
        raise HTTPException(status_code=403, detail="Access denied")
    res = supabase.table("user_bets").select("*").eq("user_id", _ent.user_id).order("created_at", desc=True).execute()
    return res.data or []

@router.post("/api/bets/record")
async def record_bet(
    req: BetRecordRequest,
    _ent: EntitlementResult = Depends(require_capability(CAP_PORTFOLIO)),
    supabase: Client = Depends(get_supabase_client)
):
    try:
        data = {
            # Owner comes exclusively from the verified JWT identity.
            # No client-supplied user_id exists on the request model.
            "user_id": _ent.user_id,
            "match_id": req.match_id,
            "market": req.market,
            "selection": req.selection,
            "odds": req.odds,
            "stake": req.stake,
            "potential_win": req.odds * req.stake,
            "status": "active",
            "created_at": datetime.now(timezone.utc).isoformat()
        }
        res = supabase.table("user_bets").insert(data).execute()
        return {"status": "success", "data": res.data[0] if res.data else data}
    except Exception as e:
        # Server-side signal only (exception type, never secrets or client
        # data). The API response is a stable, non-revealing error.
        logger.error("Bet record error: %s", type(e).__name__)
        return {"status": "error", "message": "Could not record bet. Please try again."}

@router.get("/api/dashboard/stats")
async def get_dashboard_stats(
    _ent: EntitlementResult = Depends(require_capability(CAP_DASHBOARD)),
    supabase: Client = Depends(get_supabase_client)
):
    """Calculates overall platform statistics."""
    if not supabase or isinstance(supabase, MockSupabase):
        return {
            "total_predictions": 1240, 
            "active_value_bets": 12, 
            "ai_accuracy": "74.2%",
            "win_rate": "74.2%",
            "portfolio_roi": "+12.4%"
        }
    try:
        preds_count = supabase.table("predictions").select("id", count="exact").execute().count or 0
        value_count = supabase.table("value_bets").select("id", count="exact").eq("status", "active").execute().count or 0

        settled = supabase.table("predictions").select("best_bet_selection, actual_result").not_.is_("actual_result", "null").execute().data
        accuracy = "N/A"
        if settled:
            correct = sum(1 for p in settled if p['best_bet_selection'] == p['actual_result'])
            accuracy = f"{round((correct / len(settled)) * 100, 1)}%"

        return {
            "total_predictions": preds_count,
            "active_value_bets": value_count,
            "ai_accuracy": accuracy,
            "win_rate": accuracy,
            "portfolio_roi": "+12.4%"
        }
    except Exception as e:
        logger.error(f"Stats fetch error: {e}")
        return {"total_predictions": 0, "active_value_bets": 0, "ai_accuracy": "N/A"}

@router.get("/api/auth/entitlements")
async def get_caller_entitlements(
    _ent: EntitlementResult = Depends(get_entitlements),
) -> Dict[str, Any]:
    """Return the caller's display-safe effective entitlements.

    Derived entirely from the server-resolved profile and subscription
    (verified JWT -> auth.users.id -> profiles/subscriptions). No
    client-supplied user ID, email, plan override, or preview flag is
    accepted. Only the minimum display fields are returned: no service
    credentials, provider payloads, or user lists. Commercial plan and
    owner-preview access are reported as separate dimensions; preview
    never mutates the subscription.
    """
    return {
        "role": _ent.role,
        "plan": _ent.plan,
        "subscription_status": _ent.subscription.status if _ent.subscription else None,
        "has_subscription": _ent.subscription is not None,
        "capabilities": sorted(_ent.capabilities),
        "owner_preview": _ent.owner_preview,
    }


@router.get("/api/auth/role")
async def get_caller_role(
    _ent: EntitlementResult = Depends(get_entitlements),
) -> Dict[str, Any]:
    """Return the caller's server-authoritative role for display/routing.

    The frontend uses this (Supabase session -> auth.users.id ->
    profiles.role) instead of any email allowlist. Any valid session gets
    its own role; unauthenticated callers get 401 via the dependency.
    Only the role is returned: no email, no user dump, no entitlements.
    Backend enforcement never consults this endpoint.
    """
    return {"role": _ent.role}


@router.get("/api/acca-builder")
async def get_automated_accumulator_ticket(
    _ent: EntitlementResult = Depends(require_capability(CAP_ACCA_BUILDER)),
    supabase: Client = Depends(get_supabase_client)
):
    """Greedy Combinator Algorithm for Accas."""
    try:
        res = supabase.table("value_bets") \
            .select("id, home_team, away_team, market, selection, odds, ev") \
            .eq("status", "active") \
            .order("ev", desc=True) \
            .limit(3) \
            .execute()
            
        if not res.data or len(res.data) < 2:
            return {"status": "insufficient_data", "combined_odds": 1.0, "selections": []}
            
        selections = res.data
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
    """Public Transparency Audit Ledger."""
    try:
        res = supabase.table("predictions") \
            .select("id, home_team, away_team, best_bet_market, best_bet_selection, best_bet_odds, actual_result") \
            .not_.is_("actual_result", "null") \
            .order("created_at", desc=True) \
            .limit(50) \
            .execute()
        return res.data
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch public accuracy audit trail: {str(e)}")

@router.get("/api/admin/metrics")
async def get_admin_model_metrics(
    _ent: EntitlementResult = Depends(require_role("owner", "admin")),
    supabase: Client = Depends(get_supabase_client)
):
    """Computes system accuracy and Top 10 wins."""
    try:
        preds = supabase.table("predictions").select("*").execute().data
        matches = supabase.table("matches").select("id, home_goals, away_goals").execute().data

        if not preds or not matches:
            return {"status": "no_data", "summary": {}, "top_10_wins": []}

        p_df = pd.DataFrame(preds)
        m_df = pd.DataFrame(matches).rename(columns={"id": "match_id"}).dropna()
        
        df = pd.merge(p_df, m_df, on="match_id", how="inner")
        if df.empty:
            return {"status": "no_completed_fixtures", "summary": {}, "top_10_wins": []}

        df['actual'] = df.apply(
            lambda r: "Home Win" if r['home_goals'] > r['away_goals'] else ("Draw" if r['home_goals'] == r['away_goals'] else "Away Win"),
            axis=1
        )
        df['success'] = df['best_bet_selection'] == df['actual']
        df['profit'] = df.apply(lambda r: (100 * r['best_bet_odds']) - 100 if r['success'] else -100, axis=1)

        total_fixtures = len(df)
        successful_predictions = int(df['success'].sum())
        accuracy_rate = (successful_predictions / total_fixtures) * 100
        net_profit = df['profit'].sum()

        winning_bets = df[df['success']].sort_values(by='ev', ascending=False).head(10)
        top_10 = []
        for _, row in winning_bets.iterrows():
            top_10.append({
                "home_team": row['home_team'],
                "away_team": row['away_team'],
                "market": row['best_bet_market'],
                "selection": row['best_bet_selection'],
                "odds": float(row['best_bet_odds']),
                "ev": float(row.get('ev', 0)),
                "score": f"{int(row['home_goals'])}-{int(row['away_goals'])}"
            })

        return {
            "status": "success",
            "summary": {
                "total_games_analyzed": total_fixtures,
                "successful_picks": successful_predictions,
                "model_accuracy_percentage": round(accuracy_rate, 2),
                "simulated_net_profit_usd": round(net_profit, 2),
                "simulated_roi_percentage": round((net_profit / (total_fixtures * 100)) * 100, 2)
            },
            "top_10_wins": top_10
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/api/predict")
async def predict_endpoint(
    request: PredictRequest,
    _ent: EntitlementResult = Depends(require_capability(CAP_PREDICTIONS)),
):
    from predictor import FootyEdgePredictor
    predictor = FootyEdgePredictor(football_client=football_client)
    return await predictor.predict_match(request.home_team, request.away_team, request.odds)

@router.post("/api/analyze-strategy")
async def analyze_strategy_endpoint(
    req: StrategyAnalyzeRequest,
    _ent: EntitlementResult = Depends(require_capability(CAP_AI_STRATEGY_ANALYSIS)),
):
    selections = strategy_agent.parse_strategy(req.text)
    return strategy_agent.analyze(selections, req.stake)

@router.get("/api/admin/trigger-full-sync")
async def trigger_full_sync(x_cron_token: str = Header(None)):
    """Authenticated endpoint to cleanup dummy data and force a pipeline sync."""
    CRON_SECRET = os.environ.get("CRON_SECRET_TOKEN", "1690")
    if x_cron_token != CRON_SECRET:
        raise HTTPException(status_code=401, detail="Unauthorized")

    try:
        require_destructive_approval("cleanup")
    except EnvGuardError as e:
        raise HTTPException(status_code=403, detail=str(e))
        
    # Run cleanup
    from cleanup_db import cleanup_database
    cleanup_database()
    
    # Run pipeline
    run_pipeline()
    
    return {"status": "success", "message": "Cleanup and sync triggered."}


@router.get("/api/recent-predictions")
async def recent_predictions(
    _ent: EntitlementResult = Depends(require_capability(CAP_PREDICTIONS)),
    supabase: Client = Depends(get_supabase_client)
):
    res = supabase.table("predictions").select("*").order("created_at", desc=True).limit(10).execute()
    return res.data or []

@router.get("/api/matches")
async def get_matches(
    _ent: EntitlementResult = Depends(require_capability(CAP_MATCH_INTELLIGENCE)),
):
    return await football_client.get_matches_by_date(datetime.now(timezone.utc).strftime("%Y-%m-%d"))

app.include_router(router)

try:
    from billing_api import router as billing_router
    app.include_router(billing_router)
except Exception as exc:  # billing routes must never break core startup
    logger.warning("billing router not mounted: %s", type(exc).__name__)

try:
    from admin_api import router as admin_router
    app.include_router(admin_router)
except Exception as exc:  # admin routes must never break core startup
    logger.warning("admin router not mounted: %s", type(exc).__name__)

try:
    from telegram_api import router as telegram_router
    app.include_router(telegram_router)
except Exception as exc:  # telegram routes must never break core startup
    logger.warning("telegram router not mounted: %s", type(exc).__name__)

try:
    from whatsapp_api import router as whatsapp_router
    app.include_router(whatsapp_router)
except Exception as exc:  # whatsapp routes must never break core startup
    logger.warning("whatsapp router not mounted: %s", type(exc).__name__)

# Static file serving
dist_path = os.path.join(os.path.dirname(__file__), "dist")
if os.path.exists(dist_path):
    @app.exception_handler(404)
    async def not_found_handler(request, exc):
        if not request.url.path.startswith("/api"):
            return FileResponse(os.path.join(dist_path, "index.html"))
        return JSONResponse(status_code=404, content={"message": "Not found"})
    app.mount("/", StaticFiles(directory=dist_path, html=True), name="static")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
