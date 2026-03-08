"""
Enrich lab profiles with publication metrics from Semantic Scholar API.

Fetches publication_count, citation_count, h_index for each lab's PI
by searching Semantic Scholar and matching by name + institution.
Uses "Known Paper" strategy when representative_papers are available.

Semantic Scholar: 100 req / 5 min. We use ~3s delay between calls to stay under limit.
"""
import asyncio
import logging
import os
import re
from datetime import datetime, timezone
import httpx
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession
from tenacity import (
    AsyncRetrying,
    retry_if_exception_type,
    retry_if_result,
    stop_after_attempt,
)

from app.config import DEBUG_MODE
from app.db.database import AsyncSessionLocal
from app.db.models import LabProfileORM

logger = logging.getLogger(__name__)
S2_API_BASE = "https://api.semanticscholar.org/graph/v1"
# 100 req / 5 min ≈ 1 req every 3s; use 3s to stay under limit
_RATE_LIMIT_DELAY = float(os.getenv("S2_RATE_LIMIT_DELAY", "3"))
# Batch endpoint accepts up to 1000; use 100 per request to stay under rate limits
_S2_BATCH_CHUNK_SIZE = 100

_s2_client: httpx.AsyncClient | None = None


def _get_s2_client() -> httpx.AsyncClient:
    """Reuse a single httpx client for connection pooling."""
    global _s2_client
    if _s2_client is None:
        _s2_client = httpx.AsyncClient(timeout=10.0)
    return _s2_client


def _s2_should_retry(result: httpx.Response) -> bool:
    """Retry on 429 (rate limit) or 5xx (server error)."""
    return result.status_code == 429 or result.status_code >= 500


def _s2_wait(retry_state) -> float:
    """Use Retry-After for 429; exponential backoff for 5xx/exceptions."""
    if retry_state.outcome and not retry_state.outcome.failed:
        resp = retry_state.outcome.result()
        if resp.status_code == 429:
            try:
                return float(resp.headers.get("Retry-After", "60"))
            except ValueError:
                return 60.0
    return min(60.0, 2**retry_state.attempt_number)


async def _s2_get(url: str, params: dict | None = None) -> httpx.Response:
    """
    GET with tenacity retry: 429 → Retry-After; 5xx/exception → exponential backoff.
    """
    client = _get_s2_client()

    async for attempt in AsyncRetrying(
        retry=retry_if_exception_type(Exception) | retry_if_result(_s2_should_retry),
        stop=stop_after_attempt(3),
        wait=_s2_wait,
        reraise=True,
    ):
        with attempt:
            resp = await client.get(url, params=params or {})
            if resp.status_code == 429:
                logger.warning("S2 rate limited (429), waiting Retry-After")
            elif resp.status_code >= 500:
                logger.warning("S2 %s, retry %d/3", resp.status_code, attempt.retry_state.attempt_number)
            return resp


async def _s2_post(url: str, json_body: dict, params: dict | None = None) -> httpx.Response:
    """POST with tenacity retry for batch endpoint."""
    client = _get_s2_client()
    async for attempt in AsyncRetrying(
        retry=retry_if_exception_type(Exception) | retry_if_result(_s2_should_retry),
        stop=stop_after_attempt(3),
        wait=_s2_wait,
        reraise=True,
    ):
        with attempt:
            resp = await client.post(url, json=json_body, params=params or {})
            if resp.status_code == 429:
                logger.warning("S2 rate limited (429), waiting Retry-After")
            elif resp.status_code >= 500:
                logger.warning("S2 %s, retry %d/3", resp.status_code, attempt.retry_state.attempt_number)
            return resp


async def _fetch_authors_batch(author_ids: list[str]) -> dict[str, dict]:
    """
    Fetch metrics for multiple authors via POST /author/batch.
    Returns {author_id: {paperCount, citationCount, hIndex}} for authors found.
    """
    if not author_ids:
        return {}
    url = f"{S2_API_BASE}/author/batch"
    params = {"fields": "paperCount,citationCount,hIndex"}
    try:
        resp = await _s2_post(url, {"ids": author_ids}, params=params)
    except Exception:
        logger.exception("S2 batch fetch failed for %d authors", len(author_ids))
        return {}
    if resp.status_code != 200:
        logger.warning("S2 batch: %s", resp.status_code)
        return {}
    data = resp.json()
    result: dict[str, dict] = {}
    for i, author_id in enumerate(author_ids):
        if i < len(data) and data[i] is not None:
            author = data[i]
            metrics = {
                "paperCount": author.get("paperCount"),
                "citationCount": author.get("citationCount"),
                "hIndex": author.get("hIndex"),
            }
            if any(v is not None for v in metrics.values()):
                result[author_id] = metrics
    return result


