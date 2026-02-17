# memory.py - Inserts packages into Supabase
import asyncio
from config import supabase  # Shared client

async def insert_packages_to_supabase(packages: list) -> int:
    inserted_words = 0
    for package in packages:
        table = package["table"]
        data = {
            "content": package["content"],
            "word_count": package["word_count"]
            # Add: "source_url": url, "inserted_at": now() if needed in table schema
        }
        try:
            response = supabase.table(table).insert(data).execute()
            if response.data:
                inserted_words += package["word_count"]
            else:
                raise ValueError(f"Insert failed for {table}: {response.error}")
        except Exception as e:
            raise ValueError(f"Supabase insert error: {str(e)}")
    
    # Step 26: Return inserted count for orchestrator
    return inserted_words
