from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1.outreach import router as outreach_router
from app.core.config import settings
from app.core.logging import configure_logging, get_logger
from app.jobs.scheduler import start_scheduler, stop_scheduler

configure_logging(settings.LOG_LEVEL)
log = get_logger(__name__)


@asynccontextmanager
async def lifespan(_: FastAPI):
    start_scheduler()
    log.info("app_started", env=settings.ENV)
    try:
        yield
    finally:
        stop_scheduler()


app = FastAPI(
    title="AgentEnginez — Outreach + Fulfillment",
    version="1.0.0",
    description="Track C: Equity Outreach, Postcards, Open House, Referrals, Reputation.",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
    allow_credentials=False,
)

app.include_router(outreach_router, prefix="/agentenginez/v1")


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok", "service": "agentenginez-outreach", "version": "1.0.0"}


@app.get("/")
async def root() -> dict[str, str]:
    return {
        "service": "agentenginez-outreach",
        "docs": "/docs",
        "health": "/health",
    }