async def fetch_author_metrics(author_id: str) -> dict | None:
    """
    Fetch paperCount, citationCount, hIndex for an author from Semantic Scholar.
    Public for testing; use _fetch_author_metrics alias internally.
    """
    url = f"{S2_API_BASE}/author/{author_id}"
    params = {"fields": "paperCount,citationCount,hIndex"}
    try:
        resp = await _s2_get(url, params=params)
        if resp.status_code != 200:
            logger.warning("S2 author %s: %s", author_id, resp.status_code)
            return None
        data = resp.json()
        return {
            "paperCount": data.get("paperCount"),
            "citationCount": data.get("citationCount"),
            "hIndex": data.get("hIndex"),
        }
    except Exception:
        logger.exception("S2 fetch failed for author %s", author_id)
        return None


async def _fetch_author_metrics(author_id: str) -> dict | None:
    """Alias for fetch_author_metrics."""
    return await fetch_author_metrics(author_id)


def _author_matches_institution(author: dict, institution: str) -> bool:
    """Check if author's affiliations contain the institution (or no filter)."""
    if not institution or not institution.strip():
        return True
    affiliations = author.get("affiliations") or []
    inst_lower = institution.lower()
    return any(inst_lower in (aff or "").lower() for aff in affiliations)


def _name_matches(pi_name: str, author_name: str) -> bool:
    """
    Checks if a PI name matches an author name from a publication.
    Handles: Titles, Initials (J.R. Smith), Hyphenated names, and Last Name First formats.
    """
    def tokenize(s: str):
        if not s: return []
        # Remove titles
        s = re.sub(r"^(dr\.?|prof\.?|professor|phd|m\.d\.?)\s+", "", s, flags=re.I).strip().lower()
        # Remove punctuation except hyphens inside names
        s = re.sub(r"[^\w\s-]", " ", s)
        return s.split()

    pi_tokens = tokenize(pi_name)
    auth_tokens = tokenize(author_name)

    if not pi_tokens or not auth_tokens:
        return False

    # 1. Exact match (normalized)
    if pi_tokens == auth_tokens:
        return True

    # 2. Extract Last Names (Assume last token is the primary surname)
    pi_last = pi_tokens[-1]
    auth_last = auth_tokens[-1]
    
    # Handle "Last, First" format by checking if the first author token matches PI last
    if pi_last != auth_last and pi_tokens[0] != auth_tokens[0]:
        # If the last names don't match at all, they likely aren't the same person
        if pi_last not in auth_tokens and auth_last not in pi_tokens:
            return False

    # 3. Component Matching Logic
    # We want to ensure the "Last Name" exists in both, 
    # and the "First Name" is either a full match or a matching initial.
    
    def get_initials(tokens):
        return [t[0] for t in tokens if t]

    # Check if the primary surname is present in both
    if pi_last in auth_tokens:
        pi_first_initial = pi_tokens[0][0]
        # Find the index of the PI's last name in the author's list
        try:
            auth_idx = auth_tokens.index(pi_last)
            other_auth_tokens = auth_tokens[:auth_idx] + auth_tokens[auth_idx+1:]
            if any(t.startswith(pi_first_initial) for t in other_auth_tokens):
                return True
        except ValueError:
            pass

    return False


async def _resolve_author_id_for_lab(lab_id: int, session: AsyncSession) -> str | None:
    """
    Resolve Semantic Scholar author_id for a lab via paper search or author search.
    Returns author_id or None. Does not fetch metrics.
    """
    result = await session.execute(select(LabProfileORM).where(LabProfileORM.id == lab_id))
    row = result.scalar_one_or_none()
    if not row:
        return None

    representative_papers = getattr(row, "representative_papers", None) or []
    if representative_papers:
        for paper_title in representative_papers[:5]:
            author_id = await _find_author_via_paper_search(paper_title, row.pi_name)
            if author_id:
                return author_id
            await asyncio.sleep(_RATE_LIMIT_DELAY)

    search_url = f"{S2_API_BASE}/author/search"
    params = {
        "query": row.pi_name,
        "fields": "authorId,name,affiliations,paperCount,citationCount,hIndex",
    }
    try:
        resp = await _s2_get(search_url, params=params)
    except Exception:
        logger.exception("S2 search failed for lab %d", lab_id)
        return None
    if resp.status_code != 200:
        return None
    authors = resp.json().get("data") or []
    for author in authors:
        if _author_matches_institution(author, row.institution or ""):
            author_id = author.get("authorId")
            if author_id:
                return author_id
    return None


