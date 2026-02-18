from typing import Optional
import os
from supabase import create_client
from dotenv import load_dotenv

load_dotenv()  # loads .env into environment for local dev

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")  # use anon key in client-side, service role for server tasks

if not SUPABASE_URL or not SUPABASE_KEY:
    raise RuntimeError("SUPABASE_URL and SUPABASE_KEY must be set in env")

# create a single shared client for your app
_supabase_client = create_client(SUPABASE_URL, SUPABASE_KEY)

def get_supabase_client():
    """
    Return the shared Supabase client. Import this function from other modules.
    """
    return _supabase_client

# Convenience accessors
def get_db():
    return _supabase_client.from_

def get_auth():
    return _supabase_client.auth

def get_storage():
    return _supabase_client.storage

def get_realtime():
    return _supabase_client.realtime
