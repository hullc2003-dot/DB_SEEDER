# embedder.py - Generates 768d vector embeddings using google-genai SDK

import os
import logging
import asyncio
from typing import List
from google import genai
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger("Embedder")

# — CONFIGURATION —

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
EMBEDDING_MODEL = "text-embedding-004"  # ⚠️ DO NOT prefix with "models/"
EMBEDDING_DIMENSIONS = 768
RATE_LIMIT_DELAY = 1.1  # keeps you well inside free tier

if not GEMINI_API_KEY:
    raise RuntimeError(
        "GEMINI_API_KEY environment variable not set. "
        "Get your key from https://aistudio.google.com/app/apikey"
    )

client = genai.Client(api_key=GEMINI_API_KEY)


async def embed_text(text: str) -> List[float]:
    """
    Generate a 768-dimension vector embedding for a single text string.
    Uses Gemini text-embedding-004.
    """

    if not text or not text.strip():
        raise ValueError("Cannot embed empty text.")

    try:
        response = await asyncio.to_thread(
            client.models.embed_content,
            model=EMBEDDING_MODEL,
            contents=text
        )

        if not response.embeddings:
            raise ValueError("No embeddings returned from Gemini.")

        embedding = response.embeddings[0].values

        if len(embedding) != EMBEDDING_DIMENSIONS:
            raise ValueError(
                f"Unexpected embedding dimensions: got {len(embedding)}, "
                f"expected {EMBEDDING_DIMENSIONS}"
            )

        logger.info(
            f"Embedded {len(text.split())} words → {EMBEDDING_DIMENSIONS}d vector"
        )

        return embedding

    except Exception as e:
        logger.error(f"Embedding failed: {e}")
        raise RuntimeError(f"Embedding failed: {str(e)}")


async def embed_packages(packages: list) -> list:
    """
    Embed all packages from rewrites.py, respecting Gemini rate limits.
    """

    if not packages:
        logger.warning("embed_packages called with empty package list")
        return packages

    logger.info(f"Embedding {len(packages)} packages...")

    for i, package in enumerate(packages):
        content = package.get("content", "")

        if not content.strip():
            logger.warning(f"Package {i} has empty content - skipping")
            package["embedding"] = None
            continue

        try:
            if i > 0:
                await asyncio.sleep(RATE_LIMIT_DELAY)

            embedding = await embed_text(content)
            package["embedding"] = embedding

            logger.info(
                f"Package {i + 1}/{len(packages)} embedded successfully"
            )

        except Exception as e:
            logger.error(f"Failed to embed package {i}: {e}")
            raise RuntimeError(
                f"Embedding pipeline failed at package {i}: {str(e)}"
            )

    return packages
