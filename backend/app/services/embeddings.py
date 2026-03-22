import asyncio
import os
import logging
from pathlib import Path
from typing import List

logger = logging.getLogger(__name__)

# 1. Setup Persistent Cache Path
# Using the project root /cache folder
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
CACHE_DIR = PROJECT_ROOT / "cache" / "fastembed"
CACHE_DIR.mkdir(parents=True, exist_ok=True)

# Set the env var before importing TextEmbedding
os.environ["FASTEMBED_CACHE_PATH"] = str(CACHE_DIR)

from fastembed import TextEmbedding

EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "BAAI/bge-large-en-v1.5")
_fastembed_model: TextEmbedding | None = None

def _get_model() -> TextEmbedding:
    global _fastembed_model
    if _fastembed_model is None:
        logger.info(f"Initializing FastEmbed model: {EMBEDDING_MODEL} at {CACHE_DIR}")
        # Explicitly passing cache_dir here is redundant but serves as a fail-safe
        _fastembed_model = TextEmbedding(model_name=EMBEDDING_MODEL, cache_dir=str(CACHE_DIR))
    return _fastembed_model

def warm_model():
    """Call this during app startup to prevent timeouts on the first request."""
    _get_model()

def _embed_sync(texts: List[str]) -> List[List[float]]:
    # convert generator to list of lists
    return [list(emb) for emb in _get_model().embed(texts)]

async def get_embeddings(texts: List[str]) -> List[List[float]]:
    if not texts:
        return []
    return await asyncio.to_thread(_embed_sync, texts)

async def get_embedding(text: str) -> List[float]:
    results = await get_embeddings([text])
    return results[0]