import os
import json
import logging
from datetime import datetime, timezone
from supabase import create_client, Client

logger = logging.getLogger("backup_manager")

# Initialize clients using existing environment parameters
SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_SERVICE_KEY") or os.environ.get("SUPABASE_KEY")
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

def run_database_backup():
    """
    Automated free-tier database snapshot manager.
    Aggregates table data rows and archives them directly into Supabase Storage.
    """
    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d_%H%M%S")
    filename = f"footyedge_backup_{timestamp}.json"
    logger.info(f"💾 Initiating secure table archive serialization for: {filename}")

    try:
        # 1. Fetch deep copies of your production tables
        teams = supabase.table("teams").select("*").execute().data
        matches = supabase.table("matches").select("*").execute().data
        predictions = supabase.table("predictions").select("*").execute().data
        value_bets = supabase.table("value_bets").select("*").execute().data

        # 2. Package database snapshot into a unified structure
        backup_payload = {
            "metadata": {
                "snapshot_time_utc": datetime.now(timezone.utc).isoformat(),
                "engine_version": "v2.0-free-backup"
            },
            "tables": {
                "teams": teams,
                "matches": matches,
                "predictions": predictions,
                "value_bets": value_bets
            }
        }

        # Convert data object to bytes array stream
        json_data = json.dumps(backup_payload, indent=2).encode('utf-8')

        # 3. Securely upload the snapshot to your private backup bucket
        response = supabase.storage.from_("database-backups").upload(
            path=filename,
            file=json_data,
            file_options={"content-type": "application/json"}
        )

        logger.info(f"✅ Database backup uploaded successfully. Path: {response}")
        return True

    except Exception as e:
        logger.error(f"❌ Automated database backup routine failed: {str(e)}")
        return False

if __name__ == "__main__":
    run_database_backup()
