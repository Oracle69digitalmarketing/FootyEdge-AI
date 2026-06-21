import asyncio
import os
import sys
from pathlib import Path

# Add the project root to sys.path to import football_api_client
sys.path.append(str(Path(__file__).parent.parent))

from football_api_client import FootballAPIClient

async def test_client():
    # Ensure environment variables are set or warn
    if not os.environ.get('FOOTBALL_DATA_API_KEY') and not os.environ.get('SPORTRADAR_API_KEY'):
        print("Warning: Neither FOOTBALL_DATA_API_KEY nor SPORTRADAR_API_KEY are set.")

    client = FootballAPIClient()
    print("Testing Football API Client (Aggregator)...")
    providers = [p.__class__.__name__ for p in client.providers]
    print(f"Active Providers: {', '.join(providers) if providers else 'None'}")
    
    try:
        res = await client.list_leagues()
        if res and res.get('response'):
            print(f"Success! Found {len(res['response'])} leagues.")
            # Print first 5 leagues for verification
            for l in res['response'][:5]:
                print(f" - {l.get('league', {}).get('name')} (ID: {l.get('league', {}).get('id')})")
        else:
            print("Failed to fetch leagues or no leagues found.")
            print(f"Response: {res}")
    except Exception as e:
        print(f"Error during test: {e}")

if __name__ == "__main__":
    asyncio.run(test_client())
