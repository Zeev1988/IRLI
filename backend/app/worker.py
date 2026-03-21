"""
Arq worker for background ingestion and enrichment jobs.

Run with: arq app.worker.WorkerSettings
"""
import logging
import os

from arq.connections import RedisSettings
from arq.worker import func

from app.services.ingestion import ingest_faculty
from app.services.metrics_enricher import enrich_all_labs

logger = logging.getLogger(__name__)

REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379")


def _redis_settings() -> RedisSettings:
    return RedisSettings.from_dsn(REDIS_URL or "redis://localhost:6379")


async def ingest_task(ctx: dict, index_url: str) -> dict:
    """Background task: ingest faculty index URL."""
    logger.info("Worker: starting ingest for %s", index_url)
    result = await ingest_faculty(index_url)
    logger.info("Worker: ingest complete for %s: %s", index_url, result)
    return result


async def enrich_task(ctx: dict, limit: int | None = None) -> dict:
    """Background task: enrich labs with OpenAlex metrics."""
    logger.info("Worker: starting enrich (limit=%s)", limit)
    result = await enrich_all_labs(limit=limit, only_without_metrics=False)
    logger.info("Worker: enrich complete: %s", result)
    return result


class WorkerSettings:
    functions = [
        func(ingest_task, keep_result=86400),
        func(enrich_task, keep_result=86400),
    ]
    redis_settings = _redis_settings()
