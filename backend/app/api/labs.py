"""
Query endpoints for the lab_profiles table.

GET /api/v1/labs          — list or semantic-search labs
GET /api/v1/labs/{id}     — single lab by DB id
POST /api/v1/labs/ingest  — manually trigger ingestion for a faculty index URL
"""
import logging
import os
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, HttpUrl
from sqlalchemy import and_, func, or_, select, text
from sqlalchemy.ext.asyncio import AsyncSession
from tenacity import AsyncRetrying, retry_if_exception_type, stop_after_attempt, wait_exponential

from fastapi.responses import JSONResponse

from app.config import DEBUG_MODE
from app.db.database import get_session
from app.services.embeddings import get_embedding
from app.db.models import LabProfileORM
from app.jobs import enqueue_enrich, enqueue_ingest, use_queue
from app.services.ingestion import ingest_faculty
from app.services.metrics_enricher import enrich_all_labs

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/labs", tags=["labs"])


async def _embed_query(query: str) -> list[float]:
    """Embed search query (OpenAI 3-large or BGE-Large)."""
    async for attempt in AsyncRetrying(
        retry=retry_if_exception_type(Exception),
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=60),
        reraise=True,
    ):
        with attempt:
            return await get_embedding(query)


def _orm_to_dict(row: LabProfileORM) -> dict[str, Any]:
    return {
        "id": row.id,
        "pi_name": row.pi_name,
        "institution": row.institution,
        "faculty": row.faculty,
        "research_summary": row.research_summary,
        "keywords": row.keywords,
        "technologies": row.technologies,
        "representative_papers": row.representative_papers or [],
        "hiring_status": row.hiring_status,
        "lab_url": row.lab_url,
        "publication_count": row.publication_count,
        "citation_count": row.citation_count,
        "h_index": row.h_index,
        "semantic_scholar_author_id": row.semantic_scholar_author_id,
        "metrics_updated_at": row.metrics_updated_at.isoformat() if row.metrics_updated_at else None,
        "last_crawled_at": row.last_crawled_at.isoformat() if row.last_crawled_at else None,
    }


# ---------------------------------------------------------------------------
# GET /api/v1/labs
# ---------------------------------------------------------------------------
def _build_filter_clauses(
    institution: str | None,
    faculty: str | None,
    keyword: str | None,
    min_publication_count: int | None,
    min_citation_count: int | None,
    min_h_index: int | None,
) -> list:
    """Build SQLAlchemy filter clauses for institution, faculty, keyword, metrics."""
    clauses = []
    if institution and institution.strip():
        clauses.append(LabProfileORM.institution.ilike(f"%{institution.strip()}%"))
    if faculty and faculty.strip():
        clauses.append(LabProfileORM.faculty.ilike(f"%{faculty.strip()}%"))
    if keyword and keyword.strip():
        pat = f"%{keyword.strip().lower()}%"
        clauses.append(func.lower(func.array_to_string(LabProfileORM.keywords, " ")).like(pat))
    if min_publication_count is not None:
        clauses.append(LabProfileORM.publication_count >= min_publication_count)
    if min_citation_count is not None:
        clauses.append(LabProfileORM.citation_count >= min_citation_count)
    if min_h_index is not None:
        clauses.append(LabProfileORM.h_index >= min_h_index)
    return clauses


def _order_by_clause(sort_by: str | None, sort_order: str):
    """Return SQLAlchemy order_by for sort_by (publication_count, citation_count, h_index)."""
    col = None
    if sort_by == "publication_count":
        col = LabProfileORM.publication_count
    elif sort_by == "citation_count":
        col = LabProfileORM.citation_count
    elif sort_by == "h_index":
        col = LabProfileORM.h_index
    if col is None:
        return LabProfileORM.last_crawled_at.desc().nullslast()
    return col.desc().nullslast() if sort_order == "desc" else col.asc().nullslast()


