# signals/telegram_engine.py
import os
import httpx
import logging
from typing import Dict, Any, List

logger = logging.getLogger(__name__)

class TelegramEngine:
    """
    Formats and sends betting signals to Telegram.
    """
    def __init__(self, token: str = None, chat_id: str = None):
        self.token = token or os.environ.get("TELEGRAM_BOT_TOKEN")
        self.chat_id = chat_id or os.environ.get("TELEGRAM_CHAT_ID")
        self.api_url = f"https://api.telegram.org/bot{self.token}/sendMessage" if self.token else None

    def format_signal(self, bet: Dict[str, Any], match: Dict[str, Any]) -> str:
        tier_emoji = "💎" if bet['tier'] == "Premium" else "🔥" if bet['tier'] == "Strong" else "✅"
        
        message = (
            f"{tier_emoji} *FOOTYEDGE AI SIGNAL - {bet['tier'].upper()}*\n\n"
            f"⚽️ *Match:* {match['home_team']['name']} vs {match['away_team']['name']}\n"
            f"🏆 *League:* {match['league']['name']} ({match['league']['country']})\n"
            f"⏰ *Kickoff:* {match['date']}\n\n"
            f"🎯 *Selection:* {bet['selection'].upper()}\n"
            f"📊 *Market:* {bet['market']}\n"
            f"📈 *Odds:* {bet['odds']}\n"
            f"🔮 *AI Prob:* {round(bet['probability'] * 100, 1)}%\n"
            f"💰 *Expected Value:* +{round(bet['ev'] * 100, 1)}%\n"
            f"📏 *Rec. Stake:* {round(bet.get('stake', 0), 2)} units\n\n"
            f"_{'Sharp Money Detected! 🚀' if bet.get('is_sharp') else ''}_"
        )
        return message

    async def send_message(self, text: str):
        if not self.api_url or not self.chat_id:
            logger.warning("Telegram: Bot token or Chat ID not configured. Message suppressed.")
            print(f"--- TELEGRAM SIGNAL SUPPRESSED ---\n{text}\n----------------------------------")
            return False

        try:
            async with httpx.AsyncClient() as client:
                res = await client.post(self.api_url, json={
                    "chat_id": self.chat_id,
                    "text": text,
                    "parse_mode": "Markdown"
                })
                return res.status_code == 200
        except Exception as e:
            logger.error(f"Telegram: Failed to send message: {e}")
            return False
