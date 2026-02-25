from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from apex_predict.enums import JobStatus, SessionState
from apex_predict.models import (
    JobRun,
    Prediction,
    PredictionAnswer,
    PredictionConfidenceAllocation,
    QuestionInstance,
    ScoreEntry,
    ScoringRule,
    Session,
)
from apex_predict.services.leaderboard import publish_leaderboard_snapshots


class ScoringError(Exception):
    pass


def _now() -> datetime:
    return datetime.now(tz=timezone.utc)


async def _finalize_session_and_publish(
    session: AsyncSession,
    *,
    target_session: Session,
) -> None:
    target_session.state = SessionState.FINALIZED
    await session.flush()
    await publish_leaderboard_snapshots(session, session_id=target_session.id)


def confidence_multiplier_from_credits(credits: int) -> Decimal:
    if credits < 0:
        raise ValueError("credits_must_be_non_negative")
    return (Decimal("1.00") + (Decimal(credits) / Decimal("100.00"))).quantize(Decimal("0.01"))


def awarded_points_for_prediction(base_points: int | float | Decimal, credits: int) -> Decimal:
    points = Decimal(base_points)
    if points < 0:
        raise ValueError("base_points_must_be_non_negative")
    return (points * confidence_multiplier_from_credits(credits)).quantize(Decimal("0.01"))


async def run_session_scoring(session: AsyncSession, session_id: str, initiated_by: str) -> int:
    target_session = await session.get(Session, session_id)
    if target_session is None:
        raise ScoringError("session_not_found")

    target_session.state = SessionState.SCORING
    await session.flush()

    questions = (
        await session.scalars(select(QuestionInstance).where(QuestionInstance.session_id == session_id))
    ).all()
    question_map = {q.id: q for q in questions}
    if not question_map:
        await _finalize_session_and_publish(session, target_session=target_session)
        return 0

    rule_ids = {q.scoring_rule_id for q in questions}
    rules = (
        await session.scalars(select(ScoringRule).where(ScoringRule.id.in_(rule_ids)))
    ).all()
    rule_map = {r.id: r for r in rules}

    predictions = (
        await session.scalars(select(Prediction).where(Prediction.session_id == session_id))
    ).all()
    prediction_ids = [p.id for p in predictions]
    if not prediction_ids:
        await _finalize_session_and_publish(session, target_session=target_session)
        return 0

    answers = (
        await session.scalars(
            select(PredictionAnswer).where(PredictionAnswer.prediction_id.in_(prediction_ids))
        )
    ).all()
    allocations = (
        await session.scalars(
            select(PredictionConfidenceAllocation).where(
                PredictionConfidenceAllocation.prediction_id.in_(prediction_ids)
            )
        )
    ).all()

    by_prediction_answers: dict[str, list[PredictionAnswer]] = defaultdict(list)
    for answer in answers:
        by_prediction_answers[answer.prediction_id].append(answer)

    allocation_map: dict[tuple[str, str], int] = {}
    for allocation in allocations:
        allocation_map[(allocation.prediction_id, allocation.question_instance_id)] = allocation.credits

    existing_entries = (
        await session.scalars(
            select(ScoreEntry).where(
                and_(ScoreEntry.session_id == session_id, ScoreEntry.reason == "SESSION_SCORE")
            )
        )
    ).all()
    existing_key = {
        (entry.user_id, entry.session_id, entry.question_instance_id, entry.reason)
        for entry in existing_entries
    }

    created = 0
    for prediction in predictions:
        for answer in by_prediction_answers.get(prediction.id, []):
            question = question_map.get(answer.question_instance_id)
            if question is None or question.correct_option is None:
                continue
            if answer.selected_option != question.correct_option:
                continue
            rule = rule_map.get(question.scoring_rule_id)
            if rule is None:
                continue

            credits = allocation_map.get((prediction.id, question.id), 0)
            multiplier = confidence_multiplier_from_credits(credits)
            base_points = Decimal(rule.base_points)
            awarded = awarded_points_for_prediction(base_points, credits)

            key = (prediction.user_id, session_id, question.id, "SESSION_SCORE")
            if key in existing_key:
                continue

            entry = ScoreEntry(
                user_id=prediction.user_id,
                session_id=session_id,
                question_instance_id=question.id,
                base_points=float(base_points),
                confidence_multiplier=float(multiplier),
                awarded_points=float(awarded),
                reason="SESSION_SCORE",
                metadata_json={
                    "initiated_by": initiated_by,
                    "prediction_id": prediction.id,
                    "rule_id": rule.id,
                    "credits": credits,
                },
            )
            session.add(entry)
            existing_key.add(key)
            created += 1

    await _finalize_session_and_publish(session, target_session=target_session)
    return created


async def record_job_run(
    session: AsyncSession,
    *,
    idempotency_key: str,
    job_type: str,
    status: JobStatus,
    payload_json: dict,
    result_json: dict | None = None,
    error_message: str | None = None,
) -> JobRun:
    job_run = await session.scalar(select(JobRun).where(JobRun.idempotency_key == idempotency_key))
    if job_run is None:
        job_run = JobRun(
            idempotency_key=idempotency_key,
            job_type=job_type,
            payload_json=payload_json,
        )
        session.add(job_run)

    job_run.status = status
    job_run.result_json = result_json or {}
    job_run.error_message = error_message
    job_run.finished_at = _now()
    await session.flush()
    return job_run


async def lock_expired_sessions(session: AsyncSession) -> int:
    now = _now()
    sessions = (
        await session.scalars(
            select(Session).where(
                Session.lock_at <= now,
                Session.state.in_([SessionState.SCHEDULED, SessionState.OPEN]),
            )
        )
    ).all()
    for row in sessions:
        row.state = SessionState.LOCKED
    await session.flush()
    return len(sessions)


async def auto_open_scheduled_sessions(session: AsyncSession) -> int:
    now = _now()
    sessions = (
        await session.scalars(
            select(Session).where(Session.starts_at <= now, Session.state == SessionState.SCHEDULED)
        )
    ).all()
    for row in sessions:
        row.state = SessionState.OPEN
    await session.flush()
    return len(sessions)


async def global_points(session: AsyncSession) -> dict[str, float]:
    rows = (
        await session.execute(
            select(ScoreEntry.user_id, func.coalesce(func.sum(ScoreEntry.awarded_points), 0)).group_by(
                ScoreEntry.user_id
            )
        )
    ).all()
    return {user_id: float(points) for user_id, points in rows}
