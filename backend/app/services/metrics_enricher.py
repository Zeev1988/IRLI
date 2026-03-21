"""
Enrich lab profiles with publication metrics from OpenAlex API.

Fetches publication_count, citation_count, h_index for each lab's PI
by searching OpenAlex and matching by name + institution.
Uses "Known Paper" strategy when representative_papers are available.

OpenAlex: optional OA_API_KEY enables $1/day free credits and higher limits.
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
OA_API_BASE = "https://api.openalex.org"
_RATE_LIMIT_DELAY = float(os.getenv("OA_RATE_LIMIT_DELAY", "0.2"))
_oa_client: httpx.AsyncClient | None = None


def _get_oa_headers() -> dict:
    """User-Agent with mailto for polite pool (10 req/s)."""
    mailto = os.getenv("OA_MAILTO", "irli@example.com")
    return {
        "User-Agent": f"IRLI/1.0 (https://github.com/irli; mailto:{mailto})",
        "Accept": "application/json",
    }


def _get_oa_client() -> httpx.AsyncClient:
    global _oa_client
    if _oa_client is None:
        _oa_client = httpx.AsyncClient(
            timeout=15.0,
            headers=_get_oa_headers(),
        )
    return _oa_client


def _should_retry(resp: httpx.Response) -> bool:
    return resp.status_code == 429 or resp.status_code >= 500


def _oa_wait(retry_state) -> float:
    if retry_state.outcome and not retry_state.outcome.failed:
        result = retry_state.outcome.result()
        if getattr(result, "status_code", 0) == 429:
            return 60.0
    return min(60.0, 2**retry_state.attempt_number)


def _extract_author_id(oa_url: str | None) -> str | None:
    """Extract short ID (e.g. A1234567) from https://openalex.org/A1234567."""
    if not oa_url or "/" not in oa_url:
        return None
    return oa_url.rsplit("/", 1)[-1] or None


def _oa_author_to_metrics(author: dict) -> dict:
    """Map OpenAlex author to our metrics format."""
    return {
        "paperCount": author.get("works_count"),
        "citationCount": author.get("cited_by_count"),
        "hIndex": (author.get("summary_stats") or {}).get("h_index"),
        "authorId": _extract_author_id(author.get("id")),
    }


def _author_matches_institution(author: dict, institution: str) -> bool:
    """Check if author's affiliations contain the institution (or no filter)."""
    if not institution or not institution.strip():
        return True
    inst_lower = institution.strip().lower()
    # Check affiliations
    for aff in author.get("affiliations") or []:
        inst = aff.get("institution") or {}
        if inst_lower in (inst.get("display_name") or "").lower():
            return True
    # Check last_known_institutions
    for inst in author.get("last_known_institutions") or []:
        if inst_lower in (inst.get("display_name") or "").lower():
            return True
    return False


def _name_matches(pi_name: str, author_name: str) -> bool:
    """Check if PI name matches author name (handles titles, initials, etc.)."""
    def tokenize(s: str) -> list:
        if not s:
            return []
        s = re.sub(r"^(dr\.?|prof\.?|professor|phd|m\.d\.?)\s+", "", s, flags=re.I).strip().lower()
        s = re.sub(r"[^\w\s-]", " ", s)
        return s.split()

    pi_tokens = tokenize(pi_name)
    auth_tokens = tokenize(author_name or "")
    if not pi_tokens or not auth_tokens:
        return False
    if pi_tokens == auth_tokens:
        return True
    pi_last = pi_tokens[-1]
    auth_last = auth_tokens[-1]
    if pi_last != auth_last and pi_tokens[0] != auth_tokens[0]:
        if pi_last not in auth_tokens and auth_last not in pi_tokens:
            return False
    if pi_last in auth_tokens:
        pi_first_initial = pi_tokens[0][0]
        try:
            auth_idx = auth_tokens.index(pi_last)
            other = auth_tokens[:auth_idx] + auth_tokens[auth_idx + 1 :]
            if any(t.startswith(pi_first_initial) for t in other):
                return True
        except ValueError:
            pass
    return False


def _oa_params(params: dict | None = None) -> dict:
    """Merge request params with API key if set (enables $1/day free credits)."""
    p = dict(params or {})
    if key := os.getenv("OA_API_KEY"):
        p["api_key"] = key
    return p


async def _oa_get(url: str, params: dict | None = None) -> httpx.Response:
    """GET with retry on 429/5xx."""
    client = _get_oa_client()
    req_params = _oa_params(params)
    async for attempt in AsyncRetrying(
        retry=retry_if_exception_type(Exception) | retry_if_result(_should_retry),
        stop=stop_after_attempt(3),
        wait=_oa_wait,
        reraise=True,
    ):
        with attempt:
            resp = await client.get(url, params=req_params)
            if resp.status_code == 429:
                logger.warning("OpenAlex rate limited (429)")
            elif resp.status_code >= 500:
                logger.warning("OpenAlex %s, retry %d/3", resp.status_code, attempt.retry_state.attempt_number)
            return resp


