"""
Ingestion pipeline.

Given a faculty index URL:
  1. Discover all individual lab/researcher URLs (discoverer)
  2. For each URL: crawl → extract LabProfile → generate embedding
  3. Upsert into PostgreSQL

Concurrency is capped by a semaphore to avoid hammering the LLM API.
"""
import asyncio
import logging
import os
from datetime import datetime, timezone

from openai import AsyncOpenAI
from sqlalchemy.dialects.postgresql import insert as pg_insert
from tenacity import AsyncRetrying, retry_if_exception_type, stop_after_attempt, wait_exponential

from sqlalchemy import select

from app.config import DEBUG_MODE
from app.db.database import AsyncSessionLocal
from app.db.models import IngestionLogORM, LabProfileORM
from app.models.lab import LabProfile
from app.services.discoverer import discover_lab_urls
from app.services.extractor import extract_lab_data
from app.services.lab_crawler import crawl_lab_with_nested
from app.services.metrics_enricher import enrich_all_labs

logger = logging.getLogger(__name__)

_CONCURRENCY_LIMIT = int(os.getenv("INGEST_CONCURRENCY", "5"))

# ---------------------------------------------------------------------------
# Embedding
# ---------------------------------------------------------------------------
_embed_client: AsyncOpenAI | None = None


def _get_embed_client() -> AsyncOpenAI:
    global _embed_client
    if _embed_client is None:
        _embed_client = AsyncOpenAI(api_key=os.environ["OPENAI_API_KEY"])
    return _embed_client


def _embedding_content(profile: LabProfile) -> tuple[tuple[str, ...], tuple[str, ...], tuple[str, ...]]:
    """Content used for embedding — used to detect changes."""
    return (
        tuple(profile.research_summary),
        tuple(profile.keywords),
        tuple(profile.technologies),
    )


async def _get_existing_embedding_if_unchanged(
    lab_url: str, profile: LabProfile
) -> list[float] | None:
    """Return existing embedding if profile content is unchanged; else None."""
    async with AsyncSessionLocal() as session:
        row = (
            await session.execute(
                select(
                    LabProfileORM.embedding,
                    LabProfileORM.research_summary,
                    LabProfileORM.keywords,
                    LabProfileORM.technologies,
                ).where(LabProfileORM.lab_url == lab_url)
            )
        ).first()
    if not row or row.embedding is None:
        return None
    existing = (tuple(row.research_summary or []), tuple(row.keywords or []), tuple(row.technologies or []))
    if existing != _embedding_content(profile):
        return None
    return row.embedding


async def _embed(profile: LabProfile) -> list[float] | None:
    """Generate a 1536-dim embedding from the lab's summary + keywords."""
    if DEBUG_MODE:
        # Return a zero vector in debug mode so the DB upsert still works
        return [0.0] * 1536

    text_to_embed = (
        " ".join(profile.research_summary)
        + " "
        + " ".join(profile.keywords)
        + " "
        + " ".join(profile.technologies)
    )

    try:
        async for attempt in AsyncRetrying(
            retry=retry_if_exception_type(Exception),
            stop=stop_after_attempt(3),
            wait=wait_exponential(multiplier=1, min=1, max=60),
            reraise=True,
        ):
            with attempt:
                response = await _get_embed_client().embeddings.create(
                    model="text-embedding-3-small",
                    input=text_to_embed,
                )
                return response.data[0].embedding
    except Exception:
        logger.exception("Embedding failed for %s — storing without embedding", profile.pi_name)
        return [0.0] * 1536


