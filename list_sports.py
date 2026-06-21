import asyncio
import os
from football_api_client import FootballAPIClient
from football_api_client import OddsAPIProvider

async def main():
    api_key = os.environ.get('ODDS_API_KEY')
    if not api_key:
        print("ODDS_API_KEY not found.")
        return

    provider = OddsAPIProvider(api_key)
    sports = await provider.list_sports()
    
    # Filter for soccer to make it readable
    soccer_sports = [s for s in sports if s.get('group') == 'Soccer']
    
    for s in soccer_sports:
        print(f"Key: {s.get('key')} | Title: {s.get('title')}")

if __name__ == "__main__":
    asyncio.run(main())
