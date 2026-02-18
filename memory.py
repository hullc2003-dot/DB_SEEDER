# memory.py - Corrected for strict ClientOptions requirements

import os
import logging
import asyncio
from typing import List, Dict, Any, Optional
from supabase import create_client, Client
from supabase.lib.client_options import ClientOptions # Import explicitly
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger("Memory")

# — SUPABASE SINGLETON —

_client: Optional[Client] = None

def get_supabase_client() -> Client:
    """
    Get or create Supabase client singleton.
    Fixes the 'dict' has no attribute 'headers' and 
    'ClientOptions' has no attribute 'storage' errors.
    """
    global _client

    if _client is None:
        url = os.getenv("SUPABASE_URL")
        key = os.getenv("SUPABASE_KEY") or os.getenv("SUPABASE_SERVICE_ROLE_KEY")

        if not url or not key:
            raise RuntimeError("Missing Supabase credentials.")

        try:
            # FIX: Initialize ClientOptions as an object, 
            # but don't just pass a dict. This ensures all internal 
            # attributes like .headers and .storage exist.
            opts = ClientOptions(
                schema="supabase_functions",
                # Explicitly setting these to their defaults 
                # prevents attribute errors in strict SDK versions
                headers={},
                storage_client_timeout=10
            )
            
            _client = create_client(
                url, 
                key, 
                options=opts
            )
            logger.info("Supabase client initialized with schema: supabase_functions")
        except Exception as e:
            # This captures the 'dict' object has no attribute 'headers' error
            raise RuntimeError(f"Supabase client initialization failed: {e}")

    return _client

# — MAIN INSERT FUNCTION —

async def insert_packages_to_supabase(
    packages: List[Dict[str, Any]],
    source_url: str
) -> Dict[str, Any]:
    """
    Insert embedded packages into their respective Supabase specialist tables.
    """
    if not packages:
        return {"inserted_count": 0, "skipped_count": 0, "failed_count": 0, "details": []}

    client = get_supabase_client()
    inserted_count = 0
    skipped_count = 0
    failed_count = 0
    details = []

    for i, package in enumerate(packages):
        table = package.get("table")
        content = package.get("content", "")
        embedding = package.get("embedding")
        word_count = package.get("word_count", 0)

        if embedding is None or not content.strip():
            skipped_count += 1
            continue

        row = {
            "content": content,
            "embedding": embedding,
            "source_url": source_url,
            "chunk_index": i,
            "word_count": word_count,
        }

        try:
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(
                None,
                lambda r=row, t=table: client.table(t).insert(r).execute()
            )
            inserted_count += word_count
            details.append({"index": i, "status": "inserted"})
        except Exception as e:
            failed_count += 1
            logger.error(f"Insert failed: {e}")
            details.append({"index": i, "status": "failed", "error": str(e)})

    return {
        "inserted_count": inserted_count,
        "skipped_count": skipped_count,
        "failed_count": failed_count,
        "details": details
    }
