# market/sharp_detector.py
from typing import Dict, List, Optional
import logging

logger = logging.getLogger(__name__)

class SharpDetector:
    """
    Detects significant odds movements ("Sharp Money").
    """
    def __init__(self, drop_threshold: float = 0.08):
        self.drop_threshold = drop_threshold

    def analyze_movement(self, opening_odds: Dict[str, float], current_odds: Dict[str, float]) -> List[Dict]:
        """
        Opening Odds: {'home': 2.0, 'draw': 3.4, 'away': 4.0}
        Current Odds: {'home': 1.8, 'draw': 3.5, 'away': 4.2}
        """
        alerts = []
        for selection in opening_odds:
            if selection not in current_odds: continue
            
            o = float(opening_odds[selection])
            c = float(current_odds[selection])
            
            if o <= 1 or c <= 1: continue
            
            # Drop calculation: (opening - current) / opening
            # e.g. (2.0 - 1.8) / 2.0 = 0.1 (10% drop)
            drop = (o - c) / o
            
            if drop >= self.drop_threshold:
                alerts.append({
                    "selection": selection,
                    "opening": o,
                    "current": c,
                    "drop_pct": round(drop * 100, 2),
                    "is_sharp": True
                })
                
        return alerts

    def is_sharp_confirmed(self, alerts: List[Dict], target_selection: str) -> bool:
        """Checks if a specific selection has sharp money flags."""
        return any(a['selection'] == target_selection and a['is_sharp'] for a in alerts)
