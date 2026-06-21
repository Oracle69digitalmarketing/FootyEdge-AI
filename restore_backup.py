import os
import json
import argparse
import logging
from supabase import create_client, Client

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("restore_backup")

# Initialize client from environment parameters
SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_SERVICE_KEY") or os.environ.get("SUPABASE_KEY")
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

def list_available_backups():
    """Queries the secure backup storage bucket and displays all available snapshots."""
    try:
        files = supabase.storage.from_("database-backups").list()
        if not files:
            logger.info("📁 No snapshot files found in the 'database-backups' bucket.")
            return []

        logger.info("\n===========================================")
        logger.info("       AVAILABLE DATABASE SNAPSHOTS        ")
        logger.info("===========================================")
        for idx, file in enumerate(files):
            # Exclude folder placeholders if any exist
            if file['name'] != '.emptyFolderPlaceholder':
                size_kb = file['metadata'].get('size', 0) / 1024
                logger.info(f"[{idx}] {file['name']} ({size_kb:.2f} KB) - Created: {file['created_at']}")
        logger.info("===========================================\n")
        return files
    except Exception as e:
        logger.error(f"❌ Failed to fetch bucket storage tree: {str(e)}")
        return []

def restore_database_snapshot(filename: str):
    """Downloads a historical backup and overwrites production tables while handling foreign keys."""
    logger.info(f"🔄 Downloading snapshot archive file from storage: {filename}")

    try:
        # 1. Download bytes array directly from Supabase Storage
        file_bytes = supabase.storage.from_("database-backups").download(filename)
        backup_data = json.loads(file_bytes.decode('utf-8'))

        tables = backup_data.get("tables", {})

        logger.warning("⚠️ CRITICAL OPERATION: Wiping active production tables...")

        # 2. Delete tables in strict REVERSE hierarchical order
        supabase.table("value_bets").delete().neq("id", "0").execute()
        supabase.table("predictions").delete().neq("id", "0").execute()
        supabase.table("matches").delete().neq("id", 0).execute()
        supabase.table("teams").delete().neq("id", "0").execute()

        logger.info("🧹 Tables cleared. Injecting historical dataset records...")

        # 3. Re-populate database in strict TOP-DOWN hierarchical order

        # Step A: Teams
        if tables.get("teams"):
            logger.info(f"🧬 Restoring {len(tables['teams'])} teams...")
            supabase.table("teams").insert(tables["teams"]).execute()

        # Step B: Matches
        if tables.get("matches"):
            logger.info(f"🧬 Restoring {len(tables['matches'])} matches...")
            supabase.table("matches").insert(tables["matches"]).execute()

        # Step C: Predictions
        if tables.get("predictions"):
            logger.info(f"🧬 Restoring {len(tables['predictions'])} predictions...")
            supabase.table("predictions").insert(tables["predictions"]).execute()

        # Step D: Value Bets
        if tables.get("value_bets"):
            logger.info(f"🧬 Restoring {len(tables['value_bets'])} value bets...")
            supabase.table("value_bets").insert(tables["value_bets"]).execute()

        logger.info(f"🎉 SYSTEM SUCCESS: Database rolled back to state archive date: {backup_data['metadata']['snapshot_time_utc']}")
        return True

    except Exception as e:
        logger.error(f"❌ Restoration routine aborted due to critical error: {str(e)}")
        logger.error("🚨 DATABASE STATE MAY BE INCOMPLETE. Check Supabase Dashboard immediately.")
        return False

if __name__ == "__main__":
    # Setup CLI terminal arguments parsing
    parser = argparse.ArgumentParser(description="FootyEdge AI Database Rollback & Restoration Tool")
    parser.add_argument("--file", type=str, help="The exact name of the backup JSON file inside the storage bucket")
    parser.add_argument("--list", action="store_true", help="List all available backups inside your secure bucket")
    args = parser.parse_args()

    if args.list or not args.file:
        list_available_backups()
        logger.info("💡 Run the script again with: python restore_backup.py --file [FILENAME]")
    else:
        confirm = input(f"❗ Are you absolutely sure you want to overwrite all live tables with '{args.file}'? (yes/no): ")
        if confirm.lower() == 'yes':
            restore_database_snapshot(args.file)
        else:
            logger.info("❌ Operation cancelled by user.")
