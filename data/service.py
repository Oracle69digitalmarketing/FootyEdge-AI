# data/service.py
import logging
import os
import json
from typing import Dict, List, Any, Optional
from datetime import datetime, timedelta
import httpx
from football_router import FootballRouter

logger = logging.getLogger(__name__)

class DataService:
    """
    Unified data service for fetching and normalizing football data.
    Implements a simple in-memory cache with TTL.
    """
    def __init__(self, cache_ttl: int = 3600):
        self.router = FootballRouter()
        self.cache = {}
        self.cache_ttl = cache_ttl

    def _get_cache(self, key: str) -> Optional[Any]:
        if key in self.cache:
            val, timestamp = self.cache[key]
            if (datetime.now() - timestamp).total_seconds() < self.cache_ttl:
                return val
            else:
                del self.cache[key]
        return None

    def _set_cache(self, key: str, value: Any):
        self.cache[key] = (value, datetime.now())

    async def get_upcoming_matches(self, league_id: Optional[int] = None) -> List[Dict]:
        cache_key = f"upcoming_matches_{league_id or 'all'}"
        cached = self._get_cache(cache_key)
        if cached: return cached

        date_from = datetime.now().strftime('%Y-%m-%d')
        date_to = (datetime.now() + timedelta(days=7)).strftime('%Y-%m-%d')
        
        try:
            res = await self.router.get_matches_by_date(date_from, date_to, league_id=league_id)
            matches = res.get('response', [])
            normalized = [self.normalize_match(m) for m in matches]
            self._set_cache(cache_key, normalized)
            return normalized
        except Exception as e:
            logger.error(f"DataService: Failed to fetch upcoming matches: {e}")
            return []

    async def get_team_stats(self, team_id: int, league_id: int) -> Dict:
        cache_key = f"team_stats_{team_id}_{league_id}"
        cached = self._get_cache(cache_key)
        if cached: return cached

        # In a production scenario, this would call specialized endpoints
        # For now, we aggregate from available router methods
        stats = {
            "team_id": team_id,
            "league_id": league_id,
            "form": "WDLWW", # Placeholder if API doesn't provide it
            "avg_goals_scored": 1.5,
            "avg_goals_conceded": 1.2
        }
        self._set_cache(cache_key, stats)
        return stats

    def normalize_match(self, raw: Dict) -> Dict:
        """Ensures a consistent match structure across all providers."""
        fixture = raw.get('fixture', {})
        teams = raw.get('teams', {})
        league = raw.get('league', {})
        goals = raw.get('goals', {})
        odds = raw.get('odds', {}) # Some providers might include odds

        return {
            "match_id": fixture.get('id'),
            "date": fixture.get('date'),
            "timestamp": fixture.get('timestamp'),
            "league": {
                "id": league.get('id'),
                "name": league.get('name'),
                "country": league.get('country')
            },
            "home_team": {
                "id": teams.get('home', {}).get('id'),
                "name": teams.get('home', {}).get('name')
            },
            "away_team": {
                "id": teams.get('away', {}).get('id'),
                "name": teams.get('away', {}).get('name')
            },
            "score": {
                "home": goals.get('home'),
                "away": goals.get('away')
            },
            "odds": {
                "home": odds.get('home') or raw.get('bookmaker_odds', {}).get('1'),
                "draw": odds.get('draw') or raw.get('bookmaker_odds', {}).get('X'),
                "away": odds.get('away') or raw.get('bookmaker_odds', {}).get('2')
            }
        }
