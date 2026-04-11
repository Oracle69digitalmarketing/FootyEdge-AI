import os
import pandas as pd
import numpy as np
from supabase import create_client, Client
import logging
from datetime import datetime
import hashlib

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Supabase configuration
url = os.environ.get("SUPABASE_URL")
key = os.environ.get("SUPABASE_KEY")

if not url or not key:
    raise ValueError("SUPABASE_URL and SUPABASE_KEY must be set.")

supabase: Client = create_client(url, key)

def get_team_id(team_name: str) -> int:
    """Generate a consistent numeric ID from team name."""
    return int(hashlib.md5(team_name.encode()).hexdigest(), 16) % (10**10)

def process_and_import_data(csv_path: str, start_year: int = 2010):
    logger.info(f"Processing matches from {csv_path} starting from {start_year}...")
    
    df = pd.read_csv(csv_path, low_memory=False)
    df['MatchDate'] = pd.to_datetime(df['MatchDate'])
    df = df[df['MatchDate'].dt.year >= start_year]
    
    # Replace NaN with None for JSON compliance
    df = df.replace({np.nan: None})
    
    logger.info(f"Filtered to {len(df)} matches.")

    # 1. Map Teams (Name -> UUID from DB)
    unique_team_names = pd.concat([df['HomeTeam'], df['AwayTeam']]).unique()
    
    logger.info(f"Upserting {len(unique_team_names)} teams...")
    team_name_to_id = {}
    
    for i in range(0, len(unique_team_names), 100):
        batch_names = unique_team_names[i:i+100]
        batch_data = [{"name": name, "league": "Various"} for name in batch_names]
        try:
            res = supabase.table("teams").upsert(batch_data, on_conflict="name").execute()
            for team in res.data:
                team_name_to_id[team['name']] = team['id']
        except Exception as e:
            logger.error(f"Error upserting teams batch: {e}")

    # Ensure we have all mappings
    if len(team_name_to_id) < len(unique_team_names):
        res = supabase.table("teams").select("id, name").execute()
        for team in res.data:
            team_name_to_id[team['name']] = team['id']

    # 2. Process and Import Matches
    matches_to_import = []
    for _, row in df.iterrows():
        h_id = team_name_to_id.get(row['HomeTeam'])
        a_id = team_name_to_id.get(row['AwayTeam'])
        
        if not h_id or not a_id:
            continue

        # Convert potentially float values to int or None
        def clean_val(val, target_type=int):
            if val is None: return None
            try: return target_type(val)
            except: return None

        matches_to_import.append({
            "home_team_id": h_id,
            "away_team_id": a_id,
            "match_date": row['MatchDate'].isoformat(),
            "league": row['Division'],
            "home_goals": clean_val(row['FTHome']),
            "away_goals": clean_val(row['FTAway']),
            "home_xg": float(row['HomeElo']) / 1000.0 if row['HomeElo'] is not None else None,
            "away_xg": float(row['AwayElo']) / 1000.0 if row['AwayElo'] is not None else None,
            "home_shots": clean_val(row['HomeShots']),
            "away_shots": clean_val(row['AwayShots']),
        })

    logger.info(f"Inserting {len(matches_to_import)} matches...")
    # Use smaller batches for more reliability
    batch_size = 200
    for i in range(0, len(matches_to_import), batch_size):
        try:
            supabase.table("matches").insert(matches_to_import[i:i+batch_size]).execute()
            if i % 2000 == 0:
                logger.info(f"Imported {i} matches...")
        except Exception as e:
            logger.error(f"Error at match index {i}: {e}")
            continue

if __name__ == "__main__":
    csv_file = "data/club-data/matches.csv"
    if os.path.exists(csv_file):
        process_and_import_data(csv_file)
    else:
        logger.error(f"File not found: {csv_file}")
