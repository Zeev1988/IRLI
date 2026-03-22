"""
Enrich lab profiles with publication metrics from OpenAlex API.

Fetches publication_count, citation_count, h_index for each lab's PI
by searching OpenAlex and matching by name + institution.
Resolution order: (1) author search filtered by institution ID, (2) if 0 or
multiple matches, fall back to Known Paper strategy using representative_papers.

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
_institution_id_cache: dict[str, str | None] = {}


_DEFAULT_MAILTO = "irli@example.com"
_mailto_warned = False


def _get_oa_headers() -> dict:
    """User-Agent with mailto for polite pool. Set OA_MAILTO to your email in production."""
    global _mailto_warned
    mailto = os.getenv("OA_MAILTO", _DEFAULT_MAILTO)
    if not _mailto_warned and mailto == _DEFAULT_MAILTO and not os.getenv("OA_API_KEY"):
        _mailto_warned = True
        logger.warning(
            "OA_MAILTO not set: using placeholder. Set OA_MAILTO=your@email.com for polite pool."
        )
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
    """Extract short ID (e.g. A1234567, I123456) from https://openalex.org/..."""
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


def _institution_match_strength(author: dict, institution: str) -> int:
    """
    Return 0=no match, 1=substring, 2=exact. Used for disambiguation ranking.
    """
    if not institution or not institution.strip():
        return 2
    inst = institution.strip().lower()
    best = 0

    def check(display_name: str) -> None:
        nonlocal best
        dn = (display_name or "").lower()
        if not dn:
            return
        if inst == dn:
            best = max(best, 2)
        elif inst in dn or dn in inst:
            best = max(best, 1)

    for aff in author.get("affiliations") or []:
        check((aff.get("institution") or {}).get("display_name"))
    for i in author.get("last_known_institutions") or []:
        check(i.get("display_name"))
    return best


def _name_match_strength(pi_name: str, author: dict) -> int:
    """
    Return 0=no match, 1=last+initial, 2=exact. Checks display_name and alternatives.
    """
    def tokenize(s: str) -> list:
        if not s:
            return []
        s = re.sub(r"^(dr\.?|prof\.?|professor|phd|m\.d\.?)\s+", "", s, flags=re.I).strip().lower()
        s = re.sub(r"[^\w\s-]", " ", s)
        return s.split()

    def score(name: str) -> int:
        if not name:
            return 0
        pi_tok = tokenize(pi_name)
        auth_tok = tokenize(name)
        if not pi_tok or not auth_tok:
            return 0
        if pi_tok == auth_tok:
            return 2
        pi_last, auth_last = pi_tok[-1], auth_tok[-1]
        if pi_last not in auth_tok:
            return 0
        if pi_tok[0][0] in (t[0] for t in auth_tok if t != pi_last):
            return 1
        return 0

    names = [author.get("display_name")] + (author.get("display_name_alternatives") or [])
    return max(score(n) for n in names if n)


def _name_matches(pi_name: str, author_name: str) -> bool:
    """Check if PI name matches author name (handles titles, initials, etc.)."""
    return _name_match_strength(pi_name, {"display_name": author_name}) > 0


def _pick_best_author(authors: list[dict], pi_name: str, institution: str) -> dict | None:
    """
    Disambiguate when multiple authors match. Rank by institution strength,
    then name strength, then relevance_score, then cited_by_count.
    """
    def rank(a: dict) -> tuple | None:
        inst = _institution_match_strength(a, institution)
        name = _name_match_strength(pi_name, a)
        if inst == 0 or name == 0:
            return None
        if not institution or not institution.strip():
            inst = 2
        return (inst, name, float(a.get("relevance_score") or 0), a.get("cited_by_count") or 0)

    ranked = [(r, a) for a in authors if (r := rank(a)) is not None]
    if not ranked:
        return None
    ranked.sort(key=lambda x: x[0], reverse=True)
    return ranked[0][1]


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


async def _search_institution_id(institution_name: str) -> str | None:
    """Search OpenAlex institutions by name; return best-matching ID (e.g. I123456)."""
    if not institution_name or not institution_name.strip():
        return None
    url = f"{OA_API_BASE}/institutions"
    params = {"search": institution_name[:200], "per_page": 3}
    try:
        resp = await _oa_get(url, params=params)
    except Exception:
        logger.debug("OpenAlex institution search failed for %r", institution_name[:50])
        return None
    if resp.status_code != 200:
        return None
    results = resp.json().get("results") or []
    if not results:
        return None
    return _extract_author_id(results[0].get("id"))  # I123456 from https://openalex.org/I123


async def _get_institution_id_cached(institution_name: str) -> str | None:
    """Return OpenAlex institution ID, using cache to avoid repeated lookups."""
    key = institution_name.strip() if institution_name else ""
    if not key:
        return None
    if key not in _institution_id_cache:
        _institution_id_cache[key] = await _search_institution_id(institution_name)
    return _institution_id_cache[key]


async def _search_authors_by_institution(
    pi_name: str, institution_id: str
) -> list[dict]:
    """Search authors by name filtered by institution ID. Returns full author objects."""
    url = f"{OA_API_BASE}/authors"
    params = {
        "search": pi_name,
        "filter": f"last_known_institutions.id:{institution_id}",
        "per_page": 15,
    }
    try:
        resp = await _oa_get(url, params=params)
    except Exception:
        logger.debug("OpenAlex author+institution search failed for %s", pi_name)
        return []
    if resp.status_code != 200:
        return []
    return resp.json().get("results") or []


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


