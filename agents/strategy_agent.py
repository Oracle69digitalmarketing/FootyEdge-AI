import re
from typing import Dict, List, Any

class StrategyAgent:
    """
    Analyzes natural language betting strategies and provides risk/EV assessment.
    """
    def __init__(self):
        self.market_patterns = {
            "win": r"(?P<team>.+?)\s+(?:to\s+)?win",
            "draw": r"(?P<team1>.+?)\s+vs\s+(?P<team2>.+?)\s+draw",
            "over": r"over\s+(?P<value>\d+\.?\d*)\s+(?:in\s+)?(?P<match>.+?)(?:\s+match)?",
            "under": r"under\s+(?P<value>\d+\.?\d*)\s+(?:in\s+)?(?P<match>.+?)(?:\s+match)?",
            "btts": r"btts\s+(?:in\s+)?(?P<match>.+?)(?:\s+match)?",
        }

    def parse_strategy(self, text: str) -> List[Dict[str, Any]]:
        selections = []
        lines = text.split(',')
        for line in lines:
            line = line.strip().lower()
            found = False
            for market, pattern in self.market_patterns.items():
                match = re.search(pattern, line)
                if match:
                    selections.append({
                        "market": market,
                        "details": match.groupdict(),
                        "raw": line
                    })
                    found = True
                    break
            if not found:
                selections.append({"market": "unknown", "raw": line})
        return selections

    def analyze(self, selections: List[Dict[str, Any]], stake: float = 1000) -> Dict[str, Any]:
        """
        Simulates analysis of the strategy.
        In a real scenario, this would fetch live odds and AI probabilities.
        """
        num_selections = len(selections)
        if num_selections == 0:
            return {"error": "No selections found in your strategy."}

        # Simulated analysis metrics
        avg_prob = 0.65 - (num_selections * 0.05) # More selections = lower combined prob
        confidence = max(0.4, avg_prob)
        ev = 0.08 + (num_selections * 0.02) # Simulated edge
        
        risk_level = "Low" if num_selections <= 2 else "Medium" if num_selections <= 4 else "High"
        
        recommendation = ""
        if num_selections > 3:
            recommendation = "This is a high-variance accumulator. Consider using a 'System Bet' (e.g., 3/4) to mitigate risk."
        elif ev > 0.1:
            recommendation = "Strong value detected. The selections align with current AI market inefficiencies."
        else:
            recommendation = "Standard risk profile. Ensure you are not over-exposed on a single league."

        return {
            "selections_parsed": selections,
            "metrics": {
                "combined_odds_est": round(1.9 ** num_selections, 2),
                "win_probability": f"{round(confidence * 100, 1)}%",
                "expected_value": f"+{round(ev * 100, 1)}%",
                "risk_score": risk_level
            },
            "recommendation": recommendation,
            "summary": f"Analyzed {num_selections} selections. Combined strategy shows a {risk_level} risk profile with a positive EV of {round(ev * 100, 1)}%."
        }
