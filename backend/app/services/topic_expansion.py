"""
Topic expansion via embeddings.

Expands selected topics to include semantically similar ones (e.g., Machine Learning → AI)
using FastEmbed. Used to broaden lab filtering when topic filter is applied.
"""
import os
from typing import Any

from app.services.embeddings import get_embeddings

TOPIC_SIMILARITY_THRESHOLD = float(os.getenv("TOPIC_SIMILARITY_THRESHOLD", "0.7"))

_topic_embeddings_cache: dict[Any, dict[str, list[float]]] = {}


def _cosine_similarity(a: list[float], b: list[float]) -> float:
    """Cosine similarity for (assumed normalized) vectors. Dot product = cos sim if normalized."""
    return sum(x * y for x, y in zip(a, b))


async def get_topic_embeddings(topics: list[str]) -> dict[str, list[float]]:
    """
    Embed topics and cache by topic set. Returns {topic: embedding}.
    Cache key is frozenset of topics; cache invalidated when topic list changes.
    """
    key = frozenset(topics)
    if key not in _topic_embeddings_cache:
        if not topics:
            _topic_embeddings_cache[key] = {}
        else:
            embeddings = await get_embeddings(topics)
            _topic_embeddings_cache[key] = dict(zip(topics, embeddings))
    return _topic_embeddings_cache[key]


async def expand_topics_by_similarity(
    selected: list[str],
    all_topics: list[str],
    threshold: float | None = None,
) -> list[str]:
    """
    Expand selected topics to include semantically similar ones from all_topics.
    Returns union of selected + topics with cosine similarity >= threshold.
    """
    if not selected:
        return []
    threshold = threshold if threshold is not None else TOPIC_SIMILARITY_THRESHOLD
    topics_to_embed = list(dict.fromkeys(selected + all_topics))
    topic_embeddings = await get_topic_embeddings(topics_to_embed)
    expanded: set[str] = set(selected)
    for sel in selected:
        sel_emb = topic_embeddings.get(sel)
        if sel_emb is None:
            continue
        for other in all_topics:
            if other in expanded:
                continue
            other_emb = topic_embeddings.get(other)
            if other_emb is None:
                continue
            sim = _cosine_similarity(sel_emb, other_emb)
            if sim >= threshold:
                expanded.add(other)
    return list(expanded)
