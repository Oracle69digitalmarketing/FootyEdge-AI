import pytest
import asyncio
from football_api_client import FootballAPIClient, TheStatsAPIProvider

@pytest.mark.asyncio
async def test_football_router_initialization():
    client = FootballAPIClient()
    # We now have keys in the environment for testing
    assert len(client.providers) > 0

@pytest.mark.asyncio
async def test_stats_provider_initialization():
    provider = TheStatsAPIProvider("fake_key")
    assert provider.api_key == "fake_key"
    assert provider.base_url == "https://thestatsapi.com"

@pytest.mark.asyncio
async def test_predictor_flattened_response():
    from unittest.mock import MagicMock, AsyncMock
    from predictor import FootyEdgePredictor
    
    predictor = FootyEdgePredictor()
    predictor.get_team_matches = AsyncMock(return_value=[])
    predictor.team_strength_agent.assess = AsyncMock(return_value=MagicMock(attack_strength=1.5, defense_strength=1.0))
    
    home_team = "Team A"
    away_team = "Team B"
    odds = {"home_win": 2.0, "draw": 3.0, "away_win": 4.0}
    
    res = await predictor.predict_match(home_team, away_team, odds)
    
    assert "home_prob" in res
    assert "draw_prob" in res
    assert "away_prob" in res
    assert "home_xg" in res
    assert "away_xg" in res
    assert "confidence" in res
    assert "created_at" in res
    assert isinstance(res["home_prob"], float)

# More tests could be added for get_matches_by_date, failover logic etc.
# but this verifies basic structural integrity of the new components.
