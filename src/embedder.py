# embedder.py - Generates vector embeddings using Google Gemini text-embedding-004

import os
import logging
import asyncio
import time
from typing import List
import google.generativeai as genai
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(“Embedder”)

# — CONFIGURATION —

GEMINI_API_KEY = os.getenv(“GEMINI_API_KEY”)
EMBEDDING_MODEL = “models/text-embedding-004”
EMBEDDING_DIMENSIONS = 768
RATE_LIMIT_DELAY = 1.1  # Gemini free tier: 1 request/second — slightly over to be safe

# — SETUP —

if not GEMINI_API_KEY:
raise RuntimeError(
“GEMINI_API_KEY environment variable not set. “
“Get your key from https://aistudio.google.com/app/apikey”
)

genai.configure(api_key=GEMINI_API_KEY)

def embed_text(text: str) -> List[float]:
“””
Generate a 768-dimension vector embedding for a single text string.

```
Args:
    text: The content string to embed

Returns:
    List of 768 floats representing the semantic vector

Raises:
    ValueError: If embedding fails or returns unexpected dimensions
"""
try:
    result = genai.embed_content(
        model=EMBEDDING_MODEL,
        content=text,
        task_type="retrieval_document"  # Optimized for DB storage + retrieval
    )

    embedding = result["embedding"]

    # Sanity check dimensions
    if len(embedding) != EMBEDDING_DIMENSIONS:
        raise ValueError(
            f"Unexpected embedding dimensions: got {len(embedding)}, "
            f"expected {EMBEDDING_DIMENSIONS}"
        )

    logger.info(f"Embedded {len(text.split())} words → {EMBEDDING_DIMENSIONS}d vector")
    return embedding

except Exception as e:
    logger.error(f"Embedding failed: {e}")
    raise ValueError(f"Embedding failed: {str(e)}")
```

async def embed_text_async(text: str) -> List[float]:
“””
Async wrapper for embed_text — runs in thread pool to avoid blocking
the event loop since Gemini SDK is synchronous.

```
Args:
    text: The content string to embed

Returns:
    List of 768 floats
"""
loop = asyncio.get_event_loop()
return await loop.run_in_executor(None, embed_text, text)
```

async def embed_packages(packages: list) -> list:
“””
Embed all packages from rewrites.py, respecting Gemini’s 1 req/sec rate limit.
Adds ‘embedding’ field to each package in place.

```
Args:
    packages: List of package dicts from rewrites.py
              Each must have 'content' field

Returns:
    Same list with 'embedding' field added to each package

Raises:
    ValueError: If any embedding fails
"""
if not packages:
    logger.warning("embed_packages called with empty package list")
    return packages

logger.info(f"Embedding {len(packages)} packages...")

for i, package in enumerate(packages):
    content = package.get("content", "")

    if not content.strip():
        logger.warning(f"Package {i} has empty content — skipping embedding")
        package["embedding"] = None
        continue

    try:
        # Respect Gemini free tier rate limit
        if i > 0:
            await asyncio.sleep(RATE_LIMIT_DELAY)

        package["embedding"] = await embed_text_async(content)
        logger.info(f"Package {i + 1}/{len(packages)} embedded → table: {package.get('table', 'unknown')}")

    except Exception as e:
        logger.error(f"Failed to embed package {i}: {e}")
        raise ValueError(f"Embedding pipeline failed at package {i}: {str(e)}")

logger.info(f"All {len(packages)} packages embedded successfully")
return packages
```
