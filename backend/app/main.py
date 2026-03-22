import logging
import os
from contextlib import asynccontextmanager

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

load_dotenv()

from app.api import ingestion_logs as _ingestion_logs_module
from app.api import jobs as _jobs_module
from app.api import labs as _labs_module
from app.api.routes import router
from app.db.init import ensure_db_ready
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
        await ensure_db_ready()
        app.include_router(_labs_module.router)
        app.include_router(_jobs_module.router)
        app.include_router(_ingestion_logs_module.router)
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

_allowed_origins = os.getenv("ALLOWED_ORIGINS", "http://localhost:3000").strip()
CORS_ORIGINS = [o.strip() for o in _allowed_origins.split(",") if o.strip()] or ["*"]

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "https://irli-frontend.vercel.app",
        "https://irli.vercel.app"
    ],
    allow_credentials=True,
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
