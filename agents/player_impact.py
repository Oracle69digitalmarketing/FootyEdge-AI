# agents/player_impact.py
"""
Agent 2: Player Impact Agent
Models how individual players affect team strength.
"""
from typing import Dict, Any, List

from agents.models import PlayerImpact
from agents.team_strength import TeamStrengthAgent

class PlayerImpactAgent:
    """
    Models how individual players affect team strength.
    Can predict impact of injuries, suspensions, transfers.
    """
    
    def __init__(self, team_agent: TeamStrengthAgent):
        self.player_models = {}
        self.lineup_history = {}
        self.team_agent = team_agent # Requires a TeamStrengthAgent instance
    
    async def _get_matches_with_player(self, team: str, player: Any) -> List[Dict]:
        # MOCK: Placeholder to get matches where a player participated.
        return []

    async def _get_matches_without_player(self, team: str, player: Any) -> List[Dict]:
        # MOCK: Placeholder to get matches where a player was absent.
        return []

    async def assess_player_impact(self, player: Any, team: str, position: str) -> PlayerImpact:
        """
        Calculate how much this player contributes to team strength.
        """
        with_player = await self._get_matches_with_player(team, player)
        without_player = await self._get_matches_without_player(team, player)
        
        impact = {
            'xG_difference': self._calculate_xG_impact(with_player, without_player),
            'defensive_impact': self._calculate_defensive_impact(with_player, without_player),
            'possession_impact': self._calculate_possession_impact(with_player, without_player),
            'momentum_factor': self._calculate_momentum_impact(player)
        }
        
        # Position-specific adjustments (mocked)
        if position in ['striker', 'winger']:
            impact['goal_contribution'] = 0.5 # player.goals_per_90
        elif position in ['cb', 'gk']:
            impact['clean_sheet_factor'] = 0.1 # player.clean_sheet_rate
        
        return PlayerImpact(
            player=player,
            position=position,
            total_impact=self._weighted_total(impact),
            details=impact
        )
    
    async def predict_lineup_impact(self, predicted_lineup: List[Any], team: str) -> Dict:
        """
        Given expected lineup, adjust team strength.
        Critical for early betting before lineups are announced.
        """
        base_strength = await self.team_agent.assess(team)
        
        lineup_adjustment = 0
        for player in predicted_lineup:
            # Assuming player object has name and position
            impact = await self.assess_player_impact(player, team, player.position)
            lineup_adjustment += impact.total_impact
        
        synergy = self._calculate_synergy(predicted_lineup)
        
        return {
            'adjusted_strength': base_strength.overall_rating + lineup_adjustment + synergy,
            'key_absences': self._identify_key_missing_players(predicted_lineup, team),
            'formation_analysis': self._analyze_formation(predicted_lineup)
        }

    # --- Placeholder Private Methods ---

    def _calculate_xG_impact(self, with_player: List, without_player: List) -> float:
        # MOCK: In reality, compare xG performance in both sets of matches.
        return 0.1

    def _calculate_defensive_impact(self, with_player: List, without_player: List) -> float:
        # MOCK: Compare xG against.
        return -0.05

    def _calculate_possession_impact(self, with_player: List, without_player: List) -> float:
        # MOCK: Compare possession stats.
        return 0.02

    def _calculate_momentum_impact(self, player: Any) -> float:
        # MOCK: Leaders matter. This is a qualitative adjustment.
        return 0.01

    def _weighted_total(self, impact: Dict) -> float:
        # MOCK: Combine impact scores into a single number.
        return sum(value for value in impact.values() if isinstance(value, (int, float)))

    def _calculate_synergy(self, lineup: List) -> float:
        # MOCK: Placeholder for player chemistry effects.
        return 0.0

    def _identify_key_missing_players(self, lineup: List, team: str) -> List:
        # MOCK: Identify who is missing from the usual starters.
        return ["Key Player A"]

    def _analyze_formation(self, lineup: List) -> Dict:
        # MOCK: Analyze the tactical shape.
        return {"shape": "4-3-3", "analysis": "Aggressive"}
