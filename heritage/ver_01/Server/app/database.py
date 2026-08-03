"""
app/database.py
Supabase 클라이언트 연결 및 데이터 핸들러 (Mock Fallback 지원)
"""

try:
    from supabase import create_client, Client
except Exception:
    create_client = None
    Client = None

from app.config import settings

# Supabase Client
supabase_client = None
try:
    if create_client and settings.SUPABASE_URL and settings.SUPABASE_KEY and "your-supabase" not in settings.SUPABASE_URL:
        supabase_client = create_client(settings.SUPABASE_URL, settings.SUPABASE_KEY)
except Exception as e:
    print(f"Supabase connection warning: {e}")

def get_supabase() -> Client:
    try:
        if create_client and settings.SUPABASE_URL and settings.SUPABASE_KEY and "your-supabase" not in settings.SUPABASE_URL:
            return create_client(settings.SUPABASE_URL, settings.SUPABASE_KEY)
    except Exception as e:
        print(f"Supabase client connection error: {e}")
    return None
