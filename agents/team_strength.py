# agents/team_strength.py
"""
Agent 1: Team Strength Agent (The Foundation)
Builds dynamic, Bayesian-updated team ratings.
"""
from datetime import datetime
from typing import List, Dict, Any
import numpy as np

from agents.models import TeamStrength

class TeamStrengthAgent:
    """
    Builds dynamic team ratings using data from a persistent source.
    """
    
    def __init__(self, supabase_client: Any, k_factor=20, decay_rate=0.95, history_length=20):
        self.supabase = supabase_client
        self.k_factor = k_factor
        self.decay_rate = decay_rate
        self.history_length = history_length

    async def assess(self, team_name: str, matches: List[Dict], league_name: str = None, squad_data: Dict = None) -> TeamStrength:
        """
        Calculates comprehensive team strength based on provided match history.
        """
        base_rating, history = await self._calculate_elo_from_history(team_name, matches)
        
        home_matches = [m for m in history if m['is_home']]
        away_matches = [m for m in history if not m['is_home']]

        home_rating, _ = await self._calculate_elo_from_history(team_name, home_matches)
        away_rating, _ = await self._calculate_elo_from_history(team_name, away_matches)

        form_rating = self._calculate_form(history[:10])
        attack_strength = self._calculate_attack_strength(history)
        defense_strength = self._calculate_defense_strength(history)
        
        squad_adjustment = self._adjust_for_squad(squad_data) if squad_data else 0
        comp_adjustment = self._competition_factor(league_name)
        
        return TeamStrength(
            name=team_name,
            overall_rating=base_rating + squad_adjustment,
            home_advantage=home_rating - base_rating,
            away_disadvantage=away_rating - base_rating,
            form_rating=form_rating,
            attack_strength=attack_strength,
            defense_strength=defense_strength,
            xG_performance=self._calculate_xg_perf(history),
            variance_profile=self._calculate_variance(history),
            competition_factor=comp_adjustment,
            midfield_rating=base_rating * 0.8
        )

    def _calculate_xg_perf(self, history: List[Dict]) -> float:
        # If we don't have real xG, we derive a performance ratio from goal efficiency
        if not history: return 1.0
        # High ratio means overperforming (lucky or efficient)
        return 1.0 + (sum(m['goals_scored'] for m in history) / len(history)) / 5.0

    async def _get_rating_from_db(self, team_name: str) -> float:
        if not self.supabase: return 1500.0
        try:
            res = await self.supabase.table('teams').select('elo_rating').eq('name', team_name).single().execute()
            return res.data.get('elo_rating', 1500.0) if res.data else 1500.0
        except Exception:
            return 1500.0

    async def _calculate_elo_from_history(self, team_name: str, matches: List[Dict]) -> (float, List[Dict]):
        current_rating = await self._get_rating_from_db(team_name)
        if not matches: return current_rating, []
        
        processed_matches = []
        for match in reversed(matches): # Process chronologically
            opponent_name = match.get('opponent_name', 'Unknown Opponent')
            opponent_rating = await self._get_rating_from_db(opponent_name)
            
            home_adv = 50 if match['is_home'] else -50
            expected_score = 1 / (1 + 10**((opponent_rating - (current_rating + home_adv)) / 400))
            
            if match['result'] == 'win': actual_score = 1
            elif match['result'] == 'draw': actual_score = 0.5
            else: actual_score = 0
            
            rating_change = self.k_factor * (actual_score - expected_score)
            current_rating += rating_change
            
            match_copy = match.copy()
            match_copy['rating_change'] = rating_change
            processed_matches.append(match_copy)
            
        return current_rating, list(reversed(processed_matches)) # Return to recent-first

    def _calculate_form(self, recent_matches: List[Dict]) -> float:
        if not recent_matches: return 0.5
        form_score = 0
        total_weight = 0
        for i, match in enumerate(recent_matches):
            weight = self.decay_rate ** i
            rating_change = match.get('rating_change', 0)
            form_score += rating_change * weight
            total_weight += weight
        return (form_score / total_weight) * 10 if total_weight > 0 else 0.5

    def _calculate_attack_strength(self, matches: List[Dict]) -> float:
        if not matches: return 1.0
        weighted_goals = 0
        total_weight = 0
        for i, match in enumerate(matches):
            weight = self.decay_rate ** i
            weighted_goals += match['goals_scored'] * weight
            total_weight += weight
        return weighted_goals / total_weight if total_weight > 0 else 1.0

    def _calculate_defense_strength(self, matches: List[Dict]) -> float:
        if not matches: return 1.0
        weighted_goals_conceded = 0
        total_weight = 0
        for i, match in enumerate(matches):
            weight = self.decay_rate ** i
            weighted_goals_conceded += match['goals_conceded'] * weight
            total_weight += weight
        return weighted_goals_conceded / total_weight if total_weight > 0 else 1.0

    def _calculate_variance(self, matches: List[Dict]) -> float:
        if len(matches) < 2: return 0.2
        goal_diffs = [(m['goals_scored'] - m['goals_conceded']) for m in matches]
        return np.std(goal_diffs)

    def _adjust_for_squad(self, squad_data: Dict) -> float:
        return squad_data.get('adjustment', 0) if squad_data else 0

    def _competition_factor(self, league_name: str) -> float:
        if not league_name: return 1.0
        tier_map = {
            'Premier League': 1.1,
            'Champions League': 1.15,
            'La Liga': 1.05,
            'Bundesliga': 1.02,
            'Serie A': 1.02,
            'Ligue 1': 0.95
        }
        return tier_map.get(league_name, 1.0)
