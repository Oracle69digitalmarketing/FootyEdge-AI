import numpy as np
from scipy.stats import poisson
from typing import Dict
from agents.models import GoalDistribution

class GoalDistributionAgent:
    """
    Shared agent for calculating Poisson-based goal distributions and market probabilities.
    Centralizes the logic to ensure consistency between nightly pipeline and on-demand API.
    """
    
    def __init__(self, max_goals: int = 10):
        self.max_goals = max_goals

    def calculate(self, home_xg: float, away_xg: float) -> GoalDistribution:
        """
        Computes a full probability grid and derived market probabilities.
        """
        # Ensure non-negative xG
        h_xg = max(0.01, home_xg)
        a_xg = max(0.01, away_xg)
        
        # 1. Generate 2D Poisson Grid
        home_pmf = poisson.pmf(np.arange(self.max_goals), h_xg)
        away_pmf = poisson.pmf(np.arange(self.max_goals), a_xg)
        
        # Normalize to ensure sums to 1.0 (AR-008)
        home_pmf /= home_pmf.sum()
        away_pmf /= away_pmf.sum()
        
        grid = np.outer(home_pmf, away_pmf)
        
        # 2. Derive 3-Way Probabilities
        home_win = float(np.sum(np.tril(grid, -1)))
        draw = float(np.sum(np.diag(grid)))
        away_win = float(np.sum(np.triu(grid, 1)))
        
        # 3. Market: Over/Under 2.5 Goals
        # Under 2.5 = scores (0,0), (1,0), (0,1), (1,1), (2,0), (0,2)
        under_25 = 0.0
        for i in range(3):
            for j in range(3):
                if i + j < 2.5:
                    under_25 += grid[i, j]
        
        over_25 = 1.0 - under_25
        
        # 4. Market: Both Teams to Score (BTTS)
        # BTTS Yes = 1 - P(Home 0) - P(Away 0) + P(0,0)
        # Or more simply: sum of grid where both i > 0 and j > 0
        btts_yes = float(np.sum(grid[1:, 1:]))
        
        # 5. Correct Score Odds (Implied)
        correct_scores = {}
        for i in range(min(6, self.max_goals)):
            for j in range(min(6, self.max_goals)):
                prob = grid[i, j]
                if prob > 0:
                    correct_scores[f"{i}-{j}"] = 1.0 / prob
        
        return GoalDistribution(
            score_matrix=grid,
            home_xG=h_xg,
            away_xG=a_xg,
            home_win_prob=home_win,
            draw_prob=draw,
            away_win_prob=away_win,
            over_under={"2.5": over_25},
            both_teams_score=btts_yes,
            correct_score_odds=correct_scores,
            exact_goal_markets={} # Placeholder for future expansion
        )
