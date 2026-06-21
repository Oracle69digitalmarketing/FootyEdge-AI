# backtesting/backtester.py
import pandas as pd
import numpy as np
import logging
from typing import Dict, List, Any
from probability.hybrid_engine import HybridEngine
from market.value_engine import ValueEngine
from risk.kelly import KellyEngine
from tqdm import tqdm

logger = logging.getLogger(__name__)

class Backtester:
    """
    Simulates the betting strategy on historical data.
    """
    def __init__(self, initial_bankroll: float = 10000.0):
        self.initial_bankroll = initial_bankroll
        self.bankroll = initial_bankroll
        self.hybrid = HybridEngine()
        self.value_engine = ValueEngine()
        self.kelly = KellyEngine()
        self.history = []

    def run(self, csv_path: str, limit: int = 100):
        df = pd.read_csv(csv_path)
        df = df.sort_values('MatchDate')
        df = df.dropna(subset=['FTResult', 'OddHome', 'OddDraw', 'OddAway'])
        
        if limit: df = df.head(limit)
        
        # We need a rolling history for the feature engine
        team_histories = {}

        for _, row in tqdm(df.iterrows(), total=len(df), desc="Backtesting"):
            h_team = row['HomeTeam']
            a_team = row['AwayTeam']
            
            h_hist = team_histories.get(h_team, [])
            a_hist = team_histories.get(a_team, [])
            
            match_data = {
                "home_elo": row.get('HomeElo', 1500),
                "away_elo": row.get('AwayElo', 1500),
                "odds": {"home": row.get('OddHome'), "draw": row.get('OddDraw'), "away": row.get('OddAway')}
            }
            
            # 1. Get AI Probabilities
            probs = self.hybrid.predict(match_data, h_hist, a_hist)
            
            # 2. Identify Value Bets
            value_bets = self.value_engine.identify_value_bets(probs, match_data['odds'])
            
            # 3. Apply Staking if Value Found
            if value_bets:
                best_bet = value_bets[0] # Take highest EV bet
                stake = self.kelly.calculate_stake(best_bet['probability'], best_bet['odds'], self.bankroll)
                
                if stake > 0:
                    # 4. Resolve Outcome
                    res = row['FTResult']
                    win_map = {'home': 'H', 'draw': 'D', 'away': 'A'}
                    is_win = win_map[best_bet['selection']] == res
                    
                    pnl = (stake * (best_bet['odds'] - 1)) if is_win else -stake
                    self.bankroll += pnl
                    
                    self.history.append({
                        'date': row['MatchDate'],
                        'teams': f"{h_team} vs {a_team}",
                        'selection': best_bet['selection'],
                        'odds': best_bet['odds'],
                        'stake': stake,
                        'is_win': is_win,
                        'pnl': pnl,
                        'bankroll': self.bankroll
                    })

            # Update histories for the next matches
            res = row['FTResult']
            m_res_h = {"result": 'win' if res == 'H' else 'draw' if res == 'D' else 'loss', "goals_scored": row['FTHome'], "goals_conceded": row['FTAway']}
            team_histories[h_team] = ([m_res_h] + h_hist)[:20]
            m_res_a = {"result": 'win' if res == 'A' else 'draw' if res == 'D' else 'loss', "goals_scored": row['FTAway'], "goals_conceded": row['FTHome']}
            team_histories[a_team] = ([m_res_a] + a_hist)[:20]

        return self.generate_report()

    def generate_report(self) -> Dict[str, Any]:
        if not self.history:
            return {"error": "No bets placed during backtest."}
            
        df_hist = pd.DataFrame(self.history)
        total_bets = len(df_hist)
        wins = df_hist['is_win'].sum()
        total_pnl = self.bankroll - self.initial_bankroll
        total_staked = df_hist['stake'].sum()
        
        # Max Drawdown
        df_hist['cum_max'] = df_hist['bankroll'].cummax()
        df_hist['drawdown'] = (df_hist['cum_max'] - df_hist['bankroll']) / df_hist['cum_max']
        max_dd = df_hist['drawdown'].max()

        return {
            "total_bets": total_bets,
            "win_rate": f"{round((wins / total_bets) * 100, 2)}%",
            "total_pnl": round(total_pnl, 2),
            "yield": f"{round((total_pnl / total_staked) * 100, 2)}%" if total_staked > 0 else "0%",
            "roi": f"{round((total_pnl / self.initial_bankroll) * 100, 2)}%",
            "max_drawdown": f"{round(max_dd * 100, 2)}%",
            "profit_factor": round(df_hist[df_hist['pnl'] > 0]['pnl'].sum() / abs(df_hist[df_hist['pnl'] < 0]['pnl'].sum()), 2) if any(df_hist['pnl'] < 0) else "Inf",
            "final_bankroll": round(self.bankroll, 2)
        }

if __name__ == "__main__":
    bt = Backtester()
    report = bt.run('data/club-data/matches.csv', limit=1000)
    print("--- Backtest Report ---")
    for k, v in report.items():
        print(f"{k}: {v}")
