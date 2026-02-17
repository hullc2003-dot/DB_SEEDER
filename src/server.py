from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from fastapi.middleware.cors import CORSMiddleware
import logging
import sys
import os

# --- PATH CONFIGURATION ---
# Keeps path logic intact but removes dependency on missing internal folders
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
if BASE_DIR not in sys.path:
    sys.path.append(BASE_DIR)

# --- INITIALIZE FASTAPI & LOGGING ---
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("RenderServer")

app = FastAPI(title="AI Brain API - Standalone Mode")

# Allow your dashboard to communicate with Render
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- SCHEMAS ---
class ChatRequest(BaseModel):
    input: str

class RewriteApproval(BaseModel):
    suggestion_id: str
    approved: bool = True

# --- ENDPOINTS ---

@app.get("/")
async def root():
    """Endpoint for basic browser verification."""
    return {
        "status": "online", 
        "mode": "Standalone / Unhooked",
        "agent": "Dale"
    }

@app.get("/health")
async def health():
    """Status polling endpoint for the dashboard light."""
    return {
        "status": "online",
        "kill_switch_active": False
    }

@app.post("/wake")
async def wake_up():
    """Wakes up the Render instance from sleep."""
    return {"status": "waking", "message": "Backend session refreshed."}

@app.post("/chat")
async def chat(req: ChatRequest):
    """Primary messaging interface - Unhooked from orchestrator."""
    try:
        # Placeholder response to prevent UI from breaking
        return {"output": f"Echo: {req.input}. (Orchestrator unhooked)"}
    except Exception as e:
        logger.error(f"Chat Error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/run-learning")
async def run_learning_endpoint():
    """Unhooked from LearningLayer."""
    try:
        return {
            "status": "success", 
            "summary": "Learning loop is currently in standalone mode.",
            "manifest": []
        }
    except Exception as e:
        logger.error(f"Learning Loop Error: {e}")
        return {"status": "error", "message": str(e)}

@app.get("/rewrite-suggestions")
async def rewrite_suggestions_endpoint():
    """Unhooked from rewrites.py."""
    return {"status": "success", "output": "No pending suggestions in standalone mode."}

@app.post("/perform-rewrites")
async def perform_rewrites_endpoint(req: RewriteApproval):
    """Unhooked from rewrites.py execution."""
    return {"status": "success", "output": "Rewrite logic bypassed."}

if __name__ == "__main__":
    import uvicorn
    # Use standard Render port logic
    port = int(os.getenv("PORT", 10000))
    uvicorn.run(app, host="0.0.0.0", port=port)
