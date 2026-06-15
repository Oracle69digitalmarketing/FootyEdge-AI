# probability/hybrid_engine.py
import pickle
import numpy as np
from typing import Dict, List, Any
from probability.poisson import PoissonEngine
from feature_engine import FeatureEngine
import os

class HybridEngine:
    """
    Blends ML and Poisson probabilities for final prediction.
    """
    def __init__(self, model_path: str = "models/footy_model_v1.pkl", ml_weight: float = 0.6):
        self.ml_weight = ml_weight
        self.poisson_weight = 1.0 - ml_weight
        self.poisson_engine = PoissonEngine()
        self.fe = FeatureEngine()
        
        if os.path.exists(model_path):
            with open(model_path, 'rb') as f:
                self.model = pickle.load(f)
        else:
            self.model = None

    def predict(self, match_data: Dict, home_history: List[Dict], away_history: List[Dict]) -> Dict[str, float]:
        # 1. Poisson Probabilities
        # (Using attack/defense strength as xG proxies if real xG is missing)
        home_xg = match_data.get('home_xg', 1.5)
        away_xg = match_data.get('away_xg', 1.2)
        p_poisson = self.poisson_engine.calculate_probabilities(home_xg, away_xg)
        
        # 2. ML Probabilities
        if self.model:
            features = self.fe.compute_features(match_data, home_history, away_history)
            ml_probs = self.model.predict_proba(features.reshape(1, -1))[0]
            # ML Order: 0:H, 1:D, 2:A
            p_ml = {"home": ml_probs[0], "draw": ml_probs[1], "away": ml_probs[2]}
        else:
            p_ml = p_poisson # Fallback
            
        # 3. Hybrid Blending
        final_probs = {
            "home": (self.ml_weight * p_ml["home"]) + (self.poisson_weight * p_poisson["home"]),
            "draw": (self.ml_weight * p_ml["draw"]) + (self.poisson_weight * p_poisson["draw"]),
            "away": (self.ml_weight * p_ml["away"]) + (self.poisson_weight * p_poisson["away"])
        }
        
        # Re-normalize to ensure sum == 1
        total = sum(final_probs.values())
        for k in final_probs: final_probs[k] /= total
            
        return final_probs
