# risk/bankroll.py
import json
import os
import logging

logger = logging.getLogger(__name__)

class BankrollManager:
    """
    Manages and persists the platform bankroll.
    """
    def __init__(self, initial_amount: float = 10000.0, persistence_path: str = "data/bankroll.json"):
        self.persistence_path = persistence_path
        self.amount = self._load() or initial_amount

    def _load(self) -> float:
        if os.path.exists(self.persistence_path):
            try:
                with open(self.persistence_path, 'r') as f:
                    data = json.load(f)
                    return float(data.get('amount', 0))
            except Exception as e:
                logger.error(f"Failed to load bankroll: {e}")
        return None

    def _save(self):
        os.makedirs(os.path.dirname(self.persistence_path), exist_ok=True)
        try:
            with open(self.persistence_path, 'w') as f:
                json.dump({'amount': self.amount}, f)
        except Exception as e:
            logger.error(f"Failed to save bankroll: {e}")

    def update(self, profit_loss: float):
        self.amount += profit_loss
        self._save()
        logger.info(f"Bankroll updated: {self.amount} (PL: {profit_loss})")

    def get_balance(self) -> float:
        return self.amount
