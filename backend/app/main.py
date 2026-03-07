import logging
import os
from contextlib import asynccontextmanager

from dotenv import load_dotenv

load_dotenv()

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import router

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)s — %(message)s",
)

_DB_AVAILABLE = bool(os.getenv("DATABASE_URL"))


@asynccontextmanager
async def lifespan(app: FastAPI):
    if _DB_AVAILABLE:
        from app.api import labs as _labs_module  # registers the router
        from app.services.scheduler import start_scheduler, stop_scheduler
        app.include_router(_labs_module.router)
        start_scheduler()
    yield
    if _DB_AVAILABLE:
        from app.services.scheduler import stop_scheduler
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
