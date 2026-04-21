import os
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")
SUPABASE_STORAGE_BASE_URL = os.getenv("SUPABASE_STORAGE_BASE_URL")
SUPABASE_MENU_BUCKET = os.getenv("SUPABASE_MENU_BUCKET")
SUPABASE_ENVIRONMENTS_BUCKET = os.getenv("SUPABASE_ENVIRONMENTS_BUCKET")


if not DATABASE_URL:
    raise ValueError("DATABASE_URL is not set")

if not SUPABASE_STORAGE_BASE_URL:
    raise ValueError("SUPABASE_STORAGE_BASE_URL is not set")

if not SUPABASE_MENU_BUCKET:
    raise ValueError("SUPABASE_MENU_BUCKET is not set")

if not SUPABASE_ENVIRONMENTS_BUCKET:
    raise ValueError("SUPABASE_ENVIRONMENTS_BUCKET is not set")