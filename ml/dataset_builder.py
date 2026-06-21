# ml/dataset_builder.py
import pandas as pd
import numpy as np
from feature_engine import FeatureEngine
import logging
from tqdm import tqdm

logger = logging.getLogger(__name__)

class DatasetBuilder:
    def __init__(self, csv_path: str):
        self.csv_path = csv_path
        self.fe = FeatureEngine()

    def build(self, output_path: str, limit: int = 10000):
        """
        Processes historical CSV and generates a feature-rich training dataset.
        """
        df = pd.read_csv(self.csv_path)
        df = df.sort_values('MatchDate')
        
        # Filter for rows with results
        df = df.dropna(subset=['FTResult'])
        if limit: df = df.head(limit)

        data = []
        labels = []
        
        # We need team history to build features.
        # This is a simplified version; real implementation would use a sliding window.
        team_histories = {} 

        for _, row in tqdm(df.iterrows(), total=len(df), desc="Building Dataset"):
            h_team = row['HomeTeam']
            a_team = row['AwayTeam']
            
            h_hist = team_histories.get(h_team, [])
            a_hist = team_histories.get(a_team, [])
            
            # Compute features using the same engine as inference
            # Note: We pass mock history here as constructing 230k histories in one go is memory-intensive.
            # In production, we'd use a more optimized rolling aggregation.
            match_data = {
                "home_elo": row.get('HomeElo', 1500),
                "away_elo": row.get('AwayElo', 1500),
                "odds": {"home": row.get('OddHome'), "draw": row.get('OddDraw'), "away": row.get('OddAway')}
            }
            
            features = self.fe.compute_features(match_data, h_hist, a_hist)
            data.append(features)
            
            # Label: H=0, D=1, A=2
            res = row['FTResult']
            label = 0 if res == 'H' else 1 if res == 'D' else 2
            labels.append(label)
            
            # Update history (limited to 20 for memory)
            m_res = {
                "result": 'win' if res == 'H' else 'draw' if res == 'D' else 'loss',
                "goals_scored": row['FTHome'],
                "goals_conceded": row['FTAway']
            }
            team_histories[h_team] = ([m_res] + h_hist)[:20]
            
            m_res_a = {
                "result": 'win' if res == 'A' else 'draw' if res == 'D' else 'loss',
                "goals_scored": row['FTAway'],
                "goals_conceded": row['FTHome']
            }
            team_histories[a_team] = ([m_res_a] + a_hist)[:20]

        feature_df = pd.DataFrame(data, columns=self.fe.get_feature_names())
        feature_df['label'] = labels
        feature_df.to_csv(output_path, index=False)
        logger.info(f"Dataset built successfully: {output_path}")
