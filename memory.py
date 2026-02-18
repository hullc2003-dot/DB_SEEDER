# memory.py - Fixed: use attribute-compatible ClientOptions shim for supabase 2.28.0

import os
import logging
import asyncio
from typing import List, Dict, Any, Optional, Sequence
from types import SimpleNamespace
from supabase import create_client, Client
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger("Memory")
logger.setLevel(logging.INFO)

# Optional: restrict which tables can be written to (prevent accidental injection)
_ALLOWED_TABLES: Sequence[str] = (
    "website_builder_mastery_junk",
    "seo_junk",
    "psychology_empathy_junk",
    "website_types_junk",
    "analytics_junk",
    "content_design_junk",
    "multimodal_visual_search_junk",
    "ai_prompt_engineering_junk",
    "code_skills_junk",
    "schema_skills_junk",
    "meta_skills_junk",
    "backlinks_junk",
    "social_media_junk",
    "master_strategy_junk",
    "critical_thinking_junk",
)

_client: Optional[Client] = None

class _CompatClientOptions:
    """
    Small compatibility shim that provides attribute-style access to keys
    the supabase client expects. Also implements dict-like getitem for safety.
    """
    def __init__(
        self,
        schema: str = "public",
        headers: Optional[Dict[str, str]] = None,
        storage: Optional[Any] = None,
        storage_client_timeout: int = 10,
        realtime: Optional[Dict[str, Any]] = None,
    ):
        self.schema = schema
        self.headers = headers or {}
        # storage: supply a SimpleNamespace so attributes like .headers work
        if storage is None:
            self.storage = SimpleNamespace(headers={}, url=None, timeout=storage_client_timeout)
        else:
            # if user passed a dict, convert to SimpleNamespace for attribute access
            if isinstance(storage, dict):
                self.storage = SimpleNamespace(**storage)
            else:
                self.storage = storage
        self.storage_client_timeout = storage_client_timeout
        self.realtime = realtime or {}

    # optional dict-like access (some code may do options["schema"])
    def __getitem__(self, key):
        return getattr(self, key)

    def get(self, key, default=None):
        return getattr(self, key, default)

def get_supabase_client(schema: str = "supabase_functions") -> Client:
    """
    Return a singleton Supabase client. Use an attribute-compatible options shim
    because some supabase-py versions expect attribute access (options.storage.headers).
    """
    global _client
    if _client is None:
        url = os.getenv("SUPABASE_URL")
        key = os.getenv("SUPABASE_KEY") or os.getenv("SUPABASE_SERVICE_ROLE_KEY")
        if not url or not key:
            raise RuntimeError("Missing Supabase credentials (SUPABASE_URL / SUPABASE_KEY).")

        try:
            # Use the compatibility object so SDK code can access attributes.
            opts = _CompatClientOptions(
                schema=schema,
                headers={},
                storage={"headers": {}, "url": None, "timeout": 10},
                storage_client_timeout=10,
                realtime={},
            )

            _client = create_client(url, key, options=opts)
            logger.info("Supabase client initialized with schema: %s", schema)
        except Exception as e:
            raise RuntimeError(f"Supabase client initialization failed: {e}") from e

    return _client

async def insert_packages_to_supabase(
    packages: List[Dict[str, Any]],
    source_url: str,
    allowed_tables: Optional[Sequence[str]] = None,
) -> Dict[str, Any]:
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
            "content": content,
            "embedding": embedding,
            "source_url": source_url,
            "chunk_index": i,
            "word_count": word_count,
        }

        try:
            # run synchronous client call in threadpool
            result = await loop.run_in_executor(
                None,
                lambda r=row, t=table: client.table(t).insert(r).execute()
            )

            # supabase client may return a dict-like response; check error
            if getattr(result, "status_code", None) not in (None, 200, 201):
                logger.warning("Insert returned non-2xx status: %s", getattr(result, "status_code", result))
            inserted_count += 1  # count rows inserted
            details.append({"index": i, "status": "inserted", "table": table})
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
