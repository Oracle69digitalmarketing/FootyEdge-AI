# agents/tactical_agent.py
"""
Agent 2: Tactical & Style Clash Agent
Analyzes the tactical matchup between two teams.
"""
from dataclasses import dataclass, field
from typing import List, Dict

from agents.models import TeamStrength

@dataclass
class TacticalAnalysis:
    """Holds the results of a tactical matchup analysis."""
    home_archetype: str
    away_archetype: str
    clash_insight: str
    probability_modifiers: Dict[str, float] = field(default_factory=dict)

class TacticalAgent:
    """
    Analyzes playing styles to predict tactical dynamics and their effect on match outcomes.
    """
    def classify_team_style(self, team_strength: TeamStrength) -> str:
        """
        Classifies a team into a tactical archetype based on its strength profile.
        
        Archetypes:
        - All-Rounder: Balanced strengths.
        - Attacking: High attack, average/low defense.
        - Defensive: Low attack, strong defense.
        - High-Variance: Unpredictable, high std. dev. in results.
        """
        attack_score = team_strength.attack_strength
        defense_score = team_strength.defense_strength # Lower is better
        variance = team_strength.variance_profile

        if variance > 1.5:
            return "High-Variance"
        if attack_score > 1.8 and defense_score > 1.4:
            return "All-Rounder"
        if attack_score > 1.6:
            return "Attacking"
        if defense_score < 1.0:
            return "Defensive"
        
        return "Balanced"

    def analyze_matchup(self, home_team: TeamStrength, away_team: TeamStrength) -> TacticalAnalysis:
        """
        Analyzes the clash of styles and returns modifiers and insights.
        """
        home_style = self.classify_team_style(home_team)
        away_style = self.classify_team_style(away_team)
        
        insight = f"A tactical battle between a {home_style} {home_team.name} and a {away_style} {away_team.name}."
        modifiers = {
            'over_2.5': 1.0,
            'under_2.5': 1.0,
            'btts_yes': 1.0,
            'draw': 1.0,
        }

        # --- Rule-based analysis for style clashes ---

        # Two attacking teams often leads to goals
        if home_style == 'Attacking' and away_style == 'Attacking':
            insight = "Clash of two attacking-minded teams. Expect goals."
            modifiers['over_2.5'] = 1.15  # 15% boost
            modifiers['btts_yes'] = 1.10   # 10% boost

        # Two defensive teams often leads to a tight, low-scoring affair
        elif home_style == 'Defensive' and away_style == 'Defensive':
            insight = "A cagey affair is likely between two solid defensive units."
            modifiers['under_2.5'] = 1.20 # 20% boost
            modifiers['draw'] = 1.05      # Slight boost to draw prob

        # An attacking team vs a defensive team can be a chess match
        elif home_style == 'Attacking' and away_style == 'Defensive':
            insight = f"Classic attack vs defense: {home_team.name}'s offense against {away_team.name}'s solid backline."
            modifiers['under_2.5'] = 1.05
            modifiers['draw'] = 1.05

        elif home_style == 'Defensive' and away_style == 'Attacking':
            insight = f"Classic attack vs defense: {away_team.name}'s offense against {home_team.name}'s solid backline."
            modifiers['under_2.5'] = 1.05
            modifiers['draw'] = 1.05
        
        # High-variance teams make for unpredictable games
        if 'High-Variance' in [home_style, away_style]:
            insight += " The presence of a high-variance team adds unpredictability."
            modifiers['over_2.5'] = 1.10 # Unpredictable games can lead to goals

        return TacticalAnalysis(
            home_archetype=home_style,
            away_archetype=away_style,
            clash_insight=insight,
            probability_modifiers=modifiers
        )
