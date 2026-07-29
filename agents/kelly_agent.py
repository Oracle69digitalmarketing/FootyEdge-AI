class KellyAgent:
    """
    Shared agent for calculating optimal stake sizing using the Kelly Criterion.
    Replaces heuristic stake sizing with a mathematically grounded approach.
    """
    
    def __init__(self, fractional_kelly: float = 0.25):
        self.fractional_kelly = fractional_kelly

    def calculate_stake(self, probability: float, odds: float) -> float:
        """
        Calculates the recommended stake percentage using the Kelly formula:
        f* = (bp - q) / b
        where:
        b = decimal odds - 1
        p = probability of winning
        q = probability of losing (1 - p)
        """
        if odds <= 1.0 or probability <= 0:
            return 0.0
            
        b = odds - 1
        p = probability
        q = 1.0 - p
        
        # Kelly percentage calculation
        kelly_f = (b * p - q) / b
        
        # Requirement CR-014: Never return negative values for non-positive EV
        if kelly_f <= 0:
            return 0.0
            
        # Apply fractional Kelly for risk management
        suggested_stake = kelly_f * self.fractional_kelly
        
        # Return as percentage (0-100)
        return round(suggested_stake * 100, 2)
