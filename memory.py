# memory.py - Supabase client wrapper usage + insert helper
# Replace your existing memory.py with this file and redeploy.

import os
import logging
import asyncio
from typing import List, Dict, Any, Optional, Sequence

from dotenv import load_dotenv

# Load env for local dev
load_dotenv()

logger = logging.getLogger("Memory")
logger.setLevel(logging.INFO)

# Optional: restrict which tables can be written to (prevent accidental injection)
_ALLOWED_TABLES: Sequence[str] = (
    "website_builder_mastery",
    "seo",
    "psychology_empathy",
    "website_types",
    "analytics",
    "content_design",
    "multimodal_visual_search",
    "ai_prompt_engineering",
    "code_skills",
    "schema_skills",
    "meta_skills",
    "backlinks",
    "social_media",
    "master_strategy",
    "critical_thinking",
)

# Import the centralized supabase client factory/wrapper you added
from supabase_client import get_supabase_client  # ensure supabase_client.py is on PYTHONPATH


async def insert_packages_to_supabase(
    packages: List[Dict[str, Any]],
    source_url: str,
    allowed_tables: Optional[Sequence[str]] = None,
) -> Dict[str, Any]:
    """
    Insert list of packages into allowed tables in Supabase.
    Each package is expected to contain:
      - table: str (target table name)
      - content: str
      - embedding: list[float] or similar
      - word_count: int (optional)

    Returns a summary dict with counts and per-package details.
    """
    if not packages:
        return {"inserted_count": 0, "skipped_count": 0, "failed_count": 0, "details": []}

    allowed = set(allowed_tables or _ALLOWED_TABLES)
    client = get_supabase_client()
    inserted_count = 0
    skipped_count = 0
    failed_count = 0
    details = []

    # prefer get_running_loop when inside an async function
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = asyncio.get_event_loop()

    for i, package in enumerate(packages):
        table = package.get("table")
        content = package.get("content", "") or ""
        embedding = package.get("embedding")
        word_count = int(package.get("word_count") or 0)

        if not table or table not in allowed:
            logger.warning("Skipping package %s: invalid or disallowed table '%s'", i, table)
            skipped_count += 1
            details.append({"index": i, "status": "skipped", "reason": "invalid_table"})
            continue

        if embedding is None or not content.strip():
            logger.info("Skipping package %s: no embedding or empty content", i)
            skipped_count += 1
            details.append({"index": i, "status": "skipped", "reason": "no_embedding_or_content"})
            continue

        row = {
    "title": package.get("title", ""),  # add this
    "content": content,
    "embedding": embedding,
    "source_url": source_url,
    "chunk_index": i,
    "word_count": word_count,
}

        }

        try:
            # run synchronous client call in threadpool to avoid blocking event loop
            def _insert_row(r=row, t=table):
                # Modern client uses .from_('table') fluent API
                return get_supabase_client().from_(t).insert(r).execute()

            result = await loop.run_in_executor(None, _insert_row)

            # Inspect typical response shape: SDK often returns object with .data and .error
            err = getattr(result, "error", None)
            data = getattr(result, "data", None)

            if err:
                logger.warning("Insert returned error for package %s into %s: %s", i, table, err)
                failed_count += 1
                details.append({"index": i, "status": "failed", "error": str(err)})
                continue

            # success
            inserted_count += 1
            details.append({"index": i, "status": "inserted", "table": table, "data": data})
        except Exception as e:
            failed_count += 1
            logger.exception("Insert failed for package %s into table %s: %s", i, table, e)
            details.append({"index": i, "status": "failed", "error": str(e)})

    return {
        "inserted_count": inserted_count,
        "skipped_count": skipped_count,
        "failed_count": failed_count,
        "details": details,
    }


# Optional: quick local debug when run directly
if __name__ == "__main__":
    import json
    try:
        client = get_supabase_client()
        print("Supabase client initialized:", type(client))
        # Run a small test query if allowed
        try:
            example = client.from_("pg_catalog.pg_tables").select("tablename").limit(1).execute()
            print("Example query data:", getattr(example, "data", None))
        except Exception as qexc:
            print("Example query failed:", repr(qexc))
    except Exception as exc:
        print("Initialization error:", repr(exc))
