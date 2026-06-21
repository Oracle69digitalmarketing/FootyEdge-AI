import os
from dotenv import load_dotenv
from supabase import create_client, Client

# Load environment variables
load_dotenv()

# Initialize Supabase Client
SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_SERVICE_KEY") or os.environ.get("SUPABASE_KEY")
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

def cleanup_database():
    print("🧹 Cleaning up dummy seeded data...")
    
    try:
        # Delete dummy predictions
        supabase.table("predictions").delete().in_("home_team", ["Team A", "Team C", "Team E"]).execute()
        
        # Delete dummy matches
        supabase.table("matches").delete().in_("home_team_id", ["1", "3", "5"]).execute()
        
        # Delete dummy teams
        supabase.table("teams").delete().in_("id", ["1", "2", "3", "4", "5", "6"]).execute()
        
        print("✅ Cleanup completed successfully!")
    except Exception as e:
        print(f"❌ Error during cleanup: {e}")

if __name__ == "__main__":
    cleanup_database()
