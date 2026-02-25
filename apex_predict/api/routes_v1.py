from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from fastapi import APIRouter, HTTPException, Query, status
from sqlalchemy import delete, select

from apex_predict.api.deps import AdminAuthorized, AuthedUserId, DbSession
from apex_predict.config import get_settings
from apex_predict.enums import (
    JobStatus,
    JoinPolicy,
    LeagueVisibility,
    MemberRole,
    ModerationState,
    SessionState,
)
from apex_predict.models import (
    Event,
    League,
    LeagueInvite,
    LeagueMember,
    ModerationReport,
    Prediction,
    PredictionAnswer,
    PredictionConfidenceAllocation,
    ProviderSyncLog,
    QuestionInstance,
    ScoringRule,
    Season,
    Session,
)
from apex_predict.providers.router import ProviderRouter
from apex_predict.schemas import (
    AIInsightOut,
    AIPreviewOut,
    EventOut,
    LeaderboardOut,
    LeagueCreateIn,
    LeagueInviteOut,
    LeagueJoinIn,
    LeagueOut,
    PredictionOut,
    PredictionQuestion,
    PredictionSubmission,
    ReportIn,
    RuleOut,
    RuleUpsertIn,
    ScoringRunIn,
    ScoringRunOut,
    SeasonOut,
    SessionOut,
)
from apex_predict.services.ai import get_or_create_preview, get_or_create_session_insight
from apex_predict.services.ingestion import ingest_session_question_outcomes
from apex_predict.services.leaderboard import build_global_leaderboard, build_league_leaderboard
from apex_predict.services.moderation import is_name_allowed
from apex_predict.services.scoring import (
    record_job_run,
    run_session_scoring,
)

router = APIRouter(prefix="/v1", tags=["v1"])
settings = get_settings()
provider_router = ProviderRouter()


def now_utc() -> datetime:
    return datetime.now(tz=timezone.utc)


def coerce_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def generate_code(size: int = 8) -> str:
    return uuid4().hex[:size].upper()


async def _get_or_create_current_season(db: DbSession) -> Season:
    current = await db.scalar(select(Season).where(Season.is_current.is_(True)))
    if current is not None:
        return current

    year = now_utc().year
    current = await db.scalar(select(Season).where(Season.year == year))
    if current is None:
        current = Season(year=year, is_current=True)
        db.add(current)
    else:
        current.is_current = True

    await db.flush()
    return current


@router.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@router.get("/seasons/current", response_model=SeasonOut)
async def get_current_season(db: DbSession) -> Any:
    season = await _get_or_create_current_season(db)
    await db.commit()
    return SeasonOut.model_validate(season, from_attributes=True)


@router.get("/events", response_model=list[EventOut])
async def get_events(
    db: DbSession,
    season_id: str | None = Query(default=None),
    sync_if_empty: bool = Query(default=True),
) -> Any:
    if season_id:
        season = await db.get(Season, season_id)
        if season is None:
            raise HTTPException(status_code=404, detail="season_not_found")
    else:
        season = await _get_or_create_current_season(db)

    events = (await db.scalars(select(Event).where(Event.season_id == season.id))).all()
    if not events and sync_if_empty:
        try:
            provider_name, payload = await provider_router.fetch_events(season.year)
            db.add(
                ProviderSyncLog(
                    provider_name=provider_name,
                    resource="events",
                    status=JobStatus.SUCCESS,
                    details=f"fetched={len(payload)}",
                )
            )
            for row in payload:
                if row.get("start_at") is None or row.get("end_at") is None:
                    continue
                db.add(
                    Event(
                        season_id=season.id,
                        external_id=row.get("external_id"),
                        name=row["name"],
                        slug=row["slug"],
                        country=row["country"],
                        start_at=row["start_at"],
                        end_at=row["end_at"],
                    )
                )
        except Exception as exc:
            db.add(
                ProviderSyncLog(
                    provider_name="provider-router",
                    resource="events",
                    status=JobStatus.FAILED,
                    details=f"error={exc}",
                )
            )
        await db.flush()
        events = (await db.scalars(select(Event).where(Event.season_id == season.id))).all()

    await db.commit()
    return [EventOut.model_validate(item, from_attributes=True) for item in events]


@router.get("/events/{event_id}/sessions", response_model=list[SessionOut])
async def get_sessions_for_event(event_id: str, db: DbSession) -> Any:
    event = await db.get(Event, event_id)
    if event is None:
        raise HTTPException(status_code=404, detail="event_not_found")
    sessions = (
        await db.scalars(select(Session).where(Session.event_id == event_id).order_by(Session.starts_at.asc()))
    ).all()
    return [SessionOut.model_validate(item, from_attributes=True) for item in sessions]