# ---------------------------------------------------------------------------
# Upsert
# ---------------------------------------------------------------------------
async def _upsert(
    profile: LabProfile,
    embedding: list[float] | None,
    metrics: dict | None = None,
) -> None:
    """Insert or update a lab profile row, keyed on lab_url."""
    row = {
        "pi_name": profile.pi_name,
        "institution": profile.institution,
        "faculty": profile.faculty,
        "research_summary": profile.research_summary,
        "keywords": profile.keywords,
        "technologies": profile.technologies,
        "representative_papers": profile.representative_papers,
        "hiring_status": str(profile.hiring_status),
        "lab_url": str(profile.lab_url),
        "embedding": embedding,
        "last_crawled_at": datetime.now(timezone.utc),
    }
    if metrics:
        row["publication_count"] = metrics.get("paperCount")
        row["citation_count"] = metrics.get("citationCount")
        row["h_index"] = metrics.get("hIndex")
        row["semantic_scholar_author_id"] = metrics.get("authorId")
        row["metrics_updated_at"] = datetime.now(timezone.utc)

    stmt = (
        pg_insert(LabProfileORM)
        .values(**row)
        .on_conflict_do_update(
            index_elements=["lab_url"],
            set_={k: v for k, v in row.items() if k != "lab_url"},
        )
    )

    async with AsyncSessionLocal() as session:
        await session.execute(stmt)
        await session.commit()


async def upsert_profile(
    profile: LabProfile,
    *,
    metrics: dict | None = None,
    generate_embedding: bool = True,
) -> None:
    """Upsert a single lab profile (e.g. from debug stub)."""
    if generate_embedding:
        existing = await _get_existing_embedding_if_unchanged(str(profile.lab_url), profile)
        embedding = existing if existing is not None else await _embed(profile)
    else:
        embedding = None
    await _upsert(profile, embedding, metrics=metrics)


# ---------------------------------------------------------------------------
# Per-lab processing
# ---------------------------------------------------------------------------
async def _process_lab(url: str, semaphore: asyncio.Semaphore) -> bool:
    """Crawl, extract, embed (only if content changed), and upsert a single lab."""
    async with semaphore:
        try:
            logger.info("Processing lab: %s", url)
            markdown = await crawl_lab_with_nested(url)
            profile = await extract_lab_data(markdown, url)
            existing = await _get_existing_embedding_if_unchanged(str(profile.lab_url), profile)
            embedding = existing if existing is not None else await _embed(profile)
            await _upsert(profile, embedding)
            logger.info("Upserted: %s (%s)", profile.pi_name, url)
            return True
        except Exception:
            logger.exception("Failed to process lab %s — skipping", url)
            return False


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------
async def ingest_faculty(index_url: str) -> dict[str, int]:
    """
    Run the full ingestion pipeline for one faculty index URL.

    Returns a summary dict with ``total``, ``success``, and ``failed`` counts.
    Logs to ingestion_logs for observability.
    """
    started_at = datetime.now(timezone.utc)
    log_id: int | None = None

    async with AsyncSessionLocal() as session:
        log = IngestionLogORM(
            index_url=index_url,
            started_at=started_at,
        )
        session.add(log)
        await session.commit()
        await session.refresh(log)
        log_id = log.id

    logger.info("Starting ingestion for faculty index: %s", index_url)
    try:
        lab_urls = await discover_lab_urls(index_url)
        logger.info("Found %d lab URLs to process", len(lab_urls))

        semaphore = asyncio.Semaphore(_CONCURRENCY_LIMIT)
        results = await asyncio.gather(
            *[_process_lab(url, semaphore) for url in lab_urls],
            return_exceptions=False,
        )

        success = sum(1 for r in results if r)
        failed = len(results) - success
        logger.info(
            "Ingestion complete for %s — %d/%d succeeded", index_url, success, len(results)
        )

        enrich_result = await enrich_all_labs(only_without_metrics=True)
        logger.info(
            "Enrichment: %d/%d labs updated with metrics",
            enrich_result["success"],
            enrich_result["total"],
        )

        if log_id is not None:
            async with AsyncSessionLocal() as session:
                log = await session.get(IngestionLogORM, log_id)
                if log:
                    log.finished_at = datetime.now(timezone.utc)
                    log.success_count = success
                    log.failed_count = failed
                    await session.commit()

        return {
            "total": len(results),
            "success": success,
            "failed": failed,
            "enriched": enrich_result["success"],
        }
    except Exception as exc:
        if log_id is not None:
            async with AsyncSessionLocal() as session:
                log = await session.get(IngestionLogORM, log_id)
                if log:
                    log.finished_at = datetime.now(timezone.utc)
                    log.error_message = str(exc)[:500]
                    await session.commit()
        raise
