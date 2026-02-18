# rewrites.py - Chunks and classifies scraped text into packages

# No summarization — raw text is chunked to preserve all knowledge

import os
import re
import asyncio
import logging
from openai import AsyncOpenAI
from dotenv import load_dotenv
from config import SPECIALIST_TABLES

load_dotenv()

logger = logging.getLogger("Rewrites")

# — OPENROUTER CONFIGURATION —

OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
MODEL = "meta-llama/llama-3-70b-instruct"

CHUNK_SIZE = 800       # Target words per chunk
CHUNK_OVERLAP = 50     # Words of overlap between chunks for context continuity

if not OPENROUTER_API_KEY:
    raise RuntimeError(
        "OPENROUTER_API_KEY environment variable not set. "
        "Get your key from https://openrouter.ai/keys"
    )

client = AsyncOpenAI(
    api_key=OPENROUTER_API_KEY,
    base_url="https://openrouter.ai/api/v1"
)

def chunk_text(text: str) -> list:
    """
    Split text into ~800 word chunks by word count, not by headings.
    Tries to split on sentence boundaries for cleaner chunks.
    """
    # Clean up whitespace
    text = re.sub(r'\n{3,}', '\n\n', text.strip())

    words = text.split()
    if not words:
        return []

    chunks = []
    start = 0

    while start < len(words):
        end = min(start + CHUNK_SIZE, len(words))

        # Try to end on a sentence boundary within the last 100 words
        if end < len(words):
            chunk_words = words[start:end]
            chunk_text_str = ' '.join(chunk_words)

            # Find last sentence-ending punctuation in the final 100 words
            last_sentence = max(
                chunk_text_str.rfind('. ', len(chunk_text_str) - 600),
                chunk_text_str.rfind('! ', len(chunk_text_str) - 600),
                chunk_text_str.rfind('? ', len(chunk_text_str) - 600),
            )

            if last_sentence > 0:
                # Trim to sentence boundary
                trimmed = chunk_text_str[:last_sentence + 1].strip()
                chunks.append(trimmed)
                # Count words in trimmed chunk to set next start
                trimmed_word_count = len(trimmed.split())
                start = start + trimmed_word_count - CHUNK_OVERLAP
            else:
                chunks.append(chunk_text_str)
                start = end - CHUNK_OVERLAP
        else:
            chunks.append(' '.join(words[start:end]))
            break

        # Safety: prevent infinite loop
        if start <= 0:
            break

    return [c for c in chunks if len(c.split()) >= 50]

async def process_text_into_packages(text: str) -> tuple:
    """
    Main pipeline: chunk raw text and classify each chunk.
    No summarization — all original content is preserved.
    """
    if not text.strip():
        logger.warning("process_text_into_packages called with empty text")
        return [], 0

    try:
        chunks = chunk_text(text)

        if not chunks:
            logger.warning("No usable chunks found after splitting")
            return [], 0

        logger.info(f"Split into {len(chunks)} chunks for processing")

        packages = []
        total_words = 0

        for i, chunk in enumerate(chunks):
            logger.info(f"Classifying chunk {i + 1}/{len(chunks)}...")

            word_count = len(chunk.split())
            suggested_table = await classify_section(chunk)
            await asyncio.sleep(0.3)

            package = {
                "content": chunk,
                "word_count": word_count,
                "table": suggested_table,
                "embedding": None
            }

            packages.append(package)
            total_words += word_count

            logger.info(f"Chunk {i + 1} complete - words: {word_count}, table: {suggested_table}")

        logger.info(f"All chunks processed - {len(packages)} packages, {total_words} total words")
        return packages, total_words

    except Exception as e:
        logger.error(f"Rewrite pipeline failed: {e}")
        raise ValueError(f"Rewrite process failed: {str(e)}")

async def classify_section(text: str) -> str:
    """
    Classify a chunk into one of the specialist tables.
    """
    tables_list = ", ".join(SPECIALIST_TABLES)

    prompt = (
        f"Classify this text into exactly ONE of these Supabase tables:\n"
        f"{tables_list}\n\n"
        f"Rules:\n"
        f"- Return ONLY the table name, nothing else\n"
        f"- Pick the single best fit (e.g. SEO content -> seo)\n"
        f"- Default to master_strategy if genuinely unclear\n\n"
        f"Text (first 600 chars):\n{text[:600]}"
    )

    try:
        response = await client.chat.completions.create(
            model=MODEL,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=20,
            temperature=0.0
        )
        table = response.choices[0].message.content.strip().lower()

        # Strip any extra words the model might add
        table = table.split()[0] if table.split() else "master_strategy"

        if table not in SPECIALIST_TABLES:
            logger.warning(f"Classifier returned unknown table '{table}' - falling back to master_strategy")
            return "master_strategy"

        return table

    except Exception as e:
        logger.error(f"Classification failed: {e}")
        raise ValueError(f"Classify failed: {str(e)}")
