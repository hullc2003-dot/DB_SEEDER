# memory.py - Supabase client compatibility shim + insert helper
# Replace your existing memory.py with this file and redeploy.

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
    Compatibility shim for supabase-py ClientOptions.
    Provides attribute-style access for fields the SDK expects and minimal
    dict-like access for safety.
    Extend this class if a new missing attribute appears in the traceback.
    """
    def __init__(
        self,
        schema: str = "public",
        headers: Optional[Dict[str, str]] = None,
        storage: Optional[Any] = None,
        storage_client_timeout: int = 10,
        realtime: Optional[Dict[str, Any]] = None,
        auto_refresh_token: bool = True,
        persist_session: bool = True,
        local_storage: Optional[Any] = None,
        headers_auth: Optional[Dict[str, str]] = None,
        # include any other defaults you expect the SDK to access
    ):
        # basic options
        self.schema = schema
        self.headers = headers or {}

        # storage is often accessed with attribute-style .headers, .url, .timeout
        if storage is None:
            self.storage = SimpleNamespace(headers={}, url=None, timeout=storage_client_timeout)
        else:
            if isinstance(storage, dict):
                # convert dict to SimpleNamespace so attribute access works
                self.storage = SimpleNamespace(**storage)
            else:
                self.storage = storage

        self.storage_client_timeout = storage_client_timeout
        self.realtime = realtime or {}

        # session and auth related options commonly used by supabase-py
        self.auto_refresh_token = auto_refresh_token
        self.persist_session = persist_session

        if local_storage is None:
            # minimal local_storage shim: get(key, default) and set(key, value)
            self.local_storage = SimpleNamespace(
                get=lambda k, default=None: default,
                set=lambda k, v: None
            )
        else:
            self.local_storage = local_storage

        # sometimes code expects a differently named headers dict
        self.headers_auth = headers_auth or {}

    # Provide mapping-like access in case some code uses options["schema"]
    def __getitem__(self, key):
        return getattr(self, key)

    def get(self, key, default=None):
        return getattr(self, key, default)


def get_supabase_client(schema: str = "supabase_functions") -> Client:
    """
    Return a singleton Supabase client. Uses a compatibility options object so
    supabase-py versions that expect attribute-style access will work.
    """
    global _client
    if _client is None:
        url = os.getenv("SUPABASE_URL")
        key = os.getenv("SUPABASE_KEY") or os.getenv("SUPABASE_SERVICE_ROLE_KEY")
        if not url or not key:
            raise RuntimeError("Missing Supabase credentials (SUPABASE_URL / SUPABASE_KEY).")

        try:
            opts = _CompatClientOptions(
                schema=schema,
                headers={},
                storage={"headers": {}, "url": None, "timeout": 10},
                storage_client_timeout=10,
                realtime={},
                auto_refresh_token=True,
                persist_session=True,
            )

            _client = create_client(url, key, options=opts)
            logger.info("Supabase client initialized with schema: %s", schema)
        except Exception as e:
            # keep the original traceback available by chaining
            raise RuntimeError(f"Supabase client initialization failed: {e}") from e

    return _client


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
            "content": content,
            "embedding": embedding,
            "source_url": source_url,
            "chunk_index": i,
            "word_count": word_count,
        }

        try:
            # run synchronous client call in threadpool to avoid blocking event loop
            result = await loop.run_in_executor(
                None,
                lambda r=row, t=table: get_supabase_client().table(t).insert(r).execute()
            )

            # supabase client often returns a dict-like response; attempt to inspect status
            status_code = None
            try:
                status_code = getattr(result, "status_code", None)
            except Exception:
                status_code = None

            if status_code not in (None, 200, 201):
                logger.warning("Insert returned non-2xx status: %s", status_code)

            inserted_count += 1
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


# Optional: quick local debug when run directly
if __name__ == "__main__":
    # TEMP DEBUG: verify client initialization locally
    try:
        client = get_supabase_client()
        print("Supabase client initialized:", type(client))
    except Exception as exc:
        print("Initialization error:", repr(exc))
