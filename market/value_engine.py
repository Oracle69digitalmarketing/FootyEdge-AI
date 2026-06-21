# market/value_engine.py
from typing import Dict, List, Any

class ValueEngine:
    """
    Identifies betting inefficiencies by comparing AI probabilities with market odds.
    """
    def __init__(self, value_threshold: float = 0.03):
        self.value_threshold = value_threshold
        self.tiers = {
            "Premium": 0.12,
            "Strong": 0.07,
            "Value": 0.03
        }

    def calculate_ev(self, probability: float, odds: float) -> float:
        """EV = (probability * odds) - 1"""
        if not odds or odds <= 1: return -1.0
        return (probability * odds) - 1

    def identify_value_bets(self, ai_probs: Dict[str, float], market_odds: Dict[str, float]) -> List[Dict[str, Any]]:
        """
        AI Probs: {'home': 0.5, 'draw': 0.25, 'away': 0.25}
        Market Odds: {'home': 2.1, 'draw': 3.4, 'away': 4.0}
        """
        value_bets = []
        
        for selection in ['home', 'draw', 'away']:
            prob = ai_probs.get(selection)
            odd = market_odds.get(selection)
            
            if prob is None or odd is None: continue
            
            ev = self.calculate_ev(prob, float(odd))
            
            if ev >= self.value_threshold:
                # Assign Tier
                tier = "Value"
                for t_name, t_val in sorted(self.tiers.items(), key=lambda x: x[1], reverse=True):
                    if ev >= t_val:
                        tier = t_name
                        break
                
                value_bets.append({
                    "selection": selection,
                    "market": "1X2",
                    "odds": odd,
                    "probability": prob,
                    "ev": round(ev, 4),
                    "tier": tier
                })
                
        return sorted(value_bets, key=lambda x: x['ev'], reverse=True)