@router.get(
    "",
    summary="List or search labs",
    description=(
        "Without `q`: returns labs (default: by last_crawled_at). "
        "With `q`: hybrid search (pgvector similarity + full-text ts_rank). "
        "Filter by institution, faculty, keyword, or min metrics. "
        "Sort by publication_count, citation_count, or h_index."
    ),
)
async def list_labs(
    q: str | None = Query(None, description="Semantic search query"),
    institution: str | None = Query(None, description="Filter by university/institution name"),
    faculty: str | None = Query(None, description="Filter by faculty/department"),
    keyword: str | None = Query(None, description="Filter by keyword (matches lab keywords)"),
    min_publication_count: int | None = Query(None, ge=0, description="Min publication count"),
    min_citation_count: int | None = Query(None, ge=0, description="Min citation count"),
    min_h_index: int | None = Query(None, ge=0, description="Min h-index"),
    sort_by: str | None = Query(
        None,
        description="Sort by: publication_count, citation_count, h_index, or last_crawled",
    ),
    sort_order: str = Query("desc", description="asc or desc"),
    limit: int = Query(20, ge=1, le=100),
    session: AsyncSession = Depends(get_session),
) -> list[dict[str, Any]]:
    filter_clauses = _build_filter_clauses(
        institution, faculty, keyword,
        min_publication_count, min_citation_count, min_h_index,
    )
    base_filter = and_(*filter_clauses) if filter_clauses else True

    if q and str(q).strip():
        if DEBUG_MODE:
            q_pat = f"%{q.strip()}%"
            q_match = or_(
                LabProfileORM.pi_name.ilike(q_pat),
                LabProfileORM.institution.ilike(q_pat),
                LabProfileORM.faculty.ilike(q_pat),
                func.array_to_string(LabProfileORM.keywords, " ").ilike(q_pat),
                func.array_to_string(LabProfileORM.technologies, " ").ilike(q_pat),
                func.array_to_string(LabProfileORM.research_summary, " ").ilike(q_pat),
            )
            stmt = (
                select(LabProfileORM)
                .where(base_filter, q_match)
                .order_by(_order_by_clause(sort_by, sort_order))
                .limit(limit)
            )
            result = await session.execute(stmt)
            return [_orm_to_dict(r) for r in result.scalars().all()]

        query_vec = await _embed_query(q)
        vec_literal = f"[{','.join(str(x) for x in query_vec)}]"
        q_clean = q.strip()

        # Hybrid search: combine pgvector similarity + PostgreSQL full-text (ts_rank).
        # Weights: 0.7 semantic, 0.3 keyword (BM25-style via ts_rank).
        filter_sql = ""
        filter_params: dict[str, Any] = {"vec": vec_literal, "limit": limit, "q_fts": q_clean}
        if institution and institution.strip():
            filter_sql += " AND institution ILIKE :inst"
            filter_params["inst"] = f"%{institution.strip()}%"
        if faculty and faculty.strip():
            filter_sql += " AND faculty ILIKE :fac"
            filter_params["fac"] = f"%{faculty.strip()}%"
        if keyword and keyword.strip():
            filter_sql += " AND EXISTS (SELECT 1 FROM unnest(keywords) AS kw WHERE kw ILIKE :kw_pat)"
            filter_params["kw_pat"] = f"%{keyword.strip()}%"
        if min_publication_count is not None:
            filter_sql += " AND publication_count >= :min_pub"
            filter_params["min_pub"] = min_publication_count
        if min_citation_count is not None:
            filter_sql += " AND citation_count >= :min_cit"
            filter_params["min_cit"] = min_citation_count
        if min_h_index is not None:
            filter_sql += " AND h_index >= :min_h"
            filter_params["min_h"] = min_h_index

        raw = await session.execute(
            text(
                """
                WITH q AS (SELECT plainto_tsquery('english', :q_fts) AS query)
                SELECT lp.* FROM lab_profiles lp
                CROSS JOIN q
                WHERE 1=1 """ + filter_sql + """
                ORDER BY (
                    0.7 * coalesce(1 - (lp.embedding <=> :vec::vector) / 2, 0)
                    + 0.3 * coalesce(
                        ts_rank(lp.search_vector, q.query) / (1 + ts_rank(lp.search_vector, q.query)),
                        0
                    )
                ) DESC NULLS LAST
                LIMIT :limit
                """
            ),
            filter_params,
        )
        rows = raw.mappings().all()
        return [dict(r) for r in rows]

    order_col = _order_by_clause(sort_by, sort_order)
    stmt = (
        select(LabProfileORM)
        .where(base_filter)
        .order_by(order_col)
        .limit(limit)
    )
    result = await session.execute(stmt)
    return [_orm_to_dict(r) for r in result.scalars().all()]


# ---------------------------------------------------------------------------
# GET /api/v1/labs/{lab_id}
# ---------------------------------------------------------------------------
@router.get("/{lab_id}", summary="Get a single lab by ID")
async def get_lab(
    lab_id: int,
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    row = await session.get(LabProfileORM, lab_id)
    if row is None:
        raise HTTPException(status_code=404, detail=f"Lab {lab_id} not found")
    return _orm_to_dict(row)


# ---------------------------------------------------------------------------
# POST /api/v1/labs/ingest
# ---------------------------------------------------------------------------
class IngestRequest(BaseModel):
    url: HttpUrl


# ---------------------------------------------------------------------------
# POST /api/v1/labs/enrich
# ---------------------------------------------------------------------------
@router.post(
    "/enrich",
    summary="Enrich labs with publication metrics from OpenAlex",
    description="Fetches publication_count, citation_count, h_index for each lab's PI.",
    response_model=None,
)
async def trigger_enrich(
    limit: int | None = Query(None, ge=1, le=500, description="Max labs to enrich (default: all)"),
) -> dict[str, Any] | JSONResponse:
    if use_queue():
        job_id = await enqueue_enrich(limit)
        if job_id:
            return JSONResponse(
                status_code=202,
                content={"job_id": job_id, "status": "queued", "message": "Enrich job queued"},
            )
    try:
        result = await enrich_all_labs(limit=limit)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    return {"status": "ok", **result}


# ---------------------------------------------------------------------------
# POST /api/v1/labs/ingest
# ---------------------------------------------------------------------------
@router.post(
    "/ingest",
    summary="Manually trigger ingestion for a faculty index URL",
    description=(
        "Discovers all lab links on the given faculty index page, "
        "crawls each one, extracts a LabProfile, and upserts it into the DB."
    ),
    response_model=None,
)
async def trigger_ingest(body: IngestRequest) -> dict[str, Any] | JSONResponse:
    if use_queue():
        job_id = await enqueue_ingest(str(body.url))
        if job_id:
            return JSONResponse(
                status_code=202,
                content={"job_id": job_id, "status": "queued", "message": "Ingest job queued"},
            )
    try:
        summary = await ingest_faculty(str(body.url))
    except Exception as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    return {"status": "ok", **summary}
