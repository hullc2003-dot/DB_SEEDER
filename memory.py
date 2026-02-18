# memory.py - Inserts embedded packages into Supabase specialist tables

import os
import logging
import asyncio
from typing import List, Dict, Any, Optional
from supabase import create_client, Client
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger("Memory")

# — SUPABASE SINGLETON —

_client: Optional[Client] = None

def get_supabase_client() -> Client:
    """
    Get or create Supabase client singleton configured for the 
    'supabase_functions' schema.
    """
    global _client

    if _client is None:
        url = os.getenv("SUPABASE_URL")
        key = os.getenv("SUPABASE_KEY") or os.getenv("SUPABASE_SERVICE_ROLE_KEY")

        if not url or not key:
            raise RuntimeError(
                "Missing Supabase credentials. "
                "Set SUPABASE_URL and SUPABASE_KEY environment variables."
            )

        try:
            # FIX: Use a dictionary for options. 
            # This avoids the 'ClientOptions has no attribute storage' error 
            # by letting the SDK merge your schema with its internal defaults.
            _client = create_client(
                url, 
                key, 
                options={"schema": "supabase_functions"}
            )
            logger.info("Supabase client initialized with schema: supabase_functions")
        except Exception as e:
            # This catches the 'ClientOptions' attribute error
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
        logger.warning("insert_packages called with empty package list")
        return {
            "inserted_count": 0,
            "skipped_count": 0,
            "failed_count": 0,
            "details": []
        }

    client = get_supabase_client()

    inserted_count = 0
    skipped_count = 0
    failed_count = 0
    details = []

    logger.info(f"Inserting {len(packages)} packages from {source_url}")

    for i, package in enumerate(packages):
        table = package.get("table")
        content = package.get("content", "")
        embedding = package.get("embedding")
        word_count = package.get("word_count", 0)

        if embedding is None or not content.strip():
            skipped_count += 1
            details.append({"index": i, "status": "skipped", "reason": "missing data"})
            continue

        row = {
            "content": content,
            "embedding": embedding,
            "source_url": source_url,
            "chunk_index": i,
            "word_count": word_count,
        }

        try:
            # Stay async-safe for sync SDK calls
            loop = asyncio.get_event_loop()
            response = await loop.run_in_executor(
                None,
                lambda r=row, t=table: client.table(t).insert(r).execute()
            )

            if response.data:
                inserted_count += word_count
                details.append({"index": i, "table": table, "status": "inserted"})
            else:
                raise ValueError("No data returned from insert")

        except Exception as e:
            failed_count += 1
            logger.error(f"Insert failed for package {i}: {e}")
            details.append({"index": i, "status": "failed", "error": str(e)})

    return {
        "inserted_count": inserted_count,
        "skipped_count": skipped_count,
        "failed_count": failed_count,
        "details": details
    }
