# trainer.py
import asyncio
import numpy as np
import logging
from memory import get_supabase_client
from embedder import embed_packages
from normalizer import ModelDataPipeline

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("Trainer")

async def train_brain():
    logger.info("Fetching raw knowledge from Supabase...")
    supabase = get_supabase_client()
    
    # 1. Fetch data (e.g., last 1000 items)
    response = supabase.table("atomic_facts").select("content, rank_score").limit(1000).execute()
    data = response.data
    
    if not data:
        logger.error("No data found in Supabase to train on.")
        return

    # 2. Prepare Data
    # In a real scenario, you might not re-embed if you stored vectors in DB.
    # But assuming we calculate fresh embeddings:
    logger.info("Generating embeddings for training set...")
    processed_data = await embed_packages(data)
    
    # Extract Vectors (X) and Scores (y)
    # Ensure we filter out items where embedding failed
    valid_items = [d for d in processed_data if d.get("embedding")]
    
    if not valid_items:
        logger.error("No valid embeddings generated.")
        return

    X = np.array([item["embedding"] for item in valid_items])
    y = np.array([item["rank_score"] for item in valid_items])

    # 3. Initialize & Run Pipeline
    pipeline = ModelDataPipeline(scaler_type="minmax", artifact_dir="./model_artifacts")
    
    # Split
    X_train, X_test, y_train, y_test = pipeline.split_data(X, y)
    
    # Fit & Save (This creates the scaler.joblib file)
    X_train_scaled = pipeline.fit_transform_train(X_train)
    
    logger.info(f"Training complete. Artifacts saved to ./model_artifacts")
    logger.info(f"Data shape: {X_train_scaled.shape}")

if __name__ == "__main__":
    asyncio.run(train_brain())
