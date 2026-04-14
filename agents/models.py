# agents/models.py
"""
Data models for the Bookmaker's Mind agent system
"""
from dataclasses import dataclass, field
from typing import Dict, List, Any, Optional
import numpy as np

@dataclass
class ValueBet:
    """Represents a single, valuable betting opportunity."""
    market_name: str  # e.g., "Match Odds", "Over/Under 2.5"
    selection: str    # e.g., "Manchester City to win", "Over"
    odds: float
    our_probability: float
    ev: float
    kelly_percentage: float
    recommended_stake: str
    tier: str = "Solid" # e.g., "Hot", "Solid", "Neutral"

@dataclass
class TeamStrength:
    name: str
    overall_rating: float
    home_advantage: float
    away_disadvantage: float
    form_rating: float
    attack_strength: float
    defense_strength: float
    xG_performance: float
    variance_profile: float
    competition_factor: float
    midfield_rating: float = 1500

@dataclass
class PlayerImpact:
    player: Any # Using Any for now, should be a Player object
    position: str
    total_impact: float
    details: Dict[str, float]

@dataclass
class MatchupAnalysis:
    home_advantage_modifier: float
    away_advantage_modifier: float
    key_battles: Dict[str, Any]
    predicted_tempo: str
    historical_pattern: Optional[Dict[str, Any]]
    style_clash_severity: float
    likely_score_pattern: str
    key_factors: List[str] = field(default_factory=list)


@dataclass
class GoalDistribution:
    score_matrix: np.ndarray
    home_xG: float
    away_xG: float
    home_win_prob: float
    draw_prob: float
    away_win_prob: float
    over_under: Dict[str, float]
    both_teams_score: float
    correct_score_odds: Dict[str, float]
    exact_goal_markets: Dict[str, float]

@dataclass
class MarketOutput:
    goal_distribution: GoalDistribution
    odds: Dict[str, float]
    implied_probabilities: Dict[str, float]
    key_factors: List[str]
    confidence: float

@dataclass
class Fixture:
    home_team: str
    away_team: str
    context: Dict[str, Any] = field(default_factory=dict)

@dataclass
class Pattern:
    name: str
    condition: str
    impact: float
    confidence: float
    significant: bool = True