@router.get("/sessions/{session_id}/questions", response_model=list[PredictionQuestion])
async def get_session_questions(session_id: str, db: DbSession) -> Any:
    session_obj = await db.get(Session, session_id)
    if session_obj is None:
        raise HTTPException(status_code=404, detail="session_not_found")
    questions = (
        await db.scalars(
            select(QuestionInstance)
            .where(QuestionInstance.session_id == session_id)
            .order_by(QuestionInstance.created_at.asc())
        )
    ).all()
    return [PredictionQuestion.model_validate(item, from_attributes=True) for item in questions]


@router.post("/sessions/{session_id}/predictions", response_model=PredictionOut)
async def submit_predictions(
    session_id: str,
    payload: PredictionSubmission,
    db: DbSession,
    user_id: AuthedUserId,
) -> Any:
    session_obj = await db.get(Session, session_id)
    if session_obj is None:
        raise HTTPException(status_code=404, detail="session_not_found")

    if session_obj.state in [SessionState.LOCKED, SessionState.SCORING, SessionState.FINALIZED]:
        raise HTTPException(status_code=409, detail="session_locked")
    if now_utc() >= coerce_utc(session_obj.lock_at):
        session_obj.state = SessionState.LOCKED
        await db.flush()
        await db.commit()
        raise HTTPException(status_code=409, detail="session_locked")

    questions = (
        await db.scalars(select(QuestionInstance).where(QuestionInstance.session_id == session_id))
    ).all()
    question_map = {q.id: q for q in questions}

    if not payload.answers:
        raise HTTPException(status_code=422, detail="prediction_answers_required")

    credits_sum = sum(item.confidence_credits for item in payload.answers)
    if credits_sum != settings.default_confidence_credits:
        raise HTTPException(
            status_code=422,
            detail=f"confidence_credits_must_sum_to_{settings.default_confidence_credits}",
        )

    seen_questions: set[str] = set()
    for item in payload.answers:
        question = question_map.get(item.question_instance_id)
        if question is None:
            raise HTTPException(status_code=422, detail="invalid_question_instance")
        if item.selected_option not in question.options:
            raise HTTPException(status_code=422, detail="invalid_selected_option")
        if item.question_instance_id in seen_questions:
            raise HTTPException(status_code=422, detail="duplicate_question_answer")
        seen_questions.add(item.question_instance_id)

    prediction = await db.scalar(
        select(Prediction).where(Prediction.user_id == user_id, Prediction.session_id == session_id)
    )

    if prediction is None:
        prediction = Prediction(user_id=user_id, session_id=session_id, client_version=payload.client_version)
        db.add(prediction)
        await db.flush()
    else:
        prediction.client_version = payload.client_version
        await db.execute(delete(PredictionAnswer).where(PredictionAnswer.prediction_id == prediction.id))
        await db.execute(
            delete(PredictionConfidenceAllocation).where(
                PredictionConfidenceAllocation.prediction_id == prediction.id
            )
        )

    for item in payload.answers:
        db.add(
            PredictionAnswer(
                prediction_id=prediction.id,
                user_id=user_id,
                question_instance_id=item.question_instance_id,
                selected_option=item.selected_option,
            )
        )
        db.add(
            PredictionConfidenceAllocation(
                prediction_id=prediction.id,
                question_instance_id=item.question_instance_id,
                credits=item.confidence_credits,
            )
        )

    await db.flush()
    await db.refresh(prediction)

    answers = (
        await db.scalars(select(PredictionAnswer).where(PredictionAnswer.prediction_id == prediction.id))
    ).all()
    allocations = (
        await db.scalars(
            select(PredictionConfidenceAllocation).where(
                PredictionConfidenceAllocation.prediction_id == prediction.id
            )
        )
    ).all()
    allocation_map = {a.question_instance_id: a.credits for a in allocations}

    await db.commit()
    return PredictionOut(
        id=prediction.id,
        user_id=prediction.user_id,
        session_id=prediction.session_id,
        client_version=prediction.client_version,
        updated_at=prediction.updated_at,
        answers=[
            {
                "question_instance_id": answer.question_instance_id,
                "selected_option": answer.selected_option,
                "confidence_credits": allocation_map.get(answer.question_instance_id, 0),
            }
            for answer in answers
        ],
    )


