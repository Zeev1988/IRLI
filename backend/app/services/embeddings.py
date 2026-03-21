"""
Embedding service using FastEmbed.

Local-only for now; may add OpenAI migration path later.
Model and dimension are configurable via EMBEDDING_MODEL and EMBEDDING_DIM.
"""
import asyncio
import os
from typing import List

from fastembed import TextEmbedding

EMBEDDING_DIM = int(os.getenv("EMBEDDING_DIM", "1024"))
EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "BAAI/bge-large-en-v1.5")

_fastembed_model: TextEmbedding | None = None


def _get_model() -> TextEmbedding:
    global _fastembed_model
    if _fastembed_model is None:
        _fastembed_model = TextEmbedding(model_name=EMBEDDING_MODEL)
    return _fastembed_model


def _embed_sync(texts: List[str]) -> List[List[float]]:
    return [list(emb) for emb in _get_model().embed(texts)]


async def get_embeddings(texts: List[str]) -> List[List[float]]:
    """Embed texts in a thread so the event loop is not blocked."""
    return await asyncio.to_thread(_embed_sync, texts)


async def get_embedding(text: str) -> List[float]:
    """Embed a single string."""
    results = await get_embeddings([text])
    return results[0]
