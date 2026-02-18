# rewrites.py - Summarizes, adjusts, and classifies scraped text into packages

import os
import re
import asyncio
import logging
from groq import Asyncgroq
from dotenv import load_dotenv
from config import SPECIALIST_TABLES

load_dotenv()

logger = logging.getLogger("Rewrites")

# — GROQ CONFIGURATION —

GROQ_API_KEY = os.getenv("GROQ_API_KEY")
GROQ_MODEL = "llama3-70b-8192"  # Updated — mixtral-8x7b-32768 is deprecated

if not GROQ_API_KEY:
    raise RuntimeError(
        "GROQ_API_KEY environment variable not set. "
        "Get your key from https://console.groq.com/keys"
    )

# Groq uses OpenAI-compatible client pointed at Groq's base URL

client = AsyncOpenAI(
    api_key=GROQ_API_KEY,
    base_url="https://api.groq.com/openai/v1"
)

async def process_text_into_packages(text: str) -> tuple:
    """
    Main pipeline function: split, summarize, adjust, and classify scraped text.

    Steps:
        1. Split raw text into sections
        2. Summarize each section (max 25% reduction)
        3. Adjust length to 500-1000 word target if needed
        4. Classify into one of the 15 specialist tables

    Args:
        text: Raw plain text from learning.py

    Returns:
        Tuple of (packages list, total_word_count)

    Raises:
        ValueError: If any step in the pipeline fails
    """
    if not text.strip():
        logger.warning("process_text_into_packages called with empty text")
        return [], 0

    try:
        # Step 1: Split into sections on headings or double newlines
        sections = re.split(r'\n\s*(#{1,6}\s.*?$|\n\n+)', text, flags=re.MULTILINE)
        sections = [s.strip() for s in sections if s.strip()]

        # Gate: skip micro-sections under 50 words — not worth an LLM call
        sections = [s for s in sections if len(s.split()) >= 50]

        if not sections:
            logger.warning("No usable sections found after split and filtering")
            return [], 0

        logger.info(f"Split into {len(sections)} sections for processing")

        packages = []
        total_words = 0

        for i, section in enumerate(sections):
            logger.info(f"Processing section {i + 1}/{len(sections)}...")

            # Step 2: Summarize
            summary = await summarize_section(section)
            word_count = len(summary.split())

            # Step 3: Adjust length if outside 500-1000 word target
            if word_count < 500 or word_count > 1000:
                summary = await adjust_summary_length(summary, word_count)
                word_count = len(summary.split())

            # Step 4: Classify into specialist table
            suggested_table = await classify_section(summary)

            package = {
                "content": summary,
                "word_count": word_count,
                "table": suggested_table,
                "embedding": None  # Filled in by embedder.py
            }

            packages.append(package)
            total_words += word_count

            logger.info(
                f"Section {i + 1} complete — "
                f"words: {word_count}, table: {suggested_table}"
            )

        logger.info(
            f"All sections processed — "
            f"{len(packages)} packages, {total_words} total words"
        )
        return packages, total_words

    except Exception as e:
        logger.error(f"Rewrite pipeline failed: {e}")
        raise ValueError(f"Rewrite process failed: {str(e)}")

async def summarize_section(section: str) -> str:
    """
    Summarize a section, retaining at least 75% of original word count.

    Args:
        section: Raw text section to summarize

    Returns:
        Summarized text string
    """
    original_words = len(section.split())
    min_keep = int(original_words * 0.75)

    prompt = (
        f"Summarize this section for optimal readability and learning:\n"
        f"- Retain at least {min_keep} words. Prioritize coherent full sentences over brevity.\n"
        f"- Focus on educational value — keep key explanations, examples, and structure.\n"
        f"- Output readable paragraphs, not bullet fragments.\n\n"
        f"Section:\n{section}"
    )

    try:
        response = await client.chat.completions.create(
            model=GROQ_MODEL,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=2000,
            temperature=0.5
        )
        result = response.choices[0].message.content.strip()
        logger.info(f"Summarized {original_words} → {len(result.split())} words")
        return result

    except Exception as e:
        logger.error(f"Summarize failed: {e}")
        raise ValueError(f"Summarize failed: {str(e)}")

async def adjust_summary_length(summary: str, current_count: int) -> str:
    """
    Expand or condense a summary to fit the 500-1000 word target.

    Args:
        summary:       Current summary text
        current_count: Current word count

    Returns:
        Adjusted summary text
    """
    if current_count < 500:
        direction = (
            "Expand to at least 500 words while maintaining learnability. "
            "Add explanatory details, examples, or context where helpful."
        )
    else:
        direction = (
            "Condense to a maximum of 1000 words. "
            "Remove redundancies but preserve all key learning content."
        )

    prompt = f"{direction}\n\nSummary:\n{summary}"

    try:
        response = await client.chat.completions.create(
            model=GROQ_MODEL,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=2000,
            temperature=0.5
        )
        result = response.choices[0].message.content.strip()
        logger.info(f"Adjusted {current_count} → {len(result.split())} words")
        return result

    except Exception as e:
        logger.error(f"Length adjustment failed: {e}")
        raise ValueError(f"Length adjust failed: {str(e)}")

async def classify_section(summary: str) -> str:
    """
    Classify a summary into one of the 15 specialist tables.

    Args:
        summary: Summarized text to classify

    Returns:
        Table name string — guaranteed to be in SPECIALIST_TABLES
    """
    tables_list = ", ".join(SPECIALIST_TABLES)

    prompt = (
        f"Classify this summary into exactly ONE of these Supabase tables:\n"
        f"{tables_list}\n\n"
        f"Rules:\n"
        f"- Return ONLY the table name, nothing else\n"
        f"- Pick the single best fit (e.g. SEO content → seo)\n"
        f"- Default to master_strategy if genuinely unclear\n\n"
        f"Summary (first 1000 chars):\n{summary[:1000]}"
    )

    try:
        response = await client.chat.completions.create(
            model=GROQ_MODEL,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=50,
            temperature=0.0  # Deterministic — classification should not be creative
        )
        table = response.choices[0].message.content.strip().lower()

        # Validate — fall back to master_strategy if unrecognized
        if table not in SPECIALIST_TABLES:
            logger.warning(
                f"Classifier returned unknown table '{table}' — "
                f"falling back to master_strategy"
            )
            return "master_strategy"

        return table

    except Exception as e:
        logger.error(f"Classification failed: {e}")
        raise ValueError(f"Classify failed: {str(e)}")
