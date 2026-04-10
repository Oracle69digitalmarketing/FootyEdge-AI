# agents/player_impact.py
"""
Agent 2: Player Impact Agent
Models how individual players affect team strength.
"""
from typing import Dict, Any, List, Optional
import logging

from agents.models import PlayerImpact
from agents.team_strength import TeamStrengthAgent

logger = logging.getLogger(__name__)

class PlayerImpactAgent:
    """
    Models how individual players affect team strength using real API data.
    """
    
    def __init__(self, football_client: Any, team_agent: TeamStrengthAgent):
        self.football_client = football_client
        self.team_agent = team_agent
    
    async def assess_player_stats(self, player_name: str, team_id: int) -> Optional[PlayerImpact]:
        """
        Fetch and analyze real player statistics.
        """
        try:
            res = await self.football_client.search_players(player_name)
            if not res.get('response'): return None

            # Find the correct player for the team
            player_data = None
            for p in res['response']:
                for stat in p.get('statistics', []):
                    if stat.get('team', {}).get('id') == team_id:
                        player_data = p
                        break
                if player_data: break

            if not player_data: return None

            stats = player_data['statistics'][0]
            games = stats.get('games', {})
            goals = stats.get('goals', {})
            passes = stats.get('passes', {})
            tackles = stats.get('tackles', {})

            position = games.get('position', 'Unknown')

            # Derived impact scores
            rating = float(games.get('rating') or 6.5)
            goal_contrib = (float(goals.get('total') or 0) + float(goals.get('assists') or 0)) / max(1, float(games.get('appearences') or 1))

            impact = {
                'rating_factor': (rating - 6.5) * 10,
                'goal_contribution': goal_contrib * 20,
                'efficiency': float(passes.get('accuracy') or 70) / 100.0,
                'defensive_contribution': float(tackles.get('total') or 0) / max(1, float(games.get('appearences') or 1))
            }

            return PlayerImpact(
                player=player_name,
                position=position,
                total_impact=self._weighted_total(impact),
                details=impact
            )
        except Exception as e:
            logger.error(f"Failed to assess player impact for {player_name}: {e}")
            return None
    
    async def predict_lineup_impact(self, predicted_lineup: List[str], team_name: str, team_id: int, matches: List[Dict], league_name: str) -> Dict:
        """
        Given expected lineup, adjust team strength.
        """
        base_strength = await self.team_agent.assess(team_name, matches, league_name=league_name)
        
        lineup_adjustment = 0
        for player_name in predicted_lineup:
            impact = await self.assess_player_stats(player_name, team_id)
            if impact:
                lineup_adjustment += impact.total_impact
        
        return {
            'adjusted_strength': base_strength.overall_rating + (lineup_adjustment / max(1, len(predicted_lineup))) * 10,
            'impact_delta': lineup_adjustment
        }

    def _weighted_total(self, impact: Dict) -> float:
        # Weighting based on importance
        return (
            impact.get('rating_factor', 0) * 0.5 +
            impact.get('goal_contribution', 0) * 0.3 +
            impact.get('defensive_contribution', 0) * 0.2
        )
