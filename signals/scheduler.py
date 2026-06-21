# signals/scheduler.py
import asyncio
import logging
from typing import List, Dict
from data.service import DataService
from probability.hybrid_engine import HybridEngine
from market.value_engine import ValueEngine
from market.sharp_detector import SharpDetector
from risk.kelly import KellyEngine
from risk.bankroll import BankrollManager
from signals.telegram_engine import TelegramEngine

logger = logging.getLogger(__name__)

class SignalScheduler:
    """
    Orchestrates the daily signal generation and distribution.
    """
    def __init__(self):
        self.data_service = DataService()
        self.hybrid = HybridEngine()
        self.value_engine = ValueEngine()
        self.sharp_detector = SharpDetector()
        self.kelly = KellyEngine()
        self.bankroll = BankrollManager()
        self.telegram = TelegramEngine()

    async def generate_daily_signals(self):
        logger.info("Starting daily signal generation...")
        matches = await self.data_service.get_upcoming_matches()
        
        for match in matches:
            # Note: For real-time we'd fetch team histories from DB
            h_hist = [] # Simplified
            a_hist = []
            
            # 1. Prediction
            probs = self.hybrid.predict(match, h_hist, a_hist)
            
            # 2. Value Detection
            value_bets = self.value_engine.identify_value_bets(probs, match['odds'])
            
            for bet in value_bets:
                # 3. Sharp Detection (if opening odds available)
                # bet['is_sharp'] = self.sharp_detector.is_sharp_confirmed(...) 
                
                # 4. Staking
                bet['stake'] = self.kelly.calculate_stake(bet['probability'], bet['odds'], self.bankroll.get_balance())
                
                # 5. Distribute
                msg = self.telegram.format_signal(bet, match)
                await self.telegram.send_message(msg)

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    scheduler = SignalScheduler()
    asyncio.run(scheduler.generate_daily_signals())
