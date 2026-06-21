# risk/kelly.py
import logging

logger = logging.getLogger(__name__)

class KellyEngine:
    """
    Computes optimal stakes using the Kelly Criterion.
    """
    def __init__(self, fraction: float = 0.5, max_stake_pct: float = 0.25):
        self.fraction = fraction # Fractional Kelly (e.g. 0.5 for Half-Kelly)
        self.max_stake_pct = max_stake_pct

    def calculate_stake(self, probability: float, odds: float, bankroll: float) -> float:
        """
        f* = (bp - q) / b
        b = decimal odds - 1
        p = probability
        q = 1 - p
        """
        if odds <= 1: return 0.0
        
        b = odds - 1
        p = probability
        q = 1 - p
        
        if p == 0: return 0.0
        
        kelly_f = (b * p - q) / b
        
        # Apply fractional Kelly and cap
        final_f = max(0, kelly_f * self.fraction)
        final_f = min(final_f, self.max_stake_pct)
        
        recommended_stake = bankroll * final_f
        
        logger.debug(f"Kelly: Prob={p}, Odds={odds}, Bank={bankroll} -> Stake={recommended_stake}")
        return float(recommended_stake)
