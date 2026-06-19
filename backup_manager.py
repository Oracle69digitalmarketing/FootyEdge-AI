import os
import json
from datetime import datetime
from supabase import create_client, Client

# Initialize Supabase
SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY")
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

def run_database_backup():
    print("💾 Initiating database backup...")
    tables = ["predictions", "matches", "teams"]
    backup_data = {}
    
    try:
        for table in tables:
            response = supabase.table(table).select("*").execute()
            backup_data[table] = response.data
        
        # Convert to JSON
        filename = f"backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        backup_json = json.dumps(backup_data)
        
        # Upload to Supabase Storage
        supabase.storage.from_("database-backups").upload(
            path=filename,
            file=backup_json.encode('utf-8'),
            file_options={"content-type": "application/json"}
        )
        print(f"✅ Backup successful: {filename}")
    except Exception as e:
        print(f"❌ Backup failed: {e}")
