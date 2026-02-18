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

GROQ_API_KEY = os.getenv("GROQ_API_KEY")
MODEL = "meta-llama/llama-4-scout-17b-16e-instruct"

CHUNK_SIZE = 800
CHUNK_OVERLAP = 50

if not OPENROUTER_API_KEY:
    raise RuntimeError("OPENROUTER_API_KEY environment variable not set.")

client = AsyncOpenAI(
    api_key=OPENROUTER_API_KEY,
    base_url="https://openrouter.ai/api/v1"
)

def chunk_text(text: str) -> list:
    text = re.sub(r'\n{3,}', '\n\n', text.strip())
    words = text.split()
    if not words:
        return []

    chunks = []
    start = 0

    while start < len(words):
        end = min(start + CHUNK_SIZE, len(words))

        if end < len(words):
            chunk_words = words[start:end]
            chunk_text_str = ' '.join(chunk_words)
            last_sentence = max(
                chunk_text_str.rfind('. ', len(chunk_text_str) - 600),
                chunk_text_str.rfind('! ', len(chunk_text_str) - 600),
                chunk_text_str.rfind('? ', len(chunk_text_str) - 600),
            )
            if last_sentence > 0:
                trimmed = chunk_text_str[:last_sentence + 1].strip()
                chunks.append(trimmed)
                trimmed_word_count = len(trimmed.split())
                start = start + trimmed_word_count - CHUNK_OVERLAP
            else:
                chunks.append(chunk_text_str)
                start = end - CHUNK_OVERLAP
        else:
            chunks.append(' '.join(words[start:end]))
            break

        if start <= 0:
            break

    return [c for c in chunks if len(c.split()) >= 50]

async def generate_title(text: str) -> str:
    prompt = (
        "Generate a concise, specific title for this content.\n"
        "Rules:\n"
        "- Maximum 6 words\n"
        "- No quotes or punctuation at the end\n"
        "- Be specific to the actual topic, not generic\n"
        "- Return ONLY the title, nothing else\n\n"
        f"Content (first 400 chars):\n{text[:400]}"
    )
    try:
        response = await client.chat.completions.create(
            model=MODEL,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=40,
            temperature=0.2
        )
        return response.choices[0].message.content.strip().strip('"').strip("'")
    except Exception as e:
        logger.error(f"Title generation failed: {e}")
        return "Untitled"

async def process_text_into_packages(text: str) -> tuple:
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
            await asyncio.sleep(50.0)

            title = await generate_title(chunk)
            await asyncio.sleep(50.0)

            package = {
                "title": title,
                "content": chunk,
                "word_count": word_count,
                "table": suggested_table,
                "embedding": None
            }

            packages.append(package)
            total_words += word_count

            logger.info(f"Chunk {i + 1} complete - words: {word_count}, table: {suggested_table}, title: {title}")

        logger.info(f"All chunks processed - {len(packages)} packages, {total_words} total words")
        return packages, total_words

    except Exception as e:
        logger.error(f"Rewrite pipeline failed: {e}")
        raise ValueError(f"Rewrite process failed: {str(e)}")

async def classify_section(text: str) -> str:
    prompt = (
        f"You are classifying SEO and digital marketing content into specialist knowledge tables.\n"
        f"ALL of these tables are SEO-related subcategories. Pick the MOST SPECIFIC match:\n\n"
        f"- seo: general SEO, rankings, algorithms, technical SEO, on-page optimization\n"
        f"- backlinks: link building, outreach, anchor text, domain authority\n"
        f"- content_design: content creation, copywriting, UX writing, page structure\n"
        f"- social_media: social platforms, engagement, paid social, influencers\n"
        f"- analytics: tracking, metrics, reporting, Google Analytics, data\n"
        f"- ai_prompt_engineering: AI tools, ChatGPT, prompts, LLMs\n"
        f"- website_builder_mastery: site speed, CMS, WordPress, technical setup\n"
        f"- psychology_empathy: persuasion, user behavior, conversion psychology\n"
        f"- schema_skills: structured data, schema markup, rich results\n"
        f"- multimodal_visual_search: image SEO, video SEO, visual search\n"
        f"- critical_thinking: strategy, research, planning, frameworks\n"
        f"- meta_skills: productivity, learning, personal development\n"
        f"- master_strategy: broad strategy that spans multiple categories\n"
        f"- code_skills: HTML, CSS, JavaScript, dev tools\n"
        f"- website_types: ecommerce, blogs, landing pages, site types\n\n"
        f"Return ONLY the table name. Prefer specific tables over 'seo' or 'master_strategy'.\n\n"
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
        table = table.split()[0] if table.split() else "master_strategy"

        if table not in SPECIALIST_TABLES:
            logger.warning(f"Classifier returned unknown table '{table}' - falling back to master_strategy")
            return "master_strategy"

        return table

    except Exception as e:
        logger.error(f"Classification failed: {e}")
        raise ValueError(f"Classify failed: {str(e)}")
