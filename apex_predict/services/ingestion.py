from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from apex_predict.enums import JobStatus, QuestionType, SessionState
from apex_predict.models import JobRun, ProviderSyncLog, QuestionInstance, Session
from apex_predict.providers.router import ProviderRouter
from apex_predict.services.scoring import record_job_run, run_session_scoring


def _now() -> datetime:
    return datetime.now(tz=timezone.utc)


def _normalize_token(value: str) -> str:
    return "".join(ch for ch in value.upper() if ch.isalnum())


def _match_option(options: list[str], candidates: list[str | None]) -> str | None:
    normalized_to_option = {_normalize_token(option): option for option in options}
    for candidate in candidates:
        if not candidate:
            continue
        direct = normalized_to_option.get(_normalize_token(candidate))
        if direct:
            return direct
    return None


def resolve_question_option(question: QuestionInstance, facts: dict) -> str | None:
    if question.question_type == QuestionType.POLE:
        return _match_option(question.options, [facts.get("pole"), facts.get("winner")])

    if question.question_type == QuestionType.WINNER:
        return _match_option(question.options, [facts.get("winner")])

    if question.question_type == QuestionType.TOP5:
        top5 = facts.get("top5") or []
        return _match_option(question.options, list(top5))

    if question.question_type == QuestionType.DNF:
        dnf = facts.get("dnf_driver_codes") or []
        return _match_option(question.options, list(dnf))

    if question.question_type == QuestionType.FASTEST_LAP:
        return _match_option(question.options, [facts.get("fastest_lap")])

    if question.question_type == QuestionType.SAFETY_CAR:
        deployed = bool(facts.get("safety_car"))
        if deployed:
            return _match_option(question.options, ["YES", "Y", "TRUE", "1"])
        return _match_option(question.options, ["NO", "N", "FALSE", "0"])

    if question.question_type == QuestionType.MIDFIELD_CONSTRUCTOR:
        midfield = facts.get("midfield_constructor")
        if midfield is None:
            constructor_points = facts.get("constructor_points") or {}
            sorted_constructors = sorted(
                constructor_points.items(), key=lambda item: item[1], reverse=True
            )
            top_three = {name for name, _ in sorted_constructors[:3]}
            for constructor, _ in sorted_constructors:
                if constructor not in top_three:
                    midfield = constructor
                    break
        return _match_option(question.options, [midfield])

    if question.question_type == QuestionType.FIRST_PIT_STOP_TEAM:
        return _match_option(question.options, [facts.get("first_pit_stop_team")])

    if question.question_type == QuestionType.FIRST_SAFETY_CAR_LAP:
        first_lap = facts.get("first_safety_car_lap")
        if first_lap is not None:
            lap = int(first_lap)
            return _match_option(question.options, [str(lap), f"LAP {lap}", f"Lap {lap}"])
        return _match_option(question.options, ["NONE", "NO", "NO SC", "NO_SAFETY_CAR", "NA"])

    return None


async def ingest_session_question_outcomes(
    db: AsyncSession,
    session_obj: Session,
    provider_router: ProviderRouter | None = None,
) -> dict:
    router = provider_router or ProviderRouter()

    if not session_obj.external_id:
        db.add(
            ProviderSyncLog(
                provider_name="router",
                resource="session_outcomes",
                status=JobStatus.FAILED,
                details=f"session={session_obj.id} missing external_id",
            )
        )
        await db.flush()
        return {"resolved": 0, "unresolved": 0, "provider": "none", "facts": {}}

    provider_name, facts = await router.fetch_session_facts(session_obj.external_id)
    questions = (
        await db.scalars(select(QuestionInstance).where(QuestionInstance.session_id == session_obj.id))
    ).all()

    resolved = 0
    unresolved = 0
    for question in questions:
        answer = resolve_question_option(question, facts)
        if answer is None:
            unresolved += 1
            continue

        question.correct_option = answer
        resolved += 1

    db.add(
        ProviderSyncLog(
            provider_name=provider_name,
            resource="session_outcomes",
            status=JobStatus.SUCCESS,
            details=f"session={session_obj.id} resolved={resolved} unresolved={unresolved}",
            finished_at=_now(),
        )
    )
    await db.flush()

    return {"resolved": resolved, "unresolved": unresolved, "provider": provider_name, "facts": facts}


async def auto_finalize_ended_sessions(
    db: AsyncSession,
    initiated_by: str = "worker:auto-finalize",
    provider_router: ProviderRouter | None = None,
) -> dict[str, int]:
    candidates = (
        await db.scalars(
            select(Session).where(
                Session.ends_at <= _now(),
                Session.state.in_([SessionState.OPEN, SessionState.LOCKED]),
            )
        )
    ).all()

    finalized = 0
    failed = 0
    skipped = 0
    for session_obj in candidates:
        if session_obj.state == SessionState.OPEN:
            session_obj.state = SessionState.LOCKED

        idempotency_key = f"auto-finalize:{session_obj.id}"
        existing_job = await db.scalar(
            select(JobRun).where(
                JobRun.idempotency_key == idempotency_key,
                JobRun.status == JobStatus.SUCCESS,
            )
        )
        if existing_job is not None:
            skipped += 1
            continue

        try:
            ingestion = await ingest_session_question_outcomes(
                db,
                session_obj,
                provider_router=provider_router,
            )
            entries = await run_session_scoring(db, session_obj.id, initiated_by=initiated_by)
            await record_job_run(
                db,
                idempotency_key=idempotency_key,
                job_type="auto_finalize_session",
                status=JobStatus.SUCCESS,
                payload_json={"session_id": session_obj.id},
                result_json={
                    "entries_created": entries,
                    "resolved_questions": ingestion["resolved"],
                    "unresolved_questions": ingestion["unresolved"],
                },
            )
            finalized += 1
        except Exception as exc:
            failed += 1
            await record_job_run(
                db,
                idempotency_key=idempotency_key,
                job_type="auto_finalize_session",
                status=JobStatus.FAILED,
                payload_json={"session_id": session_obj.id},
                error_message=str(exc),
            )

    await db.flush()
    return {
        "candidates": len(candidates),
        "finalized": finalized,
        "failed": failed,
        "skipped": skipped,
    }