@router.get("/users/me/predictions", response_model=list[PredictionOut])
async def get_my_predictions(db: DbSession, user_id: AuthedUserId) -> Any:
    predictions = (
        await db.scalars(
            select(Prediction)
            .where(Prediction.user_id == user_id)
            .order_by(Prediction.updated_at.desc())
        )
    ).all()

    result: list[PredictionOut] = []
    for prediction in predictions:
        answers = (
            await db.scalars(select(PredictionAnswer).where(PredictionAnswer.prediction_id == prediction.id))
        ).all()
        allocations = (
            await db.scalars(
                select(PredictionConfidenceAllocation).where(
                    PredictionConfidenceAllocation.prediction_id == prediction.id
                )
            )
        ).all()
        allocation_map = {a.question_instance_id: a.credits for a in allocations}
        result.append(
            PredictionOut(
                id=prediction.id,
                user_id=prediction.user_id,
                session_id=prediction.session_id,
                client_version=prediction.client_version,
                updated_at=prediction.updated_at,
                answers=[
                    {
                        "question_instance_id": answer.question_instance_id,
                        "selected_option": answer.selected_option,
                        "confidence_credits": allocation_map.get(answer.question_instance_id, 0),
                    }
                    for answer in answers
                ],
            )
        )

    return result


@router.get("/leaderboards/global", response_model=LeaderboardOut)
async def get_global_leaderboard(db: DbSession) -> Any:
    rows = await build_global_leaderboard(db)
    return LeaderboardOut(scope="GLOBAL", rows=rows)


@router.post("/leagues", response_model=LeagueOut, status_code=status.HTTP_201_CREATED)
async def create_league(payload: LeagueCreateIn, db: DbSession, user_id: AuthedUserId) -> Any:
    if not is_name_allowed(payload.name):
        raise HTTPException(status_code=422, detail="league_name_not_allowed")

    join_policy = payload.join_policy
    if join_policy is None:
        join_policy = JoinPolicy.INVITE_ONLY if payload.visibility == LeagueVisibility.PRIVATE else JoinPolicy.OPEN

    invite_code = generate_code() if payload.visibility == LeagueVisibility.PRIVATE else None
    league = League(
        name=payload.name,
        visibility=payload.visibility,
        join_policy=join_policy,
        moderation_state=ModerationState.ACTIVE,
        invite_code=invite_code,
        created_by=user_id,
    )
    db.add(league)
    await db.flush()

    db.add(LeagueMember(league_id=league.id, user_id=user_id, role=MemberRole.OWNER))
    await db.commit()
    return LeagueOut.model_validate(league, from_attributes=True)


@router.get("/leagues/public", response_model=list[LeagueOut])
async def list_public_leagues(db: DbSession) -> Any:
    leagues = (
        await db.scalars(
            select(League).where(
                League.visibility == LeagueVisibility.PUBLIC,
                League.moderation_state == ModerationState.ACTIVE,
            )
        )
    ).all()
    return [LeagueOut.model_validate(item, from_attributes=True) for item in leagues]


@router.post("/leagues/{league_id}/join", status_code=status.HTTP_204_NO_CONTENT)
async def join_league(
    league_id: str,
    payload: LeagueJoinIn,
    db: DbSession,
    user_id: AuthedUserId,
) -> None:
    league = await db.get(League, league_id)
    if league is None:
        raise HTTPException(status_code=404, detail="league_not_found")

    existing = await db.scalar(
        select(LeagueMember).where(LeagueMember.league_id == league.id, LeagueMember.user_id == user_id)
    )
    if existing is not None:
        return

    if league.visibility == LeagueVisibility.PRIVATE or league.join_policy == JoinPolicy.INVITE_ONLY:
        code = payload.invite_code
        if not code:
            raise HTTPException(status_code=403, detail="invite_code_required")

        invite = await db.scalar(
            select(LeagueInvite).where(LeagueInvite.league_id == league.id, LeagueInvite.code == code)
        )
        invite_code_match = league.invite_code == code
        invite_is_valid = invite is not None and (
            invite.expires_at is None or invite.expires_at >= now_utc()
        )
        if not invite_code_match and not invite_is_valid:
            raise HTTPException(status_code=403, detail="invalid_invite_code")

    db.add(LeagueMember(league_id=league.id, user_id=user_id, role=MemberRole.MEMBER))
    await db.commit()


