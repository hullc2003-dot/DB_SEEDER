# rewrites.py - Summarizes and packages text (updated to use Groq API instead of Gemini/OpenAI)
from openai import AsyncOpenAI  # Groq is compatible with OpenAI client
import asyncio
import re
from dotenv import load_dotenv
import os

load_dotenv()

# Groq setup: Use Groq API key and base URL
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
GROQ_MODEL = 'mixtral-8x7b-32768'  # Or your preferred Groq model (e.g., 'llama2-70b-4096' for speed)

client = AsyncOpenAI(
    api_key=GROQ_API_KEY,
    base_url="https://api.groq.com/openai/v1"  # Groq's OpenAI-compatible endpoint
)

TABLES = [
    "ai_prompt_engineering_junk", "analytics_junk", "backlinks_junk", "code_skills_junk",
    "content_design_junk", "critical_thinking_junk", "master_strategy_junk", "meta_skills_junk",
    "multimodal_visual_search_junk", "psychology_empathy_junk", "schema_skills_junk",
    "seo_junk", "social_media_junk", "website_builder_mastery_junk", "website_types_junk"
]

async def process_text_into_packages(text: str) -> tuple:
    """Main function: Separate, summarize, package, and classify text (steps 12-20)."""
    try:
        # Step 12: Separate into sections using headings/titles/schema
        sections = re.split(r'\n\s*(#{1,6}\s.*?$|\w+:\s|\n\n+)', text, flags=re.MULTILINE)
        sections = [s.strip() for s in sections if s.strip()]

        packages = []
        total_words = 0  # Step 19: Accumulate total words
        
        for section in sections:
            # Step 13-15: Summarize (reduce <=25%, prioritize readability/learnability)
            summary = await summarize_section(section)
            word_count = len(summary.split())
            
            # Step 17: Adjust length if outside 500-1000, but prioritize learnability
            if word_count < 500 or word_count > 1000:
                summary = await adjust_summary_length(summary, word_count)
                word_count = len(summary.split())
            
            # Step 16: Classify/label with suggested table
            suggested_table = await classify_section(summary)
            
            # Package (step 16/18)
            package = {
                "content": summary,
                "word_count": word_count,
                "table": suggested_table
            }
            packages.append(package)
            total_words += word_count
        
        # Step 20: Return packages + total_words for handoff to memory.py
        return packages, total_words
    except Exception as e:
        raise ValueError(f"Rewrite process failed: {str(e)}")

async def summarize_section(section: str) -> str:
    """Summarize a section (steps 13-15)."""
    original_words = len(section.split())
    min_keep = int(original_words * 0.75)  # Max 25% reduction
    
    prompt = f"""
    Summarize this section for optimal readability and learning:
    - Retain at least {min_keep} words; prioritize coherent, full sentences over brevity.
    - Focus on educational value—keep key explanations, examples, and structure.
    - Output readable paragraphs, not fragments.
    Section: {section}
    """
    try:
        response = await client.chat.completions.create(
            model=GROQ_MODEL,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=2000,
            temperature=0.5  # Balanced for readability
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        raise ValueError(f"Summarize failed: {str(e)}")

async def adjust_summary_length(summary: str, current_count: int) -> str:
    """Adjust package size if needed (step 17)."""
    if current_count < 500:
        direction = "Expand to at least 500 words while maintaining learnability and adding explanatory details if helpful."
    else:
        direction = "Condense to max 1000 words, removing redundancies but preserving key learning content."
    
    prompt = f"{direction}\nSummary: {summary}"
    try:
        response = await client.chat.completions.create(
            model=GROQ_MODEL,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=2000
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        raise ValueError(f"Length adjust failed: {str(e)}")

async def classify_section(summary: str) -> str:
    """Classify into a junk table (step 16)."""
    prompt = f"""
    Classify this summary into ONE of these Supabase tables: {', '.join(TABLES)}.
    Pick the best fit (e.g., SEO content -> seo_junk).
    Return ONLY the table name.
    Summary: {summary[:1000]}...
    """
    try:
        response = await client.chat.completions.create(
            model=GROQ_MODEL,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=50
        )
        table = response.choices[0].message.content.strip()
        return table if table in TABLES else TABLES[0]  # Fallback to first table
    except Exception as e:
        raise ValueError(f"Classify failed: {str(e)}")
