"""
FootyEdge AI - Core Prediction Engine (Production Ready - Hybrid Data Model)
"""
import httpx
import numpy as np
from datetime import datetime, timedelta
import os
import json
from typing import Dict, List, Any, Tuple
import logging
import math
from pathlib import Path

from agents.team_strength import TeamStrengthAgent
from agents.tactical_agent import TacticalAgent
from agents.player_impact import PlayerImpactAgent
from agents.models import TeamStrength, ValueBet
from football_api_client import FootballAPIClient

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class FootyEdgePredictor:
    
    def __init__(self, supabase_url: str = None, supabase_key: str = None, 
                 rapidapi_key: str = None):
        self.rapidapi_key = rapidapi_key or os.environ.get('RAPIDAPI_KEY')
        self.supabase_url = supabase_url or os.environ.get('SUPABASE_URL')
        self.supabase_key = supabase_key or os.environ.get('SUPABASE_KEY')
        
        # Initialize Supabase client if possible
        if self.supabase_url and self.supabase_key:
            from supabase import create_client
            self.supabase = create_client(self.supabase_url, self.supabase_key)
        else:
            self.supabase = None

        self.football_client = FootballAPIClient()
        
        self.cache = {}
        self.cache_ttl = 3600
        self.team_strength_agent = TeamStrengthAgent(supabase_client=self.supabase)
        self.tactical_agent = TacticalAgent()
        self.player_agent = PlayerImpactAgent(football_client=self.football_client, team_agent=self.team_strength_agent)
        self.local_data_path = Path("data/football.json")

    def _init_supabase(self, url, key):
        supabase_url = url or os.environ.get('SUPABASE_URL')
        supabase_key = key or os.environ.get('SUPABASE_KEY')
        if supabase_url and supabase_key:
            try:
                from supabase import create_client; logger.info("Supabase connected successfully"); return create_client(supabase_url, supabase_key)
            except Exception as e:
                logger.error(f"Failed to connect to Supabase: {e}")
        return None


    async def get_team_matches(self, team_name: str, limit: int = 40) -> List[Dict]:
        cache_key = f"team_matches_hybrid_{team_name}"
        cached = self.cache.get(cache_key)
        
        # Increase TTL for historical data to 24 hours (86400s) to save API credits
        if cached and (datetime.now() - cached[1]).total_seconds() < 86400:
            return cached[0]

        # 1. Fetch from Supabase FIRST (Our primary dataset)
        db_matches = await self._fetch_db_matches(team_name, limit)
        
        # 2. Decision Logic: Do we REALLY need the Live API?
        # If we have at least 15 matches and the latest one is recent (within 10 days), SKIP API
        needs_live_api = True
        if db_matches and len(db_matches) >= 15:
            latest_match_date = datetime.strptime(db_matches[0]['date'], "%Y-%m-%d")
            if (datetime.now() - latest_match_date).days < 10:
                needs_live_api = False
                logger.info(f"Using Supabase only for {team_name} to save API credits.")

        all_matches = db_matches
        
        if needs_live_api:
            # Only fetch API and Local if Supabase is insufficient or stale
            tasks = [
                self._fetch_api_matches(team_name, limit),
                self._fetch_local_matches_async(team_name)
            ]
            results = await asyncio.gather(*tasks, return_exceptions=True)
            for res in results:
                if isinstance(res, list): all_matches.extend(res)

        # 3. Fallback: only if we have NOTHING
        if not all_matches:
            # ... (rest of the fallback search logic)
            try:
                search_res = await self.football_client.search_teams(team_name)
                if search_res and search_res.get('response'):
                    team_id = search_res['response'][0]['team']['id']
                    res = await self.football_client.get_team_fixtures(team_id, last=limit)
                    if res and res.get('response'):
                        for f in res['response']:
                            all_matches.append(self._parse_api_match(f, team_name))
            except Exception as e:
                logger.error(f"API fallback failed for {team_name}: {e}")

        # 4. Final baseline if all else fails
        if not all_matches:
            all_matches = [{
                'date': datetime.now().strftime("%Y-%m-%d"),
                'is_home': True,
                'goals_scored': 1,
                'goals_conceded': 1,
                'result': 'draw',
                'opponent_name': 'Average Opponent'
            }]

        # 5. Sort, Deduplicate, and Cache
        merged_matches = sorted(all_matches, key=lambda x: x['date'], reverse=True)
        seen_dates = set()
        unique_matches = []
        for m in merged_matches:
            if m['date'] not in seen_dates:
                unique_matches.append(m)
                seen_dates.add(m['date'])
                if len(unique_matches) >= limit:
                    break

        self.cache[cache_key] = (unique_matches, datetime.now())
        return unique_matches

    async def _fetch_db_matches(self, team_name: str, limit: int) -> List[Dict]:
        if not self.supabase: return []
        try:
            team_res = self.supabase.table("teams").select("id").eq("name", team_name).execute()
            if not team_res.data: return []
            team_id = team_res.data[0]['id']
            
            # Fetch home and away in parallel
            h_task = self.supabase.table("matches").select("*").eq("home_team_id", team_id).order("match_date", desc=True).limit(limit).execute()
            a_task = self.supabase.table("matches").select("*").eq("away_team_id", team_id).order("match_date", desc=True).limit(limit).execute()
            
            # Note: supabase-py execute() is currently not natively async in all versions, 
            # but we can wrap it or treat it as sync for now if needed.
            # Assuming standard wrapper for consistency.
            h_res = h_task
            a_res = a_task
            
            matches = []
            for m in (h_res.data or []) + (a_res.data or []):
                is_home = m['home_team_id'] == team_id
                home_goals = m.get('home_goals', 0)
                away_goals = m.get('away_goals', 0)
                result = 'draw'
                if home_goals != away_goals:
                    result = 'win' if (is_home and home_goals > away_goals) or (not is_home and away_goals > home_goals) else 'loss'
                matches.append({
                    'date': m['match_date'].split('T')[0],
                    'is_home': is_home,
                    'goals_scored': home_goals if is_home else away_goals,
                    'goals_conceded': away_goals if is_home else home_goals,
                    'result': result,
                    'opponent_name': 'Unknown (DB)'
                })
            return matches
        except Exception as e:
            logger.error(f"DB fetch failed: {e}")
            return []

    async def _fetch_api_matches(self, team_name: str, limit: int) -> List[Dict]:
        if not self.supabase: return []
        try:
            team_res = self.supabase.table("teams").select("id").eq("name", team_name).execute()
            if not team_res.data: return []
            team_id = team_res.data[0]['id']
            res = await self.football_client.get_team_fixtures(team_id, last=limit)
            if res and res.get('response'):
                return [self._parse_api_match(f, team_name) for f in res['response']]
        except Exception:
            pass
        return []

    async def _fetch_local_matches_async(self, team_name: str) -> List[Dict]:
        # Simple wrapper for now, could use aiofiles for true async I/O
        return self._load_local_matches(team_name)

    def _parse_api_match(self, fixture: Dict, team_name: str) -> Dict:
        f = fixture['fixture']
        t = fixture['teams']
        g = fixture['goals']
        is_home = t['home']['name'] == team_name
        home_score = g['home'] if g['home'] is not None else 0
        away_score = g['away'] if g['away'] is not None else 0

        result = 'draw'
        if home_score != away_score:
            result = 'win' if (is_home and home_score > away_score) or (not is_home and away_score > home_score) else 'loss'

        return {
            'date': f['date'].split('T')[0],
            'is_home': is_home,
            'goals_scored': home_score if is_home else away_score,
            'goals_conceded': away_score if is_home else home_score,
            'result': result,
            'opponent_name': t['away']['name'] if is_home else t['home']['name']
        }


    def _load_local_matches(self, team_name: str) -> List[Dict]:
        league_file, _ = self._get_team_league_file(team_name)
        all_matches = []

        # Check if local_data_path is a file (older version) or a directory (newer version)
        if not self.local_data_path.exists():
            logger.warning(f"Local football data path {self.local_data_path} not found.")
            return []

        if self.local_data_path.is_file():
            # Handle case where it's a single JSON file
            try:
                with open(self.local_data_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                    if not content: return []
                    data = json.loads(content)
                    matches = data.get('matches', [])
                    for match in matches:
                        if match.get('team1') == team_name or match.get('team2') == team_name:
                            parsed = self._parse_local_match(match, team_name)
                            if parsed: all_matches.append(parsed)
            except Exception as e:
                logger.error(f"Error reading local match file: {e}")
                return []
        else:
            # Handle directory structure
            if not league_file: return []
            for season_dir in self.local_data_path.iterdir():
                if season_dir.is_dir():
                    data_file = season_dir / f"{league_file}.json"
                    if data_file.exists():
                        with open(data_file, 'r', encoding='utf-8') as f:
                            season_data = json.load(f)
                            for match in season_data['matches']:
                                if match['team1'] == team_name or match['team2'] == team_name:
                                    parsed = self._parse_local_match(match, team_name)
                                    if parsed: all_matches.append(parsed)

        all_matches.sort(key=lambda x: x['date'], reverse=True)
        return all_matches

    async def find_all_value_bets(self, league_ids: List[int] = None) -> List[Dict]:
        if not self.rapidapi_key:
            raise ValueError("RapidAPI key not configured.")

        # Limited league list for BASIC API plans to avoid 429
        if not league_ids:
            league_ids = [
                47, 87, 54, 55, 53, # Premier League, LaLiga, Bundesliga, Serie A, Ligue 1
                42, 73, # UCL, UEL
            ]
        
        all_value_bets = []
        
        for league_id in league_ids:
            fixtures = await self._fetch_upcoming_fixtures(league_id)
            for fixture in fixtures:
                fixture_id = fixture.get('fixture', {}).get('id')
                home_team = fixture.get('teams', {}).get('home', {}).get('name')
                away_team = fixture.get('teams', {}).get('away', {}).get('name')

                if not all([fixture_id, home_team, away_team]):
                    continue

                # Fetch odds (assuming Bet365 bookmaker ID 8)
                odds = await self._fetch_odds_for_fixture(fixture_id, bookmaker_id=8)
                if not odds:
                    continue

                try:
                    prediction = await self.predict_match(home_team, away_team, odds)
                    if prediction.get('value_bets'):
                        for bet in prediction['value_bets']:
                            bet['home_team'] = home_team
                            bet['away_team'] = away_team
                            all_value_bets.append(bet)
                except Exception as e:
                    logger.error(f"Error predicting match {home_team} vs {away_team}: {e}")
        
        return all_value_bets

    async def _fetch_upcoming_fixtures(self, league_id: int) -> List[Dict]:
        try:
            # 1. Try Live API (RapidAPI with Football-Data fallback)
            all_fixtures = []
            for i in range(2): # Scan next 2 days
                target_date = (datetime.now() + timedelta(days=i)).strftime("%Y-%m-%d")
                res = await self.football_client.get_matches_by_date(target_date)
                day_matches = res.get('response', [])
                all_fixtures.extend(day_matches)
            
            # 2. Fallback: Pull from Dataset (Supabase) if API returns nothing
            if not all_fixtures and self.supabase:
                logger.info("API fixtures empty. Pulling future matches from Supabase dataset...")
                now_iso = datetime.now().isoformat()
                # Query matches in the future where we have no scores yet
                db_res = self.supabase.table("matches").select("*, home_team:home_team_id(name, logo_url), away_team:away_team_id(name, logo_url)")\
                    .gte("match_date", now_iso)\
                    .is_("home_goals", "null")\
                    .limit(20).execute()
                
                if db_res.data:
                    for m in db_res.data:
                        all_fixtures.append({
                            "fixture": {"id": m['id'], "date": m['match_date']},
                            "teams": {
                                "home": {"name": m['home_team']['name'], "id": m['home_team_id'], "logo": m['home_team']['logo_url']},
                                "away": {"name": m['away_team']['name'], "id": m['away_team_id'], "logo": m['away_team']['logo_url']}
                            },
                            "league": {"name": m.get('league', 'Dataset'), "id": 0}
                        })

            return all_fixtures
            
        except Exception as e:
            logger.error(f"Error fetching fixtures fallback: {e}")
            return []

    async def _fetch_odds_for_fixture(self, fixture_id: int, bookmaker_id: int) -> Dict:
        try:
            res = await self.football_client.get_odds_by_event_id(fixture_id)
            odds_response = res.get('response', [])
            if not odds_response:
                return {}

            # Find the requested bookmaker or default to the first one
            bm_data = next((bm for bm in odds_response[0].get('bookmakers', []) if bm['id'] == bookmaker_id), None)
            if not bm_data and odds_response[0].get('bookmakers'):
                bm_data = odds_response[0]['bookmakers'][0]
            
            if not bm_data: return {}

            odds_data = bm_data.get('bets', [])
            parsed_odds = {}
            for bet_type in odds_data:
                if bet_type['name'] == 'Match Winner':
                    for value in bet_type['values']:
                        if value['value'] == 'Home': parsed_odds['home_win'] = value['odd']
                        elif value['value'] == 'Draw': parsed_odds['draw'] = value['odd']
                        elif value['value'] == 'Away': parsed_odds['away_win'] = value['odd']
                elif bet_type['name'] == 'Goals Over/Under' and '2.5' in [v['value'] for v in bet_type['values']]:
                     for value in bet_type['values']:
                        if value['value'] == 'Over 2.5': parsed_odds['Over 2.5'] = value['odd']
                        elif value['value'] == 'Under 2.5': parsed_odds['Under 2.5'] = value['odd']
                elif bet_type['name'] == 'Both Teams To Score':
                     for value in bet_type['values']:
                        if value['value'] == 'Yes': parsed_odds['BTTS Yes'] = value['odd']
                        elif value['value'] == 'No': parsed_odds['BTTS No'] = value['odd']
            
            return parsed_odds

        except Exception as e:
            logger.error(f"Error fetching odds for fixture {fixture_id}: {e}")
            return {}

    def _get_team_league_file(self, team_name: str) -> Tuple[str, str]:
        # A more comprehensive map could be stored in a JSON or DB
        team_map = {
            'Manchester City': ('en.1', 'Premier League'),
            'Arsenal': ('en.1', 'Premier League'),
            'Liverpool': ('en.1', 'Premier League'),
            'Chelsea': ('en.1', 'Premier League'),
            'Manchester United': ('en.1', 'Premier League'),
            'Tottenham Hotspur': ('en.1', 'Premier League'),
            'Real Madrid': ('es.1', 'La Liga'),
            'Barcelona': ('es.1', 'La Liga'),
            'Atletico Madrid': ('es.1', 'La Liga'),
            'Bayern Munich': ('de.1', 'Bundesliga'),
            'Borussia Dortmund': ('de.1', 'Bundesliga'),
            'Inter Milan': ('it.1', 'Serie A'),
            'AC Milan': ('it.1', 'Serie A'),
            'Juventus': ('it.1', 'Serie A'),
            'Napoli': ('it.1', 'Serie A'),
            'Paris Saint Germain': ('fr.1', 'Ligue 1'),
            'Ajax': ('nl.1', 'Eredivisie'),
            'Benfica': ('pt.1', 'Primeira Liga'),
            'Porto': ('pt.1', 'Primeira Liga'),
        }
        # Clean team name for better matching
        cleaned_name = team_name.replace(' FC', '').replace('AFC ', '').replace(' PSG', 'Paris Saint Germain').strip()
        return team_map.get(cleaned_name, (None, None))

    def _parse_local_match(self, match: Dict, team_name: str) -> Dict:
        if 'score' not in match or 'ft' not in match['score']: return None
        home_team, away_team = match['team1'], match['team2']
        home_score, away_score = match['score']['ft']
        is_home = team_name == home_team
        result = 'draw'
        if home_score != away_score: result = 'win' if (is_home and home_score > away_score) or (not is_home and away_score > home_score) else 'loss'
        return {'date': match['date'], 'is_home': is_home, 'goals_scored': home_score if is_home else away_score, 'goals_conceded': away_score if is_home else home_score, 'result': result, 'opponent_name': away_team if is_home else home_team}

    async def _calculate_probabilities(self, home_team: str, away_team: str) -> Dict:
        home_matches = await self.get_team_matches(home_team)
        away_matches = await self.get_team_matches(away_team)
        
        home_strength = await self.team_strength_agent.assess(home_team, home_matches)
        away_strength = await self.team_strength_agent.assess(away_team, away_matches)

        # --- Tactical Analysis ---
        tactical_analysis = self.tactical_agent.analyze_matchup(home_strength, away_strength)
        mods = tactical_analysis.probability_modifiers

        # --- Base Probability Calculation (Poisson) ---
        lambda_home = home_strength.attack_strength * away_strength.defense_strength
        lambda_away = away_strength.attack_strength * home_strength.defense_strength
        max_goals = 6
        score_matrix = np.outer(
            np.array([self._poisson_pmf(i, lambda_home) for i in range(max_goals + 1)]),
            np.array([self._poisson_pmf(j, lambda_away) for j in range(max_goals + 1)])
        )
        
        # --- Apply Tactical Modifiers and Re-normalize ---
        home_win_base, draw_base, away_win_base = self._get_match_odds_probs(score_matrix)
        draw_base *= mods.get('draw', 1.0)
        norm_factor = (1 - draw_base) / (home_win_base + away_win_base)
        home_win, draw, away_win = home_win_base * norm_factor, draw_base, away_win_base * norm_factor

        # Double Chance
        dc_home_draw = home_win + draw
        dc_away_draw = away_win + draw
        dc_home_away = home_win + away_win

        ou_probs = self._get_over_under_probs(score_matrix, max_goals)
        ou_probs['Over 2.5'] *= mods.get('over_2.5', 1.0)
        ou_probs['Under 2.5'] *= mods.get('under_2.5', 1.0)
        ou_total = ou_probs['Over 2.5'] + ou_probs['Under 2.5']
        ou_probs['Over 2.5'] /= ou_total; ou_probs['Under 2.5'] /= ou_total

        btts_yes_base, btts_no_base = self._get_btts_probs(score_matrix)
        btts_yes_base *= mods.get('btts_yes', 1.0)
        btts_total = btts_yes_base + btts_no_base
        btts_yes, btts_no = btts_yes_base/btts_total, btts_no_base/btts_total

        # Correct Score (Top 5)
        correct_scores = []
        for i in range(4):
            for j in range(4):
                correct_scores.append({"score": f"{i}-{j}", "prob": float(score_matrix[i, j])})
        top_correct_scores = sorted(correct_scores, key=lambda x: x['prob'], reverse=True)[:5]

        final_insights = self._generate_insights(home_strength, away_strength)
        final_insights.insert(0, tactical_analysis.clash_insight)

        return {
            "probabilities": {
                "home_win": home_win, "draw": draw, "away_win": away_win, 
                **ou_probs, 
                "BTTS Yes": btts_yes, "BTTS No": btts_no,
                "DC Home/Draw": dc_home_draw, "DC Away/Draw": dc_away_draw, "DC Home/Away": dc_home_away
            },
            "correct_scores": top_correct_scores,
            "home_team": home_team, "away_team": away_team, "home_xg": lambda_home, "away_xg": lambda_away,
            "key_factors": final_insights
        }

    async def predict_match(self, home_team: str, away_team: str, odds: Dict) -> Dict:
        prediction_data = await self._calculate_probabilities(home_team, away_team)
        value_bets = self._find_value_bets(prediction_data["probabilities"], odds)

        # Get team IDs for H2H visualizer
        home_id, away_id = None, None
        if self.supabase:
            h_res = self.supabase.table("teams").select("id").eq("name", home_team).execute()
            a_res = self.supabase.table("teams").select("id").eq("name", away_team).execute()
            if h_res.data: home_id = h_res.data[0]['id']
            if a_res.data: away_id = a_res.data[0]['id']

        # Save to database
        if self.supabase:
            try:
                # Find best bet to store in predictions table
                best_bet = max(value_bets, key=lambda x: x.ev) if value_bets else None
                
                # Synchronously save data
                prediction_id = self._save_prediction_to_db(prediction_data, best_bet)
                if prediction_id and value_bets:
                    self._save_value_bets_to_db(value_bets, prediction_id, home_team, away_team)

            except Exception as e:
                logger.error(f"Error saving prediction to database: {e}")

        return {
            "home_team": home_team, 
            "away_team": away_team, 
            "home_id": home_id,
            "away_id": away_id,
            "probabilities": prediction_data["probabilities"],
            "home_xg": prediction_data["home_xg"], 
            "away_xg": prediction_data["away_xg"],
            "key_factors": prediction_data["key_factors"], 
            "value_bets": [bet.__dict__ for bet in value_bets],
            "correct_scores": prediction_data.get("correct_scores", [])
        }

    def _save_prediction_to_db(self, prediction_data: Dict, best_bet: ValueBet = None) -> int:
        if not self.supabase: return None

        record = {
            "home_team": prediction_data['home_team'],
            "away_team": prediction_data['away_team'],
            "home_prob": prediction_data['probabilities'].get('home_win'),
            "draw_prob": prediction_data['probabilities'].get('draw'),
            "away_prob": prediction_data['probabilities'].get('away_win'),
            "home_xg": prediction_data['home_xg'],
            "away_xg": prediction_data['away_xg'],
            "model_version": "3.0.0",
        }
        if best_bet:
            record.update({
                "best_bet_market": best_bet.market_name,
                "best_bet_selection": best_bet.selection,
                "best_bet_odds": best_bet.odds,
                "best_bet_ev": best_bet.ev,
                "best_bet_kelly": best_bet.kelly_percentage,
            })

        try:
            # Use '.execute()' to run the query
            response = self.supabase.table("predictions").insert(record).execute()
            if response.data:
                logger.info("Prediction saved to database.")
                return response.data[0]['id']
        except Exception as e:
            logger.error(f"Supabase insert failed for prediction: {e}")
        return None

    def _save_value_bets_to_db(self, value_bets: List[ValueBet], prediction_id: int, home_team: str, away_team: str):
        if not self.supabase: return

        records = []
        for bet in value_bets:
            records.append({
                "prediction_id": prediction_id,
                "home_team": home_team,
                "away_team": away_team,
                "market": bet.market_name,
                "selection": bet.selection,
                "odds": bet.odds,
                "our_probability": bet.our_probability,
                "implied_probability": 1 / bet.odds,
                "ev": bet.ev,
                "kelly_percentage": bet.kelly_percentage,
                "recommended_stake_percentage": float(bet.recommended_stake.strip('%')),
                "tier": bet.tier
            })
        
        try:
            # Use '.execute()' to run the query
            self.supabase.table("value_bets").insert(records).execute()
            logger.info(f"{len(records)} value bets saved to database.")
        except Exception as e:
            logger.error(f"Supabase insert failed for value_bets: {e}")

    def _find_value_bets(self, probabilities: Dict, odds: Dict) -> List[ValueBet]:
        value_bets = []
        market_map = {
            "home_win": ("Match Odds", "Home Win"),
            "draw": ("Match Odds", "Draw"),
            "away_win": ("Match Odds", "Away Win"),
            "Over 2.5": ("Over/Under", "Over 2.5"),
            "Under 2.5": ("Over/Under", "Under 2.5"),
            "BTTS Yes": ("Both Teams to Score", "Yes"),
            "BTTS No": ("Both Teams to Score", "No"),
        }
        for key, (market_name, selection) in market_map.items():
            if (prob := probabilities.get(key)) and (odd := odds.get(key)):
                if (ev := (prob * odd) - 1) > 0.05:
                    kelly = self.kelly_criterion(prob, odd)
                    
                    # Tiering Logic
                    tier = "Neutral"
                    if ev > 0.20: tier = "Hot 🔥"
                    elif ev > 0.10: tier = "Solid"
                    
                    value_bets.append(ValueBet(
                        market_name=market_name, 
                        selection=selection, 
                        odds=odd, 
                        our_probability=round(prob, 3), 
                        ev=round(ev, 3), 
                        kelly_percentage=round(kelly, 3), 
                        recommended_stake=f"{round(kelly * 0.25 * 100, 1)}%",
                        tier=tier
                    ))
        value_bets.sort(key=lambda x: x.ev, reverse=True)
        return value_bets

    async def analyze_custom_bet(self, home_team: str, away_team: str, market: str, selection: str, odds: float) -> Dict:
        # ... (same as before, no changes needed here)
        prediction_data = await self._calculate_probabilities(home_team, away_team)
        prob_key = selection
        if market == "Match Odds": prob_key = "home_win" if selection == "Home Win" else "draw" if selection == "Draw" else "away_win"
        if not (our_prob := prediction_data["probabilities"].get(prob_key)): return {"error": "Market or selection not found or not supported."}
        ev = (our_prob * odds) - 1; kelly = self.kelly_criterion(our_prob, odds)
        return {"your_bet": f"{market} - {selection} @ {odds}", "our_probability": round(our_prob, 3), "expected_value": round(ev, 3), "is_value_bet": ev > 0.05, "recommended_kelly_stake": f"{round(kelly * 100, 1)}% (Full Kelly)", "analysis": "This looks like a good value bet." if ev > 0.05 else "This does not appear to be a value bet."}

    def _generate_insights(self, h, a):
        # ... (Simplified now that tactical insight is separate)
        insights = []
        elo_diff = (h.overall_rating + h.home_advantage) - a.overall_rating
        if h.form_rating > a.form_rating + 2: insights.append(f"{h.name} is in significantly better form.")
        if elo_diff > 120: insights.append(f"{h.name} has a strong Elo advantage.")
        return insights
    
    def kelly_criterion(self, p, o): return max(0, (p * (o - 1) - (1 - p)) / (o - 1)) if o > 1 else 0
    def _poisson_pmf(self, k, lam): return (lam**k * math.exp(-lam)) / math.factorial(k)
    def _get_match_odds_probs(self, sm): t = np.sum(sm); return np.sum(np.tril(sm, -1))/t, np.sum(np.diag(sm))/t, np.sum(np.triu(sm, 1))/t
    def _get_btts_probs(self, sm): yes = np.sum(sm[1:, 1:]); return yes, 1 - yes
    def _get_over_under_probs(self, sm, mg):
        ou = {}
        for line in [0.5, 1.5, 2.5, 3.5]:
            total = sum(sm[i, j] for i in range(mg + 1) for j in range(mg + 1) if i + j > line)
            ou[f'Over {line}'] = total; ou[f'Under {line}'] = 1 - total
        return ou
