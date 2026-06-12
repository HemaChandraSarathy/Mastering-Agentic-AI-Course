"""Verify Supabase URL + secret key connect. (Tables may not exist yet — that's fine.)

A 'relation does not exist' error means auth + connectivity WORK and the migration just
hasn't run. An auth/JWT error means the key/URL is wrong.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
sys.stdout.reconfigure(encoding="utf-8")

from portcoiq_rag.config import settings
from portcoiq_rag.clients import supabase_client

print(f"url = {settings.supabase_url}")
print(f"key set = {bool(settings.supabase_service_key)} (len {len(settings.supabase_service_key)})")

sb = supabase_client()
try:
    sb.table("rag_chunks").select("id").limit(1).execute()
    print("CONNECTED — rag_chunks already exists.")
except Exception as e:
    msg = str(e)
    if "does not exist" in msg or "relation" in msg or "PGRST205" in msg or "Could not find the table" in msg:
        print("CONNECTED — auth OK; rag_chunks not created yet (run the migration). Good to proceed.")
    else:
        print("CONNECTION PROBLEM:", type(e).__name__, msg[:300])
