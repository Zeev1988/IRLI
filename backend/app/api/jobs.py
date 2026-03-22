"""
Job status endpoints.

GET /api/v1/jobs/{job_id} — poll status of a queued ingest/enrich job
"""
from fastapi import APIRouter, HTTPException

from app.jobs import get_job_status, use_queue

router = APIRouter(prefix="/jobs", tags=["jobs"])


@router.get(
    "/{job_id}",
    summary="Get job status",
    description="Returns status: queued, processing, or completed. When completed, includes result.",
)
async def get_job(job_id: str) -> dict:
    if not use_queue():
        raise HTTPException(status_code=503, detail="Job queue not configured (REDIS_URL required)")
    status = await get_job_status(job_id)
    if status is None:
        raise HTTPException(status_code=404, detail=f"Job {job_id} not found")
    return status