@router.get("/leagues/{league_id}/leaderboard", response_model=LeaderboardOut)
async def league_leaderboard(league_id: str, db: DbSession, user_id: AuthedUserId) -> Any:
    member = await db.scalar(
        select(LeagueMember).where(LeagueMember.league_id == league_id, LeagueMember.user_id == user_id)
    )
    if member is None:
        raise HTTPException(status_code=403, detail="not_a_league_member")

    rows = await build_league_leaderboard(db, league_id)
    return LeaderboardOut(scope=f"LEAGUE:{league_id}", rows=rows)


@router.post("/leagues/{league_id}/invites", response_model=LeagueInviteOut)
async def create_league_invite(league_id: str, db: DbSession, user_id: AuthedUserId) -> Any:
    member = await db.scalar(
        select(LeagueMember).where(LeagueMember.league_id == league_id, LeagueMember.user_id == user_id)
    )
    if member is None or member.role not in [MemberRole.OWNER, MemberRole.ADMIN]:
        raise HTTPException(status_code=403, detail="insufficient_permissions")

    invite = LeagueInvite(league_id=league_id, code=generate_code(10), created_by=user_id)
    db.add(invite)
    await db.commit()
    return LeagueInviteOut.model_validate(invite, from_attributes=True)


@router.get("/events/{event_id}/ai-preview", response_model=AIPreviewOut)
async def ai_preview(event_id: str, db: DbSession) -> Any:
    preview = await get_or_create_preview(db, event_id)
    if preview is None:
        raise HTTPException(status_code=404, detail="event_not_found")
    await db.commit()
    return AIPreviewOut.model_validate(preview, from_attributes=True)


@router.get("/sessions/{session_id}/ai-insights", response_model=AIInsightOut)
async def ai_insight(session_id: str, db: DbSession) -> Any:
    insight = await get_or_create_session_insight(db, session_id)
    if insight is None:
        raise HTTPException(status_code=404, detail="session_not_found")
    await db.commit()
    return AIInsightOut.model_validate(insight, from_attributes=True)


@router.post("/reports", status_code=status.HTTP_204_NO_CONTENT)
async def create_report(payload: ReportIn, db: DbSession, user_id: AuthedUserId) -> None:
    report = ModerationReport(
        reporter_id=user_id,
        target_type=payload.target_type,
        target_id=payload.target_id,
        reason=payload.reason,
    )
    db.add(report)
    await db.commit()


@router.post("/admin/rules", response_model=RuleOut)
async def upsert_rule(
    payload: RuleUpsertIn,
    db: DbSession,
    user_id: AuthedUserId,
    _: AdminAuthorized,
) -> Any:
    rule = await db.scalar(select(ScoringRule).where(ScoringRule.name == payload.name))
    if rule is None:
        rule = ScoringRule(
            name=payload.name,
            question_type=payload.question_type,
            base_points=payload.base_points,
            metadata_json=payload.metadata_json,
            created_by=user_id,
        )
        db.add(rule)
    else:
        rule.question_type = payload.question_type
        rule.base_points = payload.base_points
        rule.metadata_json = payload.metadata_json

    await db.commit()
    return RuleOut.model_validate(rule, from_attributes=True)


@router.post("/admin/scoring/run", response_model=ScoringRunOut)
async def admin_run_scoring(
    payload: ScoringRunIn,
    db: DbSession,
    user_id: AuthedUserId,
    _: AdminAuthorized,
) -> Any:
    idempotency_key = f"admin-score:{payload.session_id}"
    try:
        ingestion = {"resolved": 0, "unresolved": 0}
        target_session = await db.get(Session, payload.session_id)
        if target_session is not None and target_session.external_id:
            ingestion = await ingest_session_question_outcomes(db, target_session)

        created = await run_session_scoring(db, payload.session_id, initiated_by=user_id)
        await record_job_run(
            db,
            idempotency_key=idempotency_key,
            job_type="admin_scoring_run",
            status=JobStatus.SUCCESS,
            payload_json=payload.model_dump(),
            result_json={
                "entries_created": created,
                "resolved_questions": ingestion["resolved"],
                "unresolved_questions": ingestion["unresolved"],
            },
        )
    except Exception as exc:
        await record_job_run(
            db,
            idempotency_key=idempotency_key,
            job_type="admin_scoring_run",
            status=JobStatus.FAILED,
            payload_json=payload.model_dump(),
            error_message=str(exc),
        )
        await db.commit()
        raise

    await db.commit()
    return ScoringRunOut(session_id=payload.session_id, entries_created=created, finalized=True)
