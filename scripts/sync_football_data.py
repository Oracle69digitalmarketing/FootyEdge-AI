import os
import pandas as pd
import numpy as np
from supabase import create_client, Client
import logging
from datetime import datetime
import io
import requests

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Supabase configuration
url = os.environ.get("SUPABASE_URL")
key = os.environ.get("SUPABASE_KEY")

if not url or not key:
    logger.error("SUPABASE_URL and SUPABASE_KEY must be set in environment variables.")
    exit(1)

supabase: Client = create_client(url, key)

# Map Football-Data.co.uk Division codes to proper names
LEAGUE_MAP = {
    'E0': 'Premier League',
    'E1': 'Championship',
    'SP1': 'La Liga',
    'D1': 'Bundesliga',
    'I1': 'Serie A',
    'F1': 'Ligue 1'
}

# Source URLs for 2024/2025 season
SOURCES = [
    "https://www.football-data.co.uk/mmz4281/2425/E0.csv",   # Premier League
    "https://www.football-data.co.uk/mmz4281/2425/SP1.csv",  # La Liga
    "https://www.football-data.co.uk/mmz4281/2425/D1.csv",   # Bundesliga
    "https://www.football-data.co.uk/mmz4281/2425/I1.csv",   # Serie A
    "https://www.football-data.co.uk/mmz4281/2425/F1.csv",   # Ligue 1
]

def fetch_team_mapping():
    """Build a map of Name -> ID from the database."""
    logger.info("Fetching existing teams from Supabase...")
    res = supabase.table("teams").select("id, name").execute()
    return {team['name']: team['id'] for team in res.data}

def clean_val(val, target_type=int):
    """Safely convert values."""
    if pd.isna(val) or val == '': return None
    try: return target_type(val)
    except: return None

def sync_season():
    team_map = fetch_team_mapping()
    all_new_matches = []

    for source_url in SOURCES:
        league_code = source_url.split('/')[-1].replace('.csv', '')
        league_name = LEAGUE_MAP.get(league_code, 'Unknown')
        
        logger.info(f"Syncing {league_name} from {source_url}...")
        
        try:
            response = requests.get(source_url)
            response.raise_for_status()
            df = pd.read_csv(io.StringIO(response.text))
            
            # Football-Data.co.uk often has empty rows at the bottom
            df = df.dropna(subset=['Date', 'HomeTeam', 'AwayTeam'])
            
            logger.info(f"Found {len(df)} matches in {league_name}.")

            for _, row in df.iterrows():
                home_team = row['HomeTeam']
                away_team = row['AwayTeam']
                
                # Check for ID in our map
                h_id = team_map.get(home_team)
                a_id = team_map.get(away_team)
                
                if not h_id or not a_id:
                    # Logic to handle missing teams (maybe log them for manual mapping)
                    # logger.warning(f"Skipping match: Team mapping missing for {home_team} or {away_team}")
                    continue

                # Parse date (format is often DD/MM/YYYY or DD/MM/YY)
                try:
                    match_date = pd.to_datetime(row['Date'], dayfirst=True).isoformat()
                except:
                    continue

                all_new_matches.append({
                    "home_team_id": h_id,
                    "away_team_id": a_id,
                    "match_date": match_date,
                    "league": league_name,
                    "season": "2024/2025",
                    "home_goals": clean_val(row.get('FTHG')),
                    "away_goals": clean_val(row.get('FTAG')),
                    "home_shots": clean_val(row.get('HS')),
                    "away_shots": clean_val(row.get('AS')),
                    "home_shots_on_target": clean_val(row.get('HST')),
                    "away_shots_on_target": clean_val(row.get('AST')),
                    "home_corners": clean_val(row.get('HC')),
                    "away_corners": clean_val(row.get('AC')),
                    "home_yellow_cards": clean_val(row.get('HY')),
                    "away_yellow_cards": clean_val(row.get('AY')),
                    "home_red_cards": clean_val(row.get('HR')),
                    "away_red_cards": clean_val(row.get('AR'))
                })

        except Exception as e:
            logger.error(f"Failed to fetch or process {source_url}: {e}")

    if not all_new_matches:
        logger.info("No new matches to import.")
        return

    logger.info(f"Upserting {len(all_new_matches)} matches to Supabase...")
    
    # We use a unique constraint check (home_team_id, away_team_id, match_date) if possible,
    # or just insert and rely on DB to avoid duplicates if we had a unique index.
    # For now, let's insert in batches.
    batch_size = 100
    success_count = 0
    for i in range(0, len(all_new_matches), batch_size):
        batch = all_new_matches[i:i+batch_size]
        try:
            # Note: To avoid duplicates, you might want to add a UNIQUE constraint on Supabase 
            # (home_team_id, away_team_id, match_date)
            supabase.table("matches").insert(batch).execute()
            success_count += len(batch)
        except Exception as e:
            logger.error(f"Batch insert error: {e}")

    logger.info(f"Successfully synced {success_count} matches.")

if __name__ == "__main__":
    sync_season()
