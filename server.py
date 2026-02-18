# server.py - FastAPI web server — wired to the seeding orchestrator

import os
import sys
import logging
import asyncio
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from dotenv import load_dotenv

from config import BrainState
from orchestrator import SeedingOrchestrator

load_dotenv()

# — PATH CONFIGURATION —

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
if BASE_DIR not in sys.path:
    sys.path.append(BASE_DIR)

# — LOGGING —

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s"
)
logger = logging.getLogger("RenderServer")

# — BRAIN STATE (singleton for the lifetime of the server) —

brain = BrainState()

# — FASTAPI APP —

app = FastAPI(title="AI Brain API — Seeding Pipeline")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[os.getenv("ALLOWED_ORIGIN", "*")],  # Lock this down in production
    allow_methods=["*"],
    allow_headers=["*"],
)

# — SCHEMAS —

class ChatRequest(BaseModel):
    input: str

class LearningRequest(BaseModel):
    seed_url: str  # The starting URL — crawler auto-discovers everything from here

class RewriteApproval(BaseModel):
    suggestion_id: str
    approved: bool = True

# — ENDPOINTS —

@app.get("/")
async def root():
    """Basic browser verification."""
    return {
        "status": "online",
        "mode": "Live",
        "agent": "Dale",
        "version": brain.version
    }

@app.get("/health")
async def health():
    """
    Status polling for the dashboard indicator light.
    Reads live kill switch state from BrainState.
    """
    kill_switch = brain.governance.kill_switches.get("global", False)
    master = brain.governance.master_enabled

    return {
        "status": "online" if master and not kill_switch else "disabled",
        "master_enabled": master,
        "kill_switch_active": kill_switch,
        "agent_id": brain.agent_id,
        "version": brain.version,
        "use_url_enabled": brain.learning.router_toggles.get("use_url", False)
    }

@app.post("/wake")
async def wake_up():
    """Keeps Render instance from sleeping."""
    return {"status": "awake", "message": "Backend session refreshed."}

@app.get("/check-env")
async def check_env():
    """Temporary env var checker — remove before going to production."""
    import os
    return {
        "SUPABASE_URL": "set" if os.getenv("SUPABASE_URL") else "MISSING",
        "SUPABASE_KEY": "set" if os.getenv("SUPABASE_KEY") else "MISSING",
        "SUPABASE_SERVICE_ROLE_KEY": "set" if os.getenv("SUPABASE_SERVICE_ROLE_KEY") else "MISSING",
        "GROQ_API_KEY": "set" if os.getenv("GROQ_API_KEY") else "MISSING",
        "GEMINI_API_KEY": "set" if os.getenv("GEMINI_API_KEY") else "MISSING",
        "ALLOWED_ORIGIN": "set" if os.getenv("ALLOWED_ORIGIN") else "MISSING",
    }


@app.post("/chat")
async def chat(req: ChatRequest):
    """
    Chat endpoint.
    If user input is a URL → trigger learning pipeline.
    Otherwise → normal conversational response.
    """

    text = req.input.strip()

    try:
        # Detect URL
        if text.startswith("http://") or text.startswith("https://"):

            logger.info(f"URL detected in chat. Triggering learning for: {text}")

            orchestrator = SeedingOrchestrator(brain=brain)
            report = await orchestrator.run(seed_url=text)

            if report["status"] == "failed":
                return {
                    "output": f"Learning pipeline failed.\nErrors: {report['errors']}"
                }

            return {
                "output": (
                    f"Learning complete ✅\n\n"
                    f"Seed: {report['seed_url']}\n"
                    f"Discovered: {report['urls_discovered']}\n"
                    f"Processed: {report['urls_processed']}\n"
                    f"Words Inserted: {report['total_inserted']}\n"
                )
            }

        # Otherwise normal chat behavior
        return {"output": f"Echo: {text}"}

    except Exception as e:
        logger.error(f"Chat error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/run-learning")
async def run_learning(req: LearningRequest):
    """
    Triggers the full seeding pipeline from a seed URL.

    The crawler auto-discovers all internal links from the seed URL,
    then runs each page through:
        fetch → rewrite → embed → insert → gap analysis

    Body:
        seed_url: The starting URL to crawl from

    Returns:
        Full pipeline report with counts and gap analysis
    """
    logger.info(f"Learning pipeline triggered — seed URL: {req.seed_url}")

    try:
        orchestrator = SeedingOrchestrator(brain=brain)
        report = await orchestrator.run(seed_url=req.seed_url)

        # Surface status through HTTP codes as well
        if report["status"] == "failed":
            raise HTTPException(
                status_code=500,
                detail={
                    "message": "Pipeline failed",
                    "report": report
                }
            )

        logger.info(
            f"Learning pipeline complete — "
            f"status: {report['status']}, "
            f"urls: {report['urls_processed']}/{report['urls_discovered']}, "
            f"words inserted: {report['total_inserted']}"
        )

        return {
            "status": report["status"],
            "summary": {
                "seed_url": report["seed_url"],
                "urls_discovered": report["urls_discovered"],
                "urls_processed": report["urls_processed"],
                "urls_failed": report["urls_failed"],
                "total_packages": report["total_packages"],
                "total_words_inserted": report["total_inserted"],
                "total_skipped": report["total_skipped"],
                "total_failed_inserts": report["total_failed_inserts"],
            },
            "gaps": report["gaps_found"],
            "errors": report["errors"]
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Learning pipeline error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/rewrite-suggestions")
async def rewrite_suggestions():
    """Placeholder — rewrite suggestion queue not yet implemented."""
    return {"status": "success", "output": "No pending suggestions."}

@app.post("/perform-rewrites")
async def perform_rewrites(req: RewriteApproval):
    """Placeholder — rewrite approval flow not yet implemented."""
    return {"status": "success", "output": "Rewrite logic not yet wired."}

# — ENTRY POINT —

if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 10000))
    logger.info(f"Starting server on port {port}")
    uvicorn.run(app, host="0.0.0.0", port=port)
