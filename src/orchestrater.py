# orchestrater.py - Coordinator for the learning loop process
import asyncio
from dotenv import load_dotenv
import os
from learning import fetch_text_from_url, handoff_to_rewrites
from rewrites import process_text_into_packages
from memory import insert_packages_to_supabase
from config import supabase  # Assuming config.py has Supabase client

load_dotenv()

class Orchestrator:
    def __init__(self):
        self.messages = []
        self.fetched_word_count = 0
        self.inserted_word_count = 0

    async def start_learning_loop(self, url: str):
        # Step 4-5: Send URL to learning.py and trigger
        text, word_count = await fetch_text_from_url(url)
        
        # Step 7-8: Receive message from learning.py and hold
        self.messages.append(f"Text retrieved: {word_count} words")
        self.fetched_word_count = word_count
        
        # Step 9-10: Handoff to rewrites.py and receive confirmation
        handoff_success = await handoff_to_rewrites(text)
        self.messages.append("Handoff to rewrites complete" if handoff_success else "Handoff failed")
        
        # Step 11: Trigger rewrites.py
        packages, total_words = await process_text_into_packages(text)
        
        # Step 21-22: Receive from rewrites.py and hold word count
        self.messages.append(f"Packages passed to memory.py: {total_words} words")
        
        # Step 23: Trigger memory.py
        inserted_count = await insert_packages_to_supabase(packages)
        self.inserted_word_count = inserted_count
        
        # Step 26: Receive from memory.py
        self.messages.append("Insertion finished")
        
        # Step 27: Send message to UI (simulate or use webhook; for now, return)
        return f"Fetched word count: {self.fetched_word_count} | Inserted word count: {self.inserted_word_count} | Job complete"

# Example usage (integrate with ui_router.py)
if __name__ == "__main__":
    orchestrator = Orchestrator()
    asyncio.run(orchestrator.start_learning_loop("https://example.com"))
