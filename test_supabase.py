from supabase import create_client
import os
from dotenv import load_dotenv

load_dotenv()

url = os.environ.get("SUPABASE_URL")
key = os.environ.get("SUPABASE_ANON_KEY")

print(f"URL: {url}")
print(f"Key: {key[:10]}..." if key else "Key: None")

try:
    s = create_client(url, key)
    print("Client created successfully")
    # Try a simple query
    res = s.table("teams").select("count", count="exact").limit(1).execute()
    print(f"Query result: {res}")
except Exception as e:
    print(f"Connection failed: {e}")
