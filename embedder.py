# embedder.py - Generates 768d vector embeddings using google-genai SDK
# Refactored for gemini-embedding-001 compatibility (Feb 2026)

import os
import logging
import asyncio
from typing import List
from google import genai
from google.genai import types  # Required for dimension configuration
from dotenv import load_dotenv

load_dotenv()

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("Embedder")

# — CONFIGURATION —
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

# As of Jan 2026, text-embedding-004 is retired. 
# gemini-embedding-001 is the recommended stable replacement.
EMBEDDING_MODEL = "gemini-embedding-001" 

# gemini-embedding-001 supports Matryoshka learning, 
# allowing us to request 768d instead of its native 3072d.
EMBEDDING_DIMENSIONS = 768 
RATE_LIMIT_DELAY = 1.1  # Safety delay for free-tier users

if not GEMINI_API_KEY:
    raise RuntimeError(
        "GEMINI_API_KEY environment variable not set. "
        "Get your key from https://aistudio.google.com/app/apikey"
    )

# Initialize the GenAI Client
client = genai.Client(api_key=GEMINI_API_KEY)

async def embed_text(text: str) -> List[float]:
    """
    Generate a 768-dimension vector embedding for a single text string.
    """
    if not text or not text.strip():
        raise ValueError("Cannot embed empty text.")

    try:
        # We use asyncio.to_thread because the genai SDK calls are blocking
        response = await asyncio.to_thread(
            client.models.embed_content,
            model=EMBEDDING_MODEL,
            contents=text,
            config=types.EmbedContentConfig(
                output_dimensionality=EMBEDDING_DIMENSIONS
            )
        )

        if not response.embeddings:
            raise ValueError("No embeddings returned from Gemini.")

        # Extract the vector values
        embedding = response.embeddings[0].values

        # Validation check
        if len(embedding) != EMBEDDING_DIMENSIONS:
            raise ValueError(
                f"Dimension mismatch: got {len(embedding)}, expected {EMBEDDING_DIMENSIONS}"
            )

        logger.info(f"Successfully embedded text ({len(embedding)}d)")
        return embedding

    except Exception as e:
        logger.error(f"Embedding failed: {e}")
        raise RuntimeError(f"Embedding failed: {str(e)}")

async def embed_packages(packages: list) -> list:
    """
    Embed all packages, respecting Gemini rate limits.
    Each package is expected to be a dict with a 'content' key.
    """
    if not packages:
        logger.warning("embed_packages called with empty package list")
        return packages

    logger.info(f"Starting embedding pipeline for {len(packages)} packages...")

    for i, package in enumerate(packages):
        content = package.get("content", "")

        if not content.strip():
            logger.warning(f"Package {i} has empty content - skipping")
            package["embedding"] = None
            continue

        try:
            # Apply rate limiting delay after the first item
            if i > 0:
                await asyncio.sleep(RATE_LIMIT_DELAY)

            embedding = await embed_text(content)
            package["embedding"] = embedding

            logger.info(f"Package {i + 1}/{len(packages)} processed.")

        except Exception as e:
            logger.error(f"Failed to embed package {i}: {e}")
            # Raise a custom error to let the Orchestrator handle the pipeline failure
            raise RuntimeError(f"Embedding pipeline failed at package {i}: {str(e)}")

    return packages
