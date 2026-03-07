"""
Job queue client for enqueueing and polling background jobs.

Uses Arq (Redis-backed). When REDIS_URL is not set, jobs run synchronously.
"""
import logging
import os
from typing import Any

from arq import create_pool
from arq.connections import ArqRedis, RedisSettings
from arq.jobs import Job, JobStatus

logger = logging.getLogger(__name__)

REDIS_URL = os.getenv("REDIS_URL")
_redis_pool: ArqRedis | None = None


def _redis_settings() -> RedisSettings | None:
    if not REDIS_URL:
        return None
    return RedisSettings.from_dsn(REDIS_URL)


def use_queue() -> bool:
    """True if Redis is configured and jobs should be queued."""
    return REDIS_URL is not None and REDIS_URL.strip() != ""


async def get_redis_pool() -> ArqRedis | None:
    """Get or create the Arq Redis pool. Returns None if Redis not configured."""
    global _redis_pool
    if _redis_pool is not None:
        return _redis_pool
    settings = _redis_settings()
    if not settings:
        return None
    try:
        _redis_pool = await create_pool(settings)
        return _redis_pool
    except Exception:
        logger.exception("Failed to connect to Redis")
        return None


async def enqueue_ingest(index_url: str) -> str | None:
    """
    Enqueue an ingest job. Returns job_id if queued, None if queue unavailable.
    """
    redis = await get_redis_pool()
    if not redis:
        return None
    job = await redis.enqueue_job("ingest_task", index_url)
    return job.job_id if job else None


async def enqueue_enrich(limit: int | None = None) -> str | None:
    """
    Enqueue an enrich job. Returns job_id if queued, None if queue unavailable.
    """
    redis = await get_redis_pool()
    if not redis:
        return None
    job = await redis.enqueue_job("enrich_task", limit)
    return job.job_id if job else None


async def get_job_status(job_id: str) -> dict[str, Any] | None:
    """
    Get job status and result. Returns None if job not found or Redis unavailable.
    """
    redis = await get_redis_pool()
    if not redis:
        return None
    job = Job(job_id, redis)
    try:
        status = await job.status()
    except Exception:
        logger.debug("Job %s status check failed", job_id)
        return None

    result: dict[str, Any] = {
        "job_id": job_id,
        "status": status.name if hasattr(status, "name") else str(status),
    }

    if status == JobStatus.complete:
        try:
            result_info = await job.result_info()
            if result_info and result_info.result is not None:
                result["result"] = result_info.result
        except Exception:
            pass
    elif status == JobStatus.deferred:
        result["status"] = "queued"
    elif status == JobStatus.in_progress:
        result["status"] = "processing"
    elif status == JobStatus.not_found:
        return None

    return result


async def close_redis_pool() -> None:
    """Close the Redis pool (call on app shutdown)."""
    global _redis_pool
    if _redis_pool:
        await _redis_pool.close()
        _redis_pool = None
