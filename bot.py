import os
import httpx
from datetime import datetime
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

TELEGRAM_TOKEN = os.environ.get('TELEGRAM_BOT_TOKEN')
API_URL = os.environ.get('API_URL', 'http://localhost:8000/api')

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "⚽ *FootyEdge AI*\n\n"
        "AI-powered football betting intelligence.\n"
        "Predict matches, find value bets.\n\n"
        "Commands:\n"
        "/predict Man City vs Arsenal\n"
        "/value\n"
        "/team <team_name>\n"
        "/standings <league_name>\n"
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
    
    # Try to find if there's an upcoming match to get live odds
    odds = {
        "home_win": 1.85, "draw": 3.40, "away_win": 4.20,
        "Over 2.5": 1.90, "Under 2.5": 1.90,
        "BTTS Yes": 1.75, "BTTS No": 2.05
    }

    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            # 1. Search for home team to get ID
            search_res_obj = await client.get(f"{API_URL}/search/teams", params={'q': home})
            search_res = search_res_obj.json()
            if search_res.get('response'):
                # 2. Get matches for this team
                matches_res_obj = await client.get(f"{API_URL}/matches", params={'date': datetime.now().strftime("%Y-%m-%d")})
                matches_res = matches_res_obj.json()
                # This is a bit simplified, ideally we'd look ahead or search for the specific matchup
                if matches_res.get('response'):
                    for m in matches_res['response']:
                        if (m['teams']['home']['name'] == home and m['teams']['away']['name'] == away) or \
                           (m['teams']['away']['name'] == home and m['teams']['home']['name'] == away):
                            fixture_id = m['fixture']['id']
                            # 3. Get odds for this fixture
                            odds_res_obj = await client.get(f"{API_URL}/odds/{fixture_id}")
                            odds_res = odds_res_obj.json()
                            if odds_res.get('default'):
                                odds = odds_res['default']
                                break

            response = await client.post(
                f"{API_URL}/predict",
                json={'home_team': home, 'away_team': away, 'odds': odds}
            )

            if response.status_code == 200:
                data = response.json()
                message = f"""
⚽ *{data['home_team']} vs {data['away_team']}*

📊 *Prediction:*
🏠 *{data['home_team']}*: {data['probabilities']['home_win']:.1%}
🤝 *Draw*: {data['probabilities']['draw']:.1%}
✈️ *{data['away_team']}*: {data['probabilities']['away_win']:.1%}

🎯 *Expected Goals:*
🏠 {data['home_xg']:.2f}
✈️ {data['away_xg']:.2f}
"""
                if data.get('value_bets'):
                    message += "\n\n💰 *Value Bets Found:*"
                    for bet in data['value_bets']:
                        message += f"\n- {bet['market_name']} {bet['selection']} @ {bet['odds']:.2f} (EV: +{bet['ev']:.1%})"
                
                await update.message.reply_text(message, parse_mode='Markdown')
            else:
                await update.message.reply_text(f"Error getting prediction: {response.text}")
        except Exception as e:
            await update.message.reply_text(f"Error: {str(e)}")

async def value(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.chat.send_action(action="typing")
    await update.message.reply_text("Scanning for live value bets across major leagues... this may take a moment.")
    
    async with httpx.AsyncClient(timeout=120.0) as client:
        try:
            response = await client.get(f"{API_URL}/scan-value-bets")

            if response.status_code == 200:
                data = response.json()
                if data:
                    message = "💰 *Live Value Bets*\n\n"
                    for bet in data:
                        message += f"⚽ *{bet['home_team']} vs {bet['away_team']}*\n"
                        message += f"  - {bet['market_name']} {bet['selection']} @ {bet['odds']:.2f}\n"
                        message += f"    EV: +{bet['ev']:.1%}, Stake: {bet['recommended_stake']}\n\n"
                    await update.message.reply_text(message, parse_mode='Markdown')
                else:
                    await update.message.reply_text("No value bets found at the moment.")
            else:
                await update.message.reply_text("Error fetching value bets.")
        except Exception as e:
            await update.message.reply_text(f"Error: {str(e)}")

async def team(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("Use: /team <team_name>")
        return
    
    team_name = ' '.join(context.args)
    await update.message.chat.send_action(action="typing")
    
    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            # Search for the team first
            search_response = await client.get(f"{API_URL}/search/teams", params={'q': team_name})
            if search_response.status_code != 200 or not search_response.json().get('results'):
                await update.message.reply_text(f"Could not find team: {team_name}")
                return

            team_id = search_response.json()['results'][0]['id']

            # Get team details
            detail_response = await client.get(f"{API_URL}/teams/{team_id}/detail")
            if detail_response.status_code != 200:
                await update.message.reply_text(f"Could not get details for team: {team_name}")
                return
            
            data = detail_response.json()
            message = f"""
*Team: {data['name']}*
*Country:* {data['country']}
*League:* {data.get('league', 'N/A')}

*Stats:*
- Elo Rating: {data.get('elo_rating', 'N/A')}
- Attack: {data.get('attack_strength', 'N/A')}
- Defense: {data.get('defense_strength', 'N/A')}
"""
            await update.message.reply_text(message, parse_mode='Markdown')
            
        except Exception as e:
            await update.message.reply_text(f"Error: {str(e)}")


async def standings(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("Use: /standings <league_name>")
        return
        
    league_name = ' '.join(context.args)
    await update.message.chat.send_action(action="typing")

    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            # Search for league
            search_response = await client.get(f"{API_URL}/search/leagues", params={'q': league_name})
            if search_response.status_code != 200 or not search_response.json().get('results'):
                await update.message.reply_text(f"Could not find league: {league_name}")
                return

            league_id = search_response.json()['results'][0]['id']

            # Get standings
            standings_response = await client.get(f"{API_URL}/standings/{league_id}")
            if standings_response.status_code != 200:
                await update.message.reply_text(f"Could not get standings for league: {league_name}")
                return

            data = standings_response.json()
            
            message = f"*Standings for {data.get('name', league_name)}*\n\n"
            message += "```\n"
            message += "P | Team              | P | W | D | L | GD | Pts\n"
            message += "--------------------------------------------------\n"
            for team in data.get('standings', [])[:10]: # Top 10
                message += (f"{team['position']:<2} | {team['team']['name']:<17} | "
                            f"{team['playedGames']:<2} | {team['won']:<2} | {team['draw']:<2} | {team['lost']:<2} | "
                            f"{team['goalDifference']:<3} | {team['points']}\n")
            message += "```"

            await update.message.reply_text(message, parse_mode='Markdown')

        except Exception as e:
            await update.message.reply_text(f"Error: {str(e)}")


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "📖 *FootyEdge AI Help*\n\n"
        "*Commands:*\n"
        "/predict Team1 vs Team2 - Get match prediction\n"
        "/value - Today's value bets\n"
        "/team <team_name> - Get team statistics\n"
        "/standings <league_name> - Get league standings\n"
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
    app.add_handler(CommandHandler("team", team))
    app.add_handler(CommandHandler("standings", standings))
    
    print("🤖 FootyEdge Bot running...")
    app.run_polling()

if __name__ == "__main__":
    main()