async def _find_author_via_paper_search(
    paper_title: str, pi_name: str
) -> str | None:
    """
    Search for a paper by title; if found, return authorId of author matching pi_name.
    Uses the "Known Paper" strategy for disambiguation when affiliations are missing.
    """
    url = f"{S2_API_BASE}/paper/search"
    params = {"query": paper_title, "limit": 5, "fields": "title,authors"}
    try:
        resp = await _s2_get(url, params=params)
    except Exception:
        logger.exception("S2 paper search failed for %r", paper_title)
        return None
    if resp.status_code != 200:
        return None
    papers = resp.json().get("data") or []
    for paper in papers:
        for author in paper.get("authors") or []:
            if _name_matches(pi_name, author.get("name")):
                return author.get("authorId")
    return None


async def search_and_fetch_metrics(
    pi_name: str,
    institution: str,
    representative_papers: list[str] | None = None,
) -> dict | None:
    """
    Search Semantic Scholar for author by name (name-only for higher recall),
    filter by institution in affiliations, return metrics from search or fetch.
    When representative_papers is provided, tries Known Paper strategy first.
    Returns metrics dict (with optional authorId) or None. No DB. For testing.
    """
    # Known Paper strategy when representative_papers available
    if representative_papers:
        for paper_title in representative_papers[:5]:
            author_id = await _find_author_via_paper_search(paper_title, pi_name)
            if author_id:
                await asyncio.sleep(_RATE_LIMIT_DELAY)
                metrics = await _fetch_author_metrics(author_id)
                if metrics:
                    metrics["authorId"] = author_id
                    return metrics
            await asyncio.sleep(_RATE_LIMIT_DELAY)

    search_url = f"{S2_API_BASE}/author/search"
    params = {
        "query": pi_name,
        "fields": "authorId,name,affiliations,paperCount,citationCount,hIndex",
    }
    try:
        resp = await _s2_get(search_url, params=params)
    except Exception:
        logger.exception("S2 search failed for %s", pi_name)
        return None
    if resp.status_code != 200:
        logger.warning("S2 search for %s: %s", pi_name, resp.status_code)
        return None
    authors = resp.json().get("data") or []
    for author in authors:
        if _author_matches_institution(author, institution):
            metrics = {
                "paperCount": author.get("paperCount"),
                "citationCount": author.get("citationCount"),
                "hIndex": author.get("hIndex"),
            }
            if any(v is not None for v in metrics.values()):
                metrics["authorId"] = author.get("authorId")
                return metrics
            author_id = author.get("authorId")
            if author_id:
                await asyncio.sleep(_RATE_LIMIT_DELAY)
                fetched = await fetch_author_metrics(author_id)
                if fetched:
                    fetched["authorId"] = author_id
                    return fetched
    logger.debug("No S2 match for %s (institution: %s)", pi_name, institution)
    return None


async def enrich_lab_metrics(lab_id: int, session: AsyncSession) -> bool:
    """
    Fetch metrics for one lab and update the DB.
    Returns True on success.
    """
    result = await session.execute(select(LabProfileORM).where(LabProfileORM.id == lab_id))
    row = result.scalar_one_or_none()
    if not row:
        return False

    if DEBUG_MODE:
        await session.execute(
            update(LabProfileORM)
            .where(LabProfileORM.id == lab_id)
            .values(
                publication_count=0,
                citation_count=0,
                h_index=0,
                semantic_scholar_author_id=None,
                metrics_updated_at=datetime.now(timezone.utc),
            )
        )
        await session.commit()
        logger.info("[DEBUG MODE] Stub metrics for lab %d", lab_id)
        return True

    author_id = None
    metrics = None
    representative_papers = getattr(row, "representative_papers", None) or []

    # Known Paper strategy: search by paper title first when we have representative papers
    if representative_papers:
        for paper_title in representative_papers[:5]:  # limit to 5 to avoid rate limits
            author_id = await _find_author_via_paper_search(paper_title, row.pi_name)
            if author_id:
                await asyncio.sleep(_RATE_LIMIT_DELAY)
                metrics = await _fetch_author_metrics(author_id)
                if metrics:
                    logger.debug(
                        "Lab %d: matched via paper %r", lab_id, paper_title[:50]
                    )
                    break
            await asyncio.sleep(_RATE_LIMIT_DELAY)

    # Fallback: author search by name (filter by institution when affiliations present)
    if not metrics or not author_id:
        search_url = f"{S2_API_BASE}/author/search"
        params = {
            "query": row.pi_name,
            "fields": "authorId,name,affiliations,paperCount,citationCount,hIndex",
        }
        try:
            resp = await _s2_get(search_url, params=params)
        except Exception:
            logger.exception("S2 search failed for lab %d", lab_id)
            return False
        if resp.status_code != 200:
            logger.warning("S2 search for lab %d: %s", lab_id, resp.status_code)
            return False
        authors = resp.json().get("data") or []
        for author in authors:
            if _author_matches_institution(author, row.institution or ""):
                if author.get("paperCount") is not None or author.get("citationCount") is not None:
                    metrics = {
                        "paperCount": author.get("paperCount"),
                        "citationCount": author.get("citationCount"),
                        "hIndex": author.get("hIndex"),
                    }
                    author_id = author.get("authorId")
                    break
                author_id = author.get("authorId")
                if author_id:
                    await asyncio.sleep(_RATE_LIMIT_DELAY)
                    metrics = await _fetch_author_metrics(author_id)
                    if metrics:
                        break

    if not metrics or not author_id:
        logger.debug("No S2 match for lab %d (%s)", lab_id, row.pi_name)
        return False

    await session.execute(
        update(LabProfileORM)
        .where(LabProfileORM.id == lab_id)
        .values(
            publication_count=metrics.get("paperCount"),
            citation_count=metrics.get("citationCount"),
            h_index=metrics.get("hIndex"),
            semantic_scholar_author_id=author_id,
            metrics_updated_at=datetime.now(timezone.utc),
        )
    )
    await session.commit()
    logger.info(
        "Enriched lab %d: %d papers, %d citations, h=%s",
        lab_id,
        metrics.get("paperCount") or 0,
        metrics.get("citationCount") or 0,
        metrics.get("hIndex"),
    )
    return True


