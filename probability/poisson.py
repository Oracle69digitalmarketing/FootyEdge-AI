# probability/poisson.py
import math
import numpy as np
from typing import Dict, Tuple

class PoissonEngine:
    """
    Computes match probabilities based on Poisson distribution of goals.
    """
    def __init__(self, max_goals: int = 12):
        self.max_goals = max_goals

    def _poisson_prob(self, k: int, lamb: float) -> float:
        if lamb <= 0: return 1.0 if k == 0 else 0.0
        return (lamb**k * math.exp(-lamb)) / math.factorial(k)

    def calculate_probabilities(self, home_xg: float, away_xg: float) -> Dict[str, float]:
        """
        Returns probabilities for H, D, A, and goal markets.
        """
        matrix = np.zeros((self.max_goals + 1, self.max_goals + 1))
        
        for h in range(self.max_goals + 1):
            for a in range(self.max_goals + 1):
                matrix[h, a] = self._poisson_prob(h, home_xg) * self._poisson_prob(a, away_xg)

        p_home = np.sum(np.tril(matrix, -1))
        p_draw = np.sum(np.diag(matrix))
        p_away = np.sum(np.triu(matrix, 1))
        
        # Normalize to ensure sum ~ 1
        total = p_home + p_draw + p_away
        if total > 0:
            p_home /= total
            p_draw /= total
            p_away /= total

        return {
            "home": float(p_home),
            "draw": float(p_draw),
            "away": float(p_away),
            "over_2_5": float(1 - np.sum(matrix[0:3, 0:3]) if np.sum(matrix[0:3, 0:3]) < 1 else 0.0) # Approximation
        }
