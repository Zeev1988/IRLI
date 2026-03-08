"""
Database initialization and startup checks.

Ensures DB is reachable before the app starts (e.g. before scheduler).
"""
from sqlalchemy import text
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from app.db.database import engine


@retry(
    retry=retry_if_exception_type(Exception),
    stop=stop_after_attempt(5),
    wait=wait_exponential(multiplier=1, min=1, max=30),
)
async def ensure_db_ready() -> None:
    """Run a dummy query to verify DB connectivity. Retries with exponential backoff."""
    async with engine.connect() as conn:
        await conn.execute(text("SELECT 1"))
