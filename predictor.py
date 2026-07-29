"""
FootyEdge AI - Core Prediction Engine (Optimized for The-Odds-API)
"""
import httpx
import numpy as np
import math
from datetime import datetime, timedelta, timezone
import os
import json
from typing import Dict, List, Any, Tuple
import logging
from pathlib import Path

from agents.team_strength import TeamStrengthAgent
from agents.tactical_agent import TacticalAgent
from agents.player_impact import PlayerImpactAgent
from agents.models import TeamStrength, ValueBet
from agents.goal_distribution_agent import GoalDistributionAgent
from agents.kelly_agent import KellyAgent
from football_api_client import FootballAPIClient

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class FootyEdgePredictor:
    
    def __init__(self, supabase_url: str = None, supabase_key: str = None, football_client=None):
        self.supabase_url = supabase_url or os.environ.get('SUPABASE_URL')
        self.supabase_key = supabase_key or os.environ.get('SUPABASE_KEY')
        
        # Initialize Supabase client
        if self.supabase_url and self.supabase_key:
            from supabase import create_client
            try:
                self.supabase = create_client(self.supabase_url, self.supabase_key)
            except Exception as e:
                logger.error(f"Failed to connect to Supabase: {e}")
                self.supabase = None
        else:
            self.supabase = None

        self.football_client = football_client or FootballAPIClient()
        self.cache = {}
        self.cache_ttl = 3600
        self.team_strength_agent = TeamStrengthAgent(supabase_client=self.supabase)
        self.tactical_agent = TacticalAgent()
        self.player_agent = PlayerImpactAgent(football_client=self.football_client, team_agent=self.team_strength_agent)
        self.goal_agent = GoalDistributionAgent()
        self.kelly_agent = KellyAgent()


    async def get_team_matches(self, team_name: str, limit: int = 40) -> List[Dict]:
        """
        Fetches historical matches from Supabase.
        The-Odds-API doesn't provide history, so we rely on DB.
        """
        if not self.supabase: return []

        try:
            team_res = self.supabase.table("teams").select("id").eq("name", team_name).execute()
            if not team_res.data: return []

            team_id = team_res.data[0]['id']
            h_res = self.supabase.table("matches").select("*").eq("home_team_id", team_id).order("match_date", desc=True).limit(limit).execute()
            a_res = self.supabase.table("matches").select("*").eq("away_team_id", team_id).order("match_date", desc=True).limit(limit).execute()

            db_matches = []
            for m in (h_res.data or []) + (a_res.data or []):
                is_home = m['home_team_id'] == team_id
                opp_id = m['away_team_id'] if is_home else m['home_team_id']
                
                # Fetch opponent name for Elo context
                opp_res = self.supabase.table("teams").select("name").eq("id", opp_id).execute()
                opp_name = opp_res.data[0]['name'] if opp_res.data else "Unknown"

                db_matches.append({
                    'date': m['match_date'].split('T')[0],
                    'is_home': is_home,
                    'goals_scored': m.get('home_goals', 0) if is_home else m.get('away_goals', 0),
                    'goals_conceded': m.get('away_goals', 0) if is_home else m.get('home_goals', 0),
                    'result': 'win' if (is_home and m['home_goals'] > m['away_goals']) or (not is_home and m['away_goals'] > m['home_goals']) else ('draw' if m['home_goals'] == m['away_goals'] else 'loss'),
                    'opponent_id': opp_id,
                    'opponent_name': opp_name
                })
            return sorted(db_matches, key=lambda x: x['date'], reverse=True)[:limit]
        except Exception as e:
            logger.error(f"DB match fetch failed: {e}")
            return []

    async def find_all_value_bets(self) -> List[Dict]:
        """
        Scans all upcoming matches from The-Odds-API and calculates value.
        """
        all_value_bets = []
        matches_data = await self.football_client.get_matches_by_date(datetime.now().strftime("%Y-%m-%d"))
        matches = matches_data.get('response', [])

        for m in matches:
            home_team = m.get('teams', {}).get('home', {}).get('name')
            away_team = m.get('teams', {}).get('away', {}).get('name')
            odds = m.get('live_odds', {})

            if not odds or not home_team or not away_team: continue

            try:
                prediction = await self.predict_match(home_team, away_team, odds)
                if prediction.get('value_bets'):
                    for bet in prediction['value_bets']:
                        bet['home_team'] = home_team
                        bet['away_team'] = away_team
                        all_value_bets.append(bet)
            except Exception as e:
                logger.error(f"Prediction failed for {home_team} vs {away_team}: {e}")
        return all_value_bets

    async def predict_match(self, home_team: str, away_team: str, odds: Dict) -> Dict:
        # Resolve team IDs for accurate Elo lookups
        home_id_res = self.supabase.table("teams").select("id").eq("name", home_team).execute()
        away_id_res = self.supabase.table("teams").select("id").eq("name", away_team).execute()
        
        home_id = home_id_res.data[0]['id'] if home_id_res.data else None
        away_id = away_id_res.data[0]['id'] if away_id_res.data else None

        home_matches = await self.get_team_matches(home_team)
        away_matches = await self.get_team_matches(away_team)

        home_strength = await self.team_strength_agent.assess(home_team, home_matches, team_id=home_id)
        away_strength = await self.team_strength_agent.assess(away_team, away_matches, team_id=away_id)

        # Poisson distribution model
        h_att = home_strength.attack_strength
        a_def = away_strength.defense_strength
        a_att = away_strength.attack_strength
        h_def = home_strength.defense_strength

        home_xG = max(0.5, h_att * a_def * 1.1)
        away_xG = max(0.5, a_att * h_def * 0.9)

        # Use shared GoalDistributionAgent (AR-008)
        dist = self.goal_agent.calculate(home_xG, away_xG)
        probs = {
            "home_win": dist.home_win_prob,
            "draw": dist.draw_prob,
            "away_win": dist.away_win_prob,
            "Over 2.5": dist.over_under["2.5"],
            "BTTS Yes": dist.both_teams_score
        }

        value_bets = []
        mapping = [
            ("Match Winner", "Home", "home_win"), 
            ("Match Winner", "Draw", "draw"), 
            ("Match Winner", "Away", "away_win"),
            ("Over/Under 2.5", "Over 2.5 Goals", "Over 2.5"),
            ("Both Teams to Score", "BTTS Yes", "BTTS Yes")
        ]
        for market, selection, odd_key in mapping:
            if odd_key in odds and odds[odd_key] > 1.0:
                prob = probs.get(odd_key)
                if prob and prob * odds[odd_key] > 1.05:
                    ev = (prob * odds[odd_key]) - 1
                    # Use shared KellyAgent (CR-014)
                    kelly_stake = self.kelly_agent.calculate_stake(prob, odds[odd_key])
                    
                    value_bets.append({
                        "market_name": market,
                        "selection": selection,
                        "odds": odds[odd_key],
                        "our_probability": prob,
                        "ev": ev,
                        "kelly_percentage": kelly_stake,
                        "tier": "Hot 🔥" if ev > 0.15 else "Solid",
                        "recommended_stake_percentage": kelly_stake
                    })

        return {
            "home_team": home_team,
            "away_team": away_team,
            "home_xg": home_xG,
            "away_xg": away_xG,
            "home_prob": probs["home_win"],
            "draw_prob": probs["draw"],
            "away_prob": probs["away_win"],
            "kelly_percentage": value_bets[0]['kelly_percentage'] if value_bets else 0.0,
            "over_2_5_prob": probs["Over 2.5"],
            "btts_prob": probs["BTTS Yes"],
            "probabilities": probs,
            "value_bets": value_bets,
            "confidence": (probs["home_win"] + probs["away_win"]) / 1.5,
            "best_bet_market": value_bets[0]['market_name'] if value_bets else "Match Winner",
            "best_bet_selection": value_bets[0]['selection'] if value_bets else "Draw",
            "best_bet_odds": value_bets[0]['odds'] if value_bets else 3.40,
            "created_at": datetime.now(timezone.utc).isoformat()
        }

    async def analyze_custom_bet(self, home_team: str, away_team: str, market: str, selection: str, odds: float) -> Dict:
        prediction = await self.predict_match(home_team, away_team, {})
        probs = prediction.get('probabilities', {})
        prob = 0.333
        if market == "Match Winner":
            if selection == home_team: prob = probs.get('home_win', 0.33)
            elif selection == away_team: prob = probs.get('away_win', 0.33)
            else: prob = probs.get('draw', 0.34)

        ev = (prob * odds) - 1
        return {
            "home_team": home_team,
            "away_team": away_team,
            "market": market,
            "selection": selection,
            "odds": odds,
            "our_probability": prob,
            "ev": ev,
            "tier": "Hot 🔥" if ev > 0.15 else "Solid",
            "recommended_stake_percentage": max(1.0, min(10.0, ev * 15))
        }
