import logging
import os
from contextlib import asynccontextmanager

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

load_dotenv()

from app.api import jobs as _jobs_module
from app.api import labs as _labs_module
from app.api.routes import router
from app.db.database import engine
from app.jobs import close_redis_pool, get_redis_pool, use_queue
from app.services.scheduler import start_scheduler, stop_scheduler

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)s — %(message)s",
)

_DB_AVAILABLE = bool(os.getenv("DATABASE_URL"))


@asynccontextmanager
async def lifespan(app: FastAPI):
    if _DB_AVAILABLE:
        @retry(
            retry=retry_if_exception_type(Exception),
            stop=stop_after_attempt(5),
            wait=wait_exponential(multiplier=1, min=1, max=30),
        )
        async def _ensure_db_ready() -> None:
            async with engine.connect() as conn:
                await conn.execute(text("SELECT 1"))

        await _ensure_db_ready()
        app.include_router(_labs_module.router)
        app.include_router(_jobs_module.router)
        if use_queue():
            await get_redis_pool()
        start_scheduler()
    yield
    if _DB_AVAILABLE:
        await close_redis_pool()
        stop_scheduler()


app = FastAPI(
    title="IRLI — Israel Research Lab Index",
    description=(
        "LLM-powered pipeline that crawls university faculty pages and returns "
        "structured LabProfile JSON for every research lab."
    ),
    version="0.2.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # tighten in production
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router)


@app.get("/", tags=["meta"])
async def root():
    return {"message": "IRLI — Israel Research Lab Index", "docs": "/docs", "health": "/health"}


@app.get("/health", tags=["meta"])
async def health() -> dict[str, str]:
    db_status = "connected" if _DB_AVAILABLE else "not configured"
    return {"status": "ok", "db": db_status}
