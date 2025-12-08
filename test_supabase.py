import os
from dotenv import load_dotenv
from supabase import create_client

load_dotenv()

SUPABASE_URL = os.getenv('https://vrtkjoffsbgfzpkelyxh.supabase.co')
SUPABASE_KEY = os.getenv('eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InZydGtqb2Zmc2JnZnpwa2VseXhoIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NjUxNzE5NDksImV4cCI6MjA4MDc0Nzk0OX0.5qFthbgIm4XEZC_c9yqWXgsvbd7PtA9RmYf2582v8dg')

print("Testing Supabase connection...")
print(f"URL: {SUPABASE_URL}")
print(f"Key: {SUPABASE_KEY[:20]}...")  # Show first 20 chars

try:
    supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
    
    # Test connection by fetching users
    response = supabase.table('users').select('*').limit(1).execute()
    
    print("✅ Connection successful!")
    print(f"Found {len(response.data)} users")
    
except Exception as e:
    print(f"❌ Connection failed: {e}")