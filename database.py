import supabase
from config import SUPABASE_URL, SUPABASE_SERVICE_KEY

if not SUPABASE_URL or not SUPABASE_SERVICE_KEY:
    print("Warning: Missing SUPABASE_URL or SUPABASE_SERVICE_KEY in environment/config")

supabase_client = supabase.create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)
