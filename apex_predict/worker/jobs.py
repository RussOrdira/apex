from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from apex_predict.enums import JobStatus
from apex_predict.models import Event, ProviderSyncLog
from apex_predict.providers.router import ProviderRouter
from apex_predict.services.ai import get_or_create_preview
from apex_predict.services.ingestion import auto_finalize_ended_sessions
from apex_predict.services.scoring import auto_open_scheduled_sessions, lock_expired_sessions

provider_router = ProviderRouter()


def now_utc() -> datetime:
    return datetime.now(tz=timezone.utc)


async def run_session_state_jobs(db: AsyncSession) -> dict[str, int]:
    opened = await auto_open_scheduled_sessions(db)
    locked = await lock_expired_sessions(db)
    await db.flush()
    return {"opened": opened, "locked": locked}


async def run_provider_health_job(db: AsyncSession) -> dict[str, str]:
    active = await provider_router.active_provider()
    details = f"active={active.name}"
    db.add(
        ProviderSyncLog(
            provider_name=active.name,
            resource="health",
            status=JobStatus.SUCCESS,
            details=details,
        )
    )
    await db.flush()
    return {"active_provider": active.name}


async def run_ai_previews_job(db: AsyncSession) -> dict[str, int]:
    upcoming_events = (
        await db.scalars(select(Event).where(Event.end_at >= now_utc()).order_by(Event.start_at.asc()))
    ).all()

    generated = 0
    for event in upcoming_events:
        preview = await get_or_create_preview(db, event.id)
        if preview is not None:
            generated += 1
    await db.flush()
    return {"events_considered": len(upcoming_events), "previews_ready": generated}


async def run_auto_finalize_sessions_job(db: AsyncSession) -> dict[str, int]:
    return await auto_finalize_ended_sessions(
        db,
        initiated_by="worker:auto-finalize",
        provider_router=provider_router,
    )
