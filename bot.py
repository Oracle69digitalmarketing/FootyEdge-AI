import os
import requests
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

TELEGRAM_TOKEN = os.environ.get('TELEGRAM_BOT_TOKEN')
API_URL = os.environ.get('API_URL', 'http://localhost:8000')

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "⚽ *FootyEdge AI*\n\n"
        "AI-powered football betting intelligence.\n"
        "Predict matches, find value bets.\n\n"
        "Commands:\n"
        "/predict Man City vs Arsenal\n"
        "/value\n"
        "/help\n\n"
        "Powered by Oracle69 Systems",
        parse_mode='Markdown'
    )

async def predict(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args or 'vs' not in ' '.join(context.args):
        await update.message.reply_text("Use: /predict Man City vs Arsenal")
        return
    
    text = ' '.join(context.args)
    home, away = text.split('vs')
    home, away = home.strip(), away.strip()
    
    await update.message.chat.send_action(action="typing")
    
    try:
        response = requests.post(
            f"{API_URL}/predict",
            json={'home_team': home, 'away_team': away},
            timeout=10
        )
        
        if response.status_code == 200:
            data = response.json()
            message = f"""
⚽ *{data['home_team']} vs {data['away_team']}*

📊 *Prediction:*
🏠 *{data['home_team']}*: {data['home_win']:.1%}
🤝 *Draw*: {data['draw']:.1%}
✈️ *{data['away_team']}*: {data['away_win']:.1%}

🎯 *Expected Goals:*
🏠 {data['home_team']}: {data['home_xg']}
✈️ {data['away_team']}: {data['away_xg']}

📈 *Confidence:* {data['confidence']:.1%}
"""
            if data.get('value_bets'):
                best = data['value_bets'][0]
                message += f"\n💰 *Value Bet:* {best['selection']} @ {best['odds']:.2f}\n   EV: +{best['ev']:.1%}"
            
            await update.message.reply_text(message, parse_mode='Markdown')
        else:
            await update.message.reply_text("Error getting prediction")
    except Exception as e:
        await update.message.reply_text(f"Error: {str(e)}")

async def value(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "💰 *Value Bets*\n\n"
        "Check back for today's best EV+ opportunities!\n\n"
        "Use /predict to get predictions with value bets.",
        parse_mode='Markdown'
    )

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "📖 *FootyEdge AI Help*\n\n"
        "*Commands:*\n"
        "/predict Team1 vs Team2 - Get match prediction\n"
        "/value - Today's value bets\n"
        "/start - Welcome\n"
        "/help - This message\n\n"
        "*Example:* `/predict Manchester City vs Arsenal`\n\n"
        "Powered by Oracle69 Systems",
        parse_mode='Markdown'
    )

def main():
    if not TELEGRAM_TOKEN:
        print("TELEGRAM_BOT_TOKEN not set!")
        return
    
    app = Application.builder().token(TELEGRAM_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("predict", predict))
    app.add_handler(CommandHandler("value", value))
    
    print("🤖 FootyEdge Bot running...")
    app.run_polling()

if __name__ == "__main__":
    main()