async def fetch_author_metrics(author_id: str) -> dict | None:
    """
    Fetch works_count, cited_by_count, h_index for an author from OpenAlex.
    author_id can be short (A1234567) or full URL. Public for testing.
    """
    oid = _extract_author_id(author_id) if "/" in author_id else author_id
    url = f"{OA_API_BASE}/authors/{oid}"
    try:
        resp = await _oa_get(url)
        if resp.status_code != 200:
            logger.warning("OpenAlex author %s: %s", author_id, resp.status_code)
            return None
        data = resp.json()
        return _oa_author_to_metrics(data)
    except Exception:
        logger.exception("OpenAlex fetch failed for author %s", author_id)
        return None


async def _find_author_via_work_search(paper_title: str, pi_name: str) -> str | None:
    """Search works by title; return OpenAlex author ID if PI matches an author."""
    url = f"{OA_API_BASE}/works"
    params = {"search": paper_title[:200], "per_page": 5}
    try:
        resp = await _oa_get(url, params=params)
    except Exception:
        logger.exception("OpenAlex work search failed for %r", paper_title[:50])
        return None
    if resp.status_code != 200:
        return None
    works = resp.json().get("results") or []
    for work in works:
        for authorship in work.get("authorships") or []:
            author = authorship.get("author") or {}
            if _name_matches(pi_name, author.get("display_name")):
                return _extract_author_id(author.get("id"))
    return None


async def _resolve_author_for_lab(lab_id: int, session: AsyncSession) -> tuple[str | None, dict | None]:
    """
    Resolve OpenAlex author for a lab. Returns (author_id, metrics_dict) or (None, None).
    """
    result = await session.execute(select(LabProfileORM).where(LabProfileORM.id == lab_id))
    row = result.scalar_one_or_none()
    if not row:
        return None, None

    rep_papers = getattr(row, "representative_papers", None) or []
    if rep_papers:
        for paper_title in rep_papers[:5]:
            author_id = await _find_author_via_work_search(paper_title, row.pi_name)
            if author_id:
                await asyncio.sleep(_RATE_LIMIT_DELAY)
                metrics = await fetch_author_metrics(author_id)
                if metrics and any(metrics.get(k) is not None for k in ("paperCount", "citationCount", "hIndex")):
                    return author_id, metrics
            await asyncio.sleep(_RATE_LIMIT_DELAY)

    url = f"{OA_API_BASE}/authors"
    params = {"search": row.pi_name, "per_page": 10}
    try:
        resp = await _oa_get(url, params=params)
    except Exception:
        logger.exception("OpenAlex search failed for lab %d", lab_id)
        return None, None
    if resp.status_code != 200:
        return None, None
    authors = resp.json().get("results") or []
    for author in authors:
        if _author_matches_institution(author, row.institution or ""):
            metrics = _oa_author_to_metrics(author)
            if any(metrics.get(k) is not None for k in ("paperCount", "citationCount", "hIndex")):
                return metrics.get("authorId"), metrics
    return None, None


async def search_and_fetch_metrics(
    pi_name: str,
    institution: str,
    representative_papers: list[str] | None = None,
) -> dict | None:
    """
    Search OpenAlex for author by name, filter by institution, return metrics.
    When representative_papers is provided, tries Known Paper strategy first.
    Returns metrics dict (paperCount, citationCount, hIndex, authorId) or None.
    """
    if representative_papers:
        for paper_title in representative_papers[:5]:
            author_id = await _find_author_via_work_search(paper_title, pi_name)
            if author_id:
                await asyncio.sleep(_RATE_LIMIT_DELAY)
                metrics = await fetch_author_metrics(author_id)
                if metrics:
                    return metrics
            await asyncio.sleep(_RATE_LIMIT_DELAY)

    url = f"{OA_API_BASE}/authors"
    params = {"search": pi_name, "per_page": 10}
    try:
        resp = await _oa_get(url, params=params)
    except Exception:
        logger.exception("OpenAlex search failed for %s", pi_name)
        return None
    if resp.status_code != 200:
        return None
    authors = resp.json().get("results") or []
    for author in authors:
        if _author_matches_institution(author, institution):
            metrics = _oa_author_to_metrics(author)
            if any(metrics.get(k) is not None for k in ("paperCount", "citationCount", "hIndex")):
                return metrics
    return None


async def enrich_lab_metrics(lab_id: int, session: AsyncSession) -> bool:
    """Fetch metrics for one lab and update the DB. Returns True on success."""
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

    author_id, metrics = await _resolve_author_for_lab(lab_id, session)
    if not author_id or not metrics:
        logger.debug("No OpenAlex match for lab %d (%s)", lab_id, row.pi_name)
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
    Enrich labs with metrics from OpenAlex.
    Returns {"total", "success", "failed"}.
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

    success = 0
    for lab_id in lab_ids:
        async with AsyncSessionLocal() as session:
            ok = await enrich_lab_metrics(lab_id, session)
            if ok:
                success += 1
        await asyncio.sleep(_RATE_LIMIT_DELAY)

    failed = len(lab_ids) - success
    logger.info("Enrichment complete: %d/%d succeeded", success, len(lab_ids))
    return {"total": len(lab_ids), "success": success, "failed": failed}
