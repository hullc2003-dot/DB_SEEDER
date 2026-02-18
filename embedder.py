import logging
from typing import List, Dict, Any, Optional
import numpy as np
from sentence_transformers import SentenceTransformer

# — CONFIGURATION —
# "all-mpnet-base-v2" is the standard for high-quality local RAG.
# It outputs 768-dimensional vectors.
MODEL_NAME = "all-mpnet-base-v2"
DEVICE = "cpu"  # Change to "cuda" if you have an NVIDIA GPU, or "mps" for Mac M1/M2/M3

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("LocalEmbedder")

class LocalEmbedder:
    _instance = None

    def __new__(cls):
        """Singleton pattern to ensure model is loaded only once."""
        if cls._instance is None:
            cls._instance = super(LocalEmbedder, cls).__new__(cls)
            logger.info(f"Loading local model '{MODEL_NAME}' on {DEVICE}...")
            try:
                cls._instance.model = SentenceTransformer(MODEL_NAME, device=DEVICE)
                logger.info("Model loaded successfully.")
            except Exception as e:
                logger.critical(f"Failed to load model: {e}")
                raise RuntimeError("Could not load local embedding model.")
        return cls._instance

    def embed_text(self, text: str) -> List[float]:
        """
        Generate a vector embedding for a single string.
        """
        try:
            # Clean text (basic whitespace removal)
            clean_text = text.strip().replace("\n", " ")
            if not clean_text:
                return []

            # Generate embedding
            # normalize_embeddings=True helps with cosine similarity later
            embedding = self.model.encode(clean_text, normalize_embeddings=True)
            
            return embedding.tolist()
        except Exception as e:
            logger.error(f"Failed to embed text: {e}")
            return []

    def embed_batch(self, texts: List[str]) -> List[List[float]]:
        """
        Embed a list of strings efficiently using batch processing.
        Much faster than looping manually.
        """
        if not texts:
            return []
        
        try:
            # Preprocessing
            clean_texts = [t.strip().replace("\n", " ") for t in texts]
            
            # Inference
            embeddings = self.model.encode(
                clean_texts, 
                batch_size=32, 
                show_progress_bar=True, 
                normalize_embeddings=True
            )
            return embeddings.tolist()
        except Exception as e:
            logger.error(f"Batch embedding failed: {e}")
            return []

# — PUBLIC API FUNCTIONS —
# These functions match the signature expected by your orchestrator.py

_embedder_instance = LocalEmbedder()

async def embed_text(text: str) -> List[float]:
    """
    Async wrapper for single text embedding.
    Note: Local ML is CPU bound, so async here just ensures compatibility 
    with your existing pipeline, it doesn't make the CPU calculation async.
    """
    return _embedder_instance.embed_text(text)

async def embed_packages(packages: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Takes a list of package dictionaries, extracts content, 
    generates embeddings in batch, and attaches them.
    """
    if not packages:
        logger.warning("embed_packages called with empty list")
        return packages

    logger.info(f"Embedding {len(packages)} packages locally...")

    # 1. Extract content to embed
    # We maintain index mapping to ensure empty content doesn't break alignment
    indices_to_embed = []
    texts_to_embed = []

    for i, pkg in enumerate(packages):
        content = pkg.get("content", "")
        if content and content.strip():
            indices_to_embed.append(i)
            texts_to_embed.append(content)
        else:
            pkg["embedding"] = None # Handle empty packages

    # 2. Run Batch Embedding
    if texts_to_embed:
        vectors = _embedder_instance.embed_batch(texts_to_embed)
        
        # 3. Re-attach vectors to original packages
        for idx, vector in zip(indices_to_embed, vectors):
            packages[idx]["embedding"] = vector
            
    logger.info(f"Successfully embedded {len(texts_to_embed)} items.")
    return packages

if __name__ == "__main__":
    # Simple test
    test_text = "This is a test of the local embedding system."
    vector = _embedder_instance.embed_text(test_text)
    print(f"Generated vector length: {len(vector)}")
    print(f"First 5 dimensions: {vector[:5]}")
