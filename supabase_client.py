from typing import Optional
import os
from supabase import create_client, ClientOptions
from dotenv import load_dotenv

load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

if not SUPABASE_URL or not SUPABASE_KEY:
    raise RuntimeError("SUPABASE_URL and SUPABASE_KEY must be set in env")

_supabase_client = create_client(
    SUPABASE_URL,
    SUPABASE_KEY,
    options=ClientOptions(schema="supabase_functions")
)

def get_supabase_client():
    return _supabase_client

def get_db():
    return _supabase_client.from_

def get_auth():
    return _supabase_client.auth

def get_storage():
    return _supabase_client.storage

def get_realtime():
    return _supabase_client.realtime
