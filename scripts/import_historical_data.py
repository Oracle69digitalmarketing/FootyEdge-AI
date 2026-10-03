import os
import pandas as pd
import numpy as np
from supabase import create_client, Client
import logging
from datetime import datetime
import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from team_identity import (
    UnknownTeamIdentityError,
    resolve_canonical_id_db,
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Actual historical dataset represented by this importer
# (data/club-data/matches.csv). The CSV carries team display names only —
# no stable external team identifier — so the source is recorded as the
# dataset name and external_team_id always remains None. Never derive a
# provider ID from a team name.
HISTORICAL_SOURCE = "club-data"

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Supabase configuration (service key is canonical; never print it)
url = os.environ.get("SUPABASE_URL")
key = os.environ.get("SUPABASE_SERVICE_KEY") or os.environ.get("SUPABASE_KEY")

if not url or not key:
    raise ValueError("SUPABASE_URL and SUPABASE_SERVICE_KEY must be set.")

supabase: Client = create_client(url, key)


def get_team_id(team_name: str, supabase, source=HISTORICAL_SOURCE) -> int:
    """Resolve a historical team name to its canonical SHA-256/12-hex ID.

    Explicit controlled registration boundary (allow_create=True): unseen
    historical teams are registered in the canonical SHA namespace with
    their canonical spelling. No provider mapping is stored (the dataset
    provides no stable external team ID) and no alias is fabricated.
    Never MD5, never legacy.
    """
    _canonical_name, canonical_id = resolve_canonical_id_db(
        str(team_name), source=source, supabase=supabase, allow_create=True
    )
    return canonical_id


def resolve_historical_teams(unique_names, supabase, source=HISTORICAL_SOURCE):
    """Resolve every distinct CSV team spelling via the DB-backed resolver.

    Returns (team_cache, failures) where team_cache maps the raw CSV
    spelling to (canonical_name, canonical_id) and failures lists
    (raw_name, error) for identities that must not silently pass
    (conflicts, legacy hits). allow_create=True because this importer is
    the explicit controlled registration boundary for unseen historical
    teams; every created team uses the canonical SHA namespace.
    """
    team_cache = {}
    failures = []
    for raw in unique_names:
        try:
            team_cache[str(raw)] = resolve_canonical_id_db(
                str(raw), source=source, supabase=supabase, allow_create=True
            )
        except Exception as exc:
            logger.error(f"Historical team identity failed for {raw!r}: {exc}")
            failures.append((str(raw), exc))
    return team_cache, failures


def lookup_historical_team_id(raw_name, team_cache):
    """Return the canonical team ID for a CSV spelling or raise with context."""
    try:
        _canonical_name, team_id = team_cache[str(raw_name)]
    except KeyError:
        raise UnknownTeamIdentityError(
            f"Unresolved historical team identity for CSV team {raw_name!r}."
        )
    return team_id

def process_and_import_data(csv_path: str, start_year: int = 2010):
    logger.info(f"Processing matches from {csv_path} starting from {start_year}...")
    
    df = pd.read_csv(csv_path, low_memory=False)
    df['MatchDate'] = pd.to_datetime(df['MatchDate'])
    df = df[df['MatchDate'].dt.year >= start_year]
    
    # Replace NaN with None for JSON compliance
    df = df.replace({np.nan: None})
    
    logger.info(f"Filtered to {len(df)} matches.")

    # 1. Resolve every distinct CSV spelling through the canonical resolver.
    unique_team_names = pd.concat([df['HomeTeam'], df['AwayTeam']]).unique()

    logger.info(f"Resolving {len(unique_team_names)} teams...")
    team_cache, identity_failures = resolve_historical_teams(
        unique_team_names, supabase, source=HISTORICAL_SOURCE
    )
    if identity_failures:
        logger.error(
            f"{len(identity_failures)} team identities failed resolution and "
            "their fixtures will be skipped with per-row context."
        )

    logger.info(f"Upserting {len(team_cache)} resolved teams...")
    resolved = list(team_cache.values())
    for i in range(0, len(resolved), 100):
        batch = resolved[i:i+100]
        batch_data = [
            {"id": team_id, "name": canonical_name, "league_name": "Various"}
            for canonical_name, team_id in batch
        ]
        try:
            supabase.table("teams").upsert(batch_data, on_conflict="name").execute()
        except Exception as e:
            logger.error(f"Error upserting teams batch: {e}")

    # 2. Process and Import Matches
    matches_to_import = []
    for idx, row in df.iterrows():
        try:
            h_id = lookup_historical_team_id(row['HomeTeam'], team_cache)
            a_id = lookup_historical_team_id(row['AwayTeam'], team_cache)
        except UnknownTeamIdentityError as e:
            logger.error(
                f"Skipping CSV row {idx}: {e} "
                f"(HomeTeam={row['HomeTeam']!r}, AwayTeam={row['AwayTeam']!r})."
            )
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
