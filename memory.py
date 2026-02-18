# memory.py - Inserts embedded packages into Supabase specialist tables

import os
import logging
import asyncio
from typing import List, Dict, Any, Optional
from supabase import create_client, Client
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(“Memory”)

# — SUPABASE SINGLETON —

_client: Optional[Client] = None

def get_supabase_client() -> Client:
“””
Get or create Supabase client singleton.

```
Raises:
    RuntimeError: If SUPABASE_URL or SUPABASE_KEY are not set
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
        _client = create_client(url, key)
        logger.info("Supabase client initialized")
    except Exception as e:
        raise RuntimeError(f"Supabase client initialization failed: {e}")

return _client
```

# — MAIN INSERT FUNCTION —

async def insert_packages_to_supabase(
packages: List[Dict[str, Any]],
source_url: str
) -> Dict[str, Any]:
“””
Insert embedded packages into their respective Supabase specialist tables.

```
Each package must have:
    - content:    str   — summarized text
    - embedding:  list  — 768d vector from embedder.py (can be None)
    - table:      str   — target specialist table name
    - word_count: int   — word count of content

Args:
    packages:   List of package dicts from embedder.py
    source_url: The URL this content was scraped from

Returns:
    Dict with inserted_count, skipped_count, failed_count, and details
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

    # Skip packages with no embedding — not searchable
    if embedding is None:
        logger.warning(f"Package {i} has no embedding — skipping insert")
        skipped_count += 1
        details.append({
            "index": i,
            "table": table,
            "status": "skipped",
            "reason": "no embedding"
        })
        continue

    # Skip packages with no content
    if not content.strip():
        logger.warning(f"Package {i} has empty content — skipping insert")
        skipped_count += 1
        details.append({
            "index": i,
            "table": table,
            "status": "skipped",
            "reason": "empty content"
        })
        continue

    # Build the full row matching the Supabase schema
    row = {
        "content": content,
        "embedding": embedding,
        "source_url": source_url,
        "chunk_index": i,
        "word_count": word_count,
        # inserted_at is handled by Supabase default (now())
        # title is optional — can be added by orchestrator if available
    }

    try:
        # Run sync Supabase call in thread pool to stay async-safe
        loop = asyncio.get_event_loop()
        response = await loop.run_in_executor(
            None,
            lambda r=row, t=table: client.table(t).insert(r).execute()
        )

        if response.data:
            inserted_count += word_count
            logger.info(
                f"Package {i + 1}/{len(packages)} inserted → "
                f"table: {table}, words: {word_count}"
            )
            details.append({
                "index": i,
                "table": table,
                "status": "inserted",
                "word_count": word_count
            })
        else:
            raise ValueError(f"Insert returned no data for package {i}")

    except Exception as e:
        failed_count += 1
        logger.error(f"Insert failed for package {i} → table: {table} | Error: {e}")
        details.append({
            "index": i,
            "table": table,
            "status": "failed",
            "error": str(e)
        })

logger.info(
    f"Insert complete — "
    f"inserted: {inserted_count} words, "
    f"skipped: {skipped_count}, "
    f"failed: {failed_count}"
)

return {
    "inserted_count": inserted_count,
    "skipped_count": skipped_count,
    "failed_count": failed_count,
    "details": details
}
```
