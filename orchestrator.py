# orchestrator.py - UPDATED IMPORTS

import asyncio
import logging
from typing import Dict, Any

from config import BrainState, SPECIALIST_TABLES

# We keep the crawler's version as the primary name
from crawler import process_text_into_packages 
from learning import run_learning_pipeline

# We ALIAS the rewrite version so it doesn't collide
from rewrites import process_text_into_packages as rewrite_to_packages 

from embedder import embed_packages
from memory import insert_packages_to_supabase, get_supabase_client
from gap_analyzer import GapAnalyzer

# ... rest of your code ...
