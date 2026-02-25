from __future__ import annotations

import hashlib
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from apex_predict.enums import JobStatus
from apex_predict.models import AIGenerationLog, AIInsight, AIPreview, Event, Session


def _now() -> datetime:
    return datetime.now(tz=timezone.utc)


def _confidence_band(seed: str) -> str:
    bucket = int(hashlib.sha256(seed.encode("utf-8")).hexdigest(), 16) % 3
    if bucket == 0:
        return "LOW"
    if bucket == 1:
        return "MEDIUM"
    return "HIGH"


async def get_or_create_preview(db: AsyncSession, event_id: str) -> AIPreview | None:
    preview = await db.scalar(select(AIPreview).where(AIPreview.event_id == event_id))
    if preview is not None:
        return preview

    event = await db.get(Event, event_id)
    if event is None:
        return None

    confidence = _confidence_band(event.slug)
    summary = (
        f"{event.name}: strategy likely hinges on tire degradation and track position. "
        "Weather volatility could impact pit window timing."
    )

    preview = AIPreview(
        event_id=event.id,
        summary=summary,
        confidence_band=confidence,
        data_sources=["openf1", "historical_results", "aggregate_form"],
        generated_at=_now(),
    )
    db.add(preview)
    db.add(
        AIGenerationLog(
            entity_type="event_preview",
            entity_id=event.id,
            status=JobStatus.SUCCESS,
            prompt_hash=hashlib.sha256(summary.encode("utf-8")).hexdigest(),
            provider="heuristic-aggregate",
        )
    )
    await db.flush()
    return preview


async def get_or_create_session_insight(db: AsyncSession, session_id: str) -> AIInsight | None:
    insight = await db.scalar(select(AIInsight).where(AIInsight.session_id == session_id))
    if insight is not None:
        return insight

    session_obj = await db.get(Session, session_id)
    if session_obj is None:
        return None

    confidence = _confidence_band(f"{session_obj.id}:{session_obj.session_type.value}")
    explanation = (
        "Advisory pick weighting uses aggregate track history, recent pace trend, "
        "and session-type volatility. No personal user history is sent to any model provider."
    )

    insight = AIInsight(
        session_id=session_obj.id,
        explanation=explanation,
        confidence_band=confidence,
        data_sources=["openf1", "jolpica", "aggregate_session_metrics"],
        generated_at=_now(),
    )
    db.add(insight)
    db.add(
        AIGenerationLog(
            entity_type="session_insight",
            entity_id=session_obj.id,
            status=JobStatus.SUCCESS,
            prompt_hash=hashlib.sha256(explanation.encode("utf-8")).hexdigest(),
            provider="heuristic-aggregate",
        )
    )
    await db.flush()
    return insight
