"""
Daily ingestion scheduler.

Uses APScheduler's AsyncIOScheduler so it shares the same event loop as
FastAPI. Started and stopped via the FastAPI lifespan context manager.

The job runs once per day at CRAWL_SCHEDULE_HOUR (default 3 AM UTC),
iterating over every URL in seeds/faculty_urls.py.
"""
import logging
import os

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from app.seeds.faculty_urls import FACULTY_INDEX_URLS
from app.services.ingestion import ingest_faculty

logger = logging.getLogger(__name__)

_SCHEDULE_HOUR = int(os.getenv("CRAWL_SCHEDULE_HOUR", "3"))

scheduler = AsyncIOScheduler()


async def _run_all_faculties() -> None:
    logger.info(
        "Scheduled ingestion starting — %d faculty URLs queued", len(FACULTY_INDEX_URLS)
    )
    for url in FACULTY_INDEX_URLS:
        try:
            summary = await ingest_faculty(url)
            logger.info("Ingested %s: %s", url, summary)
        except Exception:
            logger.exception("Ingestion failed for %s — continuing", url)
    logger.info("Scheduled ingestion complete")


def start_scheduler() -> None:
    scheduler.add_job(
        _run_all_faculties,
        trigger=CronTrigger(hour=_SCHEDULE_HOUR, minute=0, timezone="UTC"),
        id="daily_ingestion",
        replace_existing=True,
        misfire_grace_time=3600,  # allow up to 1h late start
    )
    scheduler.start()
    logger.info(
        "Scheduler started — daily ingestion at %02d:00 UTC", _SCHEDULE_HOUR
    )


def stop_scheduler() -> None:
    scheduler.shutdown(wait=False)
    logger.info("Scheduler stopped")