async def enrich_all_labs(
    limit: int | None = None,
    only_without_metrics: bool = False,
) -> dict[str, int]:
    """
    Enrich labs with metrics from Semantic Scholar.
    Uses POST /author/batch to reduce API calls. Returns {"total", "success", "failed"}.

    Args:
        limit: Max labs to process (None = all).
        only_without_metrics: If True, only enrich labs where publication_count IS NULL.
    """
    if DEBUG_MODE:
        async with AsyncSessionLocal() as session:
            stmt = select(LabProfileORM.id).order_by(LabProfileORM.id)
            if only_without_metrics:
                stmt = stmt.where(LabProfileORM.publication_count.is_(None))
            if limit:
                stmt = stmt.limit(limit)
            result = await session.execute(stmt)
            lab_ids = [r[0] for r in result.all()]
        for lab_id in lab_ids:
            async with AsyncSessionLocal() as session:
                await enrich_lab_metrics(lab_id, session)
        return {"total": len(lab_ids), "success": len(lab_ids), "failed": 0}

    async with AsyncSessionLocal() as session:
        stmt = select(LabProfileORM.id).order_by(LabProfileORM.id)
        if only_without_metrics:
            stmt = stmt.where(LabProfileORM.publication_count.is_(None))
        if limit:
            stmt = stmt.limit(limit)
        result = await session.execute(stmt)
        lab_ids = [r[0] for r in result.all()]

    lab_to_author: dict[int, str] = {}
    for lab_id in lab_ids:
        async with AsyncSessionLocal() as session:
            author_id = await _resolve_author_id_for_lab(lab_id, session)
            if author_id:
                lab_to_author[lab_id] = author_id
        await asyncio.sleep(_RATE_LIMIT_DELAY)

    all_author_ids = list(lab_to_author.values())
    author_metrics: dict[str, dict] = {}
    for i in range(0, len(all_author_ids), _S2_BATCH_CHUNK_SIZE):
        chunk = all_author_ids[i : i + _S2_BATCH_CHUNK_SIZE]
        batch = await _fetch_authors_batch(chunk)
        author_metrics.update(batch)
        if i + _S2_BATCH_CHUNK_SIZE < len(all_author_ids):
            await asyncio.sleep(_RATE_LIMIT_DELAY)

    success = 0
    for lab_id, author_id in lab_to_author.items():
        metrics = author_metrics.get(author_id)
        if not metrics:
            continue
        async with AsyncSessionLocal() as session:
            await session.execute(
                update(LabProfileORM)
                .where(LabProfileORM.id == lab_id)
                .values(
                    publication_count=metrics.get("paperCount"),
                    citation_count=metrics.get("citationCount"),
                    h_index=metrics.get("hIndex"),
                    semantic_scholar_author_id=author_id,
                    metrics_updated_at=datetime.now(timezone.utc),
                )
            )
            await session.commit()
            success += 1
        logger.debug(
            "Enriched lab %d: %s papers, %s citations",
            lab_id,
            metrics.get("paperCount"),
            metrics.get("citationCount"),
        )

    failed = len(lab_ids) - success
    logger.info("Enrichment complete: %d/%d succeeded", success, len(lab_ids))
    return {"total": len(lab_ids), "success": success, "failed": failed}
