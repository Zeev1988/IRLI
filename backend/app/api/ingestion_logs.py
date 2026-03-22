"""
Ingestion observability endpoints.

GET /api/v1/ingestion-logs — list recent ingestion runs
"""
from sqlalchemy import select

from app.db.database import get_session
from app.db.models import IngestionLogORM
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

router = APIRouter(prefix="/ingestion-logs", tags=["ingestion-logs"])


@router.get(
    "",
    summary="List ingestion logs",
    description="Returns recent ingestion runs with index_url, timing, and success/failed counts.",
)
async def list_ingestion_logs(
    limit: int = 50,
    session: AsyncSession = Depends(get_session),
) -> list[dict]:
    result = await session.execute(
        select(IngestionLogORM)
        .order_by(IngestionLogORM.started_at.desc())
        .limit(limit)
    )
    rows = result.scalars().all()
    return [
        {
            "id": r.id,
            "index_url": r.index_url,
            "started_at": r.started_at.isoformat() if r.started_at else None,
            "finished_at": r.finished_at.isoformat() if r.finished_at else None,
            "success_count": r.success_count,
            "failed_count": r.failed_count,
            "error_message": r.error_message,
        }
        for r in rows
    ]
