from contextlib import asynccontextmanager

from fastapi import FastAPI

from apex_predict.config import get_settings
from apex_predict.db import AsyncSessionLocal, init_db
from apex_predict.worker.jobs import (
    run_ai_previews_job,
    run_auto_finalize_sessions_job,
    run_provider_health_job,
    run_session_state_jobs,
)
from apex_predict.worker.scheduler import ScheduledJob, WorkerScheduler

settings = get_settings()
scheduler = WorkerScheduler(
    jobs=[
        ScheduledJob(
            name="session-state",
            interval_seconds=settings.worker_session_state_interval_seconds,
            runner=run_session_state_jobs,
        ),
        ScheduledJob(
            name="provider-health",
            interval_seconds=settings.worker_provider_health_interval_seconds,
            runner=run_provider_health_job,
        ),
        ScheduledJob(
            name="ai-previews",
            interval_seconds=settings.worker_ai_previews_interval_seconds,
            runner=run_ai_previews_job,
        ),
        ScheduledJob(
            name="auto-finalize",
            interval_seconds=settings.worker_auto_finalize_interval_seconds,
            runner=run_auto_finalize_sessions_job,
        ),
    ],
    session_factory=AsyncSessionLocal,
    startup_delay_seconds=settings.worker_startup_delay_seconds,
)

@asynccontextmanager
async def lifespan(_: FastAPI):
    await init_db()
    if settings.worker_scheduler_enabled:
        await scheduler.start()
    yield
    if settings.worker_scheduler_enabled:
        await scheduler.stop()


app = FastAPI(title="Apex Predict Worker", lifespan=lifespan)


@app.get("/health")
async def health() -> dict[str, str | bool]:
    return {
        "status": "ok",
        "scheduler_enabled": settings.worker_scheduler_enabled,
        "scheduler_running": scheduler.is_running,
    }


@app.post("/jobs/session-state")
async def session_state_job() -> dict:
    async with AsyncSessionLocal() as db:
        result = await run_session_state_jobs(db)
        await db.commit()
        return result


@app.post("/jobs/provider-health")
async def provider_health_job() -> dict:
    async with AsyncSessionLocal() as db:
        result = await run_provider_health_job(db)
        await db.commit()
        return result


@app.post("/jobs/ai-previews")
async def ai_previews_job() -> dict:
    async with AsyncSessionLocal() as db:
        result = await run_ai_previews_job(db)
        await db.commit()
        return result


@app.post("/jobs/auto-finalize-sessions")
async def auto_finalize_sessions_job() -> dict:
    async with AsyncSessionLocal() as db:
        result = await run_auto_finalize_sessions_job(db)
        await db.commit()
        return result


@app.post("/jobs/scoring-candidates")
async def scoring_candidates_compat_job() -> dict:
    async with AsyncSessionLocal() as db:
        result = await run_auto_finalize_sessions_job(db)
        await db.commit()
        return result