async def _resolve_author_via_papers(
    rep_papers: list[str], pi_name: str
) -> tuple[str | None, dict | None]:
    """Known Paper strategy: search works by title, match author. Returns (author_id, metrics) or (None, None)."""
    for paper_title in rep_papers[:5]:
        author_id = await _find_author_via_work_search(paper_title, pi_name)
        if author_id:
            await asyncio.sleep(_RATE_LIMIT_DELAY)
            metrics = await fetch_author_metrics(author_id)
            if metrics and any(metrics.get(k) is not None for k in ("paperCount", "citationCount", "hIndex")):
                return author_id, metrics
        await asyncio.sleep(_RATE_LIMIT_DELAY)
    return None, None


async def _resolve_author_for_lab(lab_id: int, session: AsyncSession) -> tuple[str | None, dict | None]:
    """
    Resolve OpenAlex author. (1) Institution-filtered search first; (2) if 0 or
    multiple matches, fall back to Known Paper strategy; (3) fallback to name-only search.
    """
    result = await session.execute(select(LabProfileORM).where(LabProfileORM.id == lab_id))
    row = result.scalar_one_or_none()
    if not row:
        return None, None

    pi_name = row.pi_name
    institution = row.institution or ""
    rep_papers = getattr(row, "representative_papers", None) or []

    # Step 1: Institution-first — search authors by name filtered by institution ID
    authors: list[dict] = []
    if institution.strip():
        await asyncio.sleep(_RATE_LIMIT_DELAY)
        inst_id = await _get_institution_id_cached(institution)
        if inst_id:
            await asyncio.sleep(_RATE_LIMIT_DELAY)
            authors = await _search_authors_by_institution(pi_name, inst_id)

    # If no institution filter worked, fall back to name-only search
    if not authors:
        url = f"{OA_API_BASE}/authors"
        params = {"search": pi_name, "per_page": 15}
        try:
            resp = await _oa_get(url, params=params)
            if resp.status_code == 200:
                authors = resp.json().get("results") or []
        except Exception:
            logger.exception("OpenAlex search failed for lab %d", lab_id)

    # Filter to those matching institution (client-side when we used name-only)
    if institution.strip() and authors:
        authors = [a for a in authors if _institution_match_strength(a, institution) > 0]

    matching = [
        a for a in authors
        if _institution_match_strength(a, institution) > 0 and _name_match_strength(pi_name, a) > 0
    ]
    best = _pick_best_author(authors, pi_name, institution)

    # Single clear match — use it
    if best and len(matching) == 1:
        metrics = _oa_author_to_metrics(best)
        if any(metrics.get(k) is not None for k in ("paperCount", "citationCount", "hIndex")):
            return metrics.get("authorId"), metrics

    # Step 2: 0 or multiple matches — try Known Paper strategy
    if rep_papers:
        author_id, metrics = await _resolve_author_via_papers(rep_papers, pi_name)
        if author_id and metrics:
            return author_id, metrics

    # Step 3: Use best from name/institution search even if ambiguous (no paper confirm)
    if best:
        metrics = _oa_author_to_metrics(best)
        if any(metrics.get(k) is not None for k in ("paperCount", "citationCount", "hIndex")):
            return metrics.get("authorId"), metrics

    return None, None


async def search_and_fetch_metrics(
    pi_name: str,
    institution: str,
    representative_papers: list[str] | None = None,
) -> dict | None:
    """
    Search OpenAlex for author. Institution-filtered search first; if 0 or
    multiple matches, fall back to Known Paper strategy.
    Returns metrics dict (paperCount, citationCount, hIndex, authorId) or None.
    """
    rep_papers = representative_papers or []

    # Step 1: Institution-first
    authors: list[dict] = []
    if institution and institution.strip():
        await asyncio.sleep(_RATE_LIMIT_DELAY)
        inst_id = await _get_institution_id_cached(institution)
        if inst_id:
            await asyncio.sleep(_RATE_LIMIT_DELAY)
            authors = await _search_authors_by_institution(pi_name, inst_id)

    if not authors:
        url = f"{OA_API_BASE}/authors"
        params = {"search": pi_name, "per_page": 15}
        try:
            resp = await _oa_get(url, params=params)
            if resp.status_code == 200:
                authors = resp.json().get("results") or []
        except Exception:
            logger.exception("OpenAlex search failed for %s", pi_name)
            return None

    if institution and institution.strip() and authors:
        authors = [a for a in authors if _institution_match_strength(a, institution) > 0]

    matching = [
        a for a in authors
        if _institution_match_strength(a, institution) > 0 and _name_match_strength(pi_name, a) > 0
    ]
    best = _pick_best_author(authors, pi_name, institution)

    if best and len(matching) == 1:
        metrics = _oa_author_to_metrics(best)
        if any(metrics.get(k) is not None for k in ("paperCount", "citationCount", "hIndex")):
            return metrics

    # Step 2: Fallback to papers
    if rep_papers:
        author_id, metrics = await _resolve_author_via_papers(rep_papers, pi_name)
        if author_id and metrics:
            return metrics

    if best:
        metrics = _oa_author_to_metrics(best)
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
