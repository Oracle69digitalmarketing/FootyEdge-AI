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

# More tests could be added for get_matches_by_date, failover logic etc.
# but this verifies basic structural integrity of the new components.
