from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from apex_predict.db import Base
from apex_predict.enums import (
    JobStatus,
    JoinPolicy,
    LeaderboardScope,
    LeagueVisibility,
    MemberRole,
    ModerationState,
    QuestionType,
    ReportStatus,
    SessionState,
    SessionType,
)


def utc_now() -> datetime:
    return datetime.now(tz=timezone.utc)


def uuid_str() -> str:
    return str(uuid4())


class User(Base):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_str)
    email: Mapped[str | None] = mapped_column(String(320), nullable=True, unique=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)

    profile: Mapped[Profile | None] = relationship(back_populates="user", uselist=False)


class Profile(Base):
    __tablename__ = "profiles"

    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"), primary_key=True)
    username: Mapped[str] = mapped_column(String(50), unique=True)
    avatar_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    total_points: Mapped[float] = mapped_column(Float, default=0.0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)

    user: Mapped[User] = relationship(back_populates="profile")


class Season(Base):
    __tablename__ = "seasons"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_str)
    year: Mapped[int] = mapped_column(Integer, unique=True)
    is_current: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)


class Event(Base):
    __tablename__ = "events"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_str)
    season_id: Mapped[str] = mapped_column(String(36), ForeignKey("seasons.id"), index=True)
    external_id: Mapped[str | None] = mapped_column(String(40), nullable=True, index=True)
    name: Mapped[str] = mapped_column(String(120))
    slug: Mapped[str] = mapped_column(String(120), unique=True)
    country: Mapped[str] = mapped_column(String(80))
    start_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    end_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)


class Session(Base):
    __tablename__ = "sessions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_str)
    event_id: Mapped[str] = mapped_column(String(36), ForeignKey("events.id"), index=True)
    external_id: Mapped[str | None] = mapped_column(String(40), nullable=True, index=True)
    provider_name: Mapped[str | None] = mapped_column(String(40), nullable=True)
    name: Mapped[str] = mapped_column(String(120))
    session_type: Mapped[SessionType] = mapped_column(Enum(SessionType), index=True)
    state: Mapped[SessionState] = mapped_column(Enum(SessionState), default=SessionState.SCHEDULED, index=True)
    starts_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    lock_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    ends_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)


class Driver(Base):
    __tablename__ = "drivers"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_str)
    code: Mapped[str] = mapped_column(String(8), unique=True)
    full_name: Mapped[str] = mapped_column(String(120))


class Constructor(Base):
    __tablename__ = "constructors"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_str)
    code: Mapped[str] = mapped_column(String(12), unique=True)
    name: Mapped[str] = mapped_column(String(120))


class ScoringRule(Base):
    __tablename__ = "scoring_rules"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_str)
    name: Mapped[str] = mapped_column(String(120), unique=True)
    question_type: Mapped[QuestionType] = mapped_column(Enum(QuestionType), index=True)
    base_points: Mapped[int] = mapped_column(Integer)
    metadata_json: Mapped[dict] = mapped_column(JSON, default=dict)
    created_by: Mapped[str | None] = mapped_column(String(36), ForeignKey("users.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)


class QuestionTemplate(Base):
    __tablename__ = "question_templates"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_str)
    session_type: Mapped[SessionType] = mapped_column(Enum(SessionType), index=True)
    question_type: Mapped[QuestionType] = mapped_column(Enum(QuestionType), index=True)
    prompt: Mapped[str] = mapped_column(String(500))
    options: Mapped[list[str]] = mapped_column(JSON)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)


class QuestionInstance(Base):
    __tablename__ = "question_instances"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_str)
    session_id: Mapped[str] = mapped_column(String(36), ForeignKey("sessions.id"), index=True)
    question_type: Mapped[QuestionType] = mapped_column(Enum(QuestionType), index=True)
    prompt: Mapped[str] = mapped_column(String(500))
    options: Mapped[list[str]] = mapped_column(JSON)
    lock_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    scoring_rule_id: Mapped[str] = mapped_column(String(36), ForeignKey("scoring_rules.id"), index=True)
    correct_option: Mapped[str | None] = mapped_column(String(120), nullable=True)
    metadata_json: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)


class Prediction(Base):
    __tablename__ = "predictions"
    __table_args__ = (UniqueConstraint("user_id", "session_id", name="uq_prediction_user_session"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_str)
    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"), index=True)
    session_id: Mapped[str] = mapped_column(String(36), ForeignKey("sessions.id"), index=True)
    client_version: Mapped[str | None] = mapped_column(String(40), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, onupdate=utc_now)

    answers: Mapped[list[PredictionAnswer]] = relationship(
        back_populates="prediction", cascade="all, delete-orphan"
    )
    confidence_allocations: Mapped[list[PredictionConfidenceAllocation]] = relationship(
        back_populates="prediction", cascade="all, delete-orphan"
    )


class PredictionAnswer(Base):
    __tablename__ = "prediction_answers"
    __table_args__ = (
        UniqueConstraint("user_id", "question_instance_id", name="uq_prediction_user_question"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_str)
    prediction_id: Mapped[str] = mapped_column(String(36), ForeignKey("predictions.id"), index=True)
    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"), index=True)
    question_instance_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("question_instances.id"), index=True
    )
    selected_option: Mapped[str] = mapped_column(String(120))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)

    prediction: Mapped[Prediction] = relationship(back_populates="answers")


class PredictionConfidenceAllocation(Base):
    __tablename__ = "prediction_confidence_allocations"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_str)
    prediction_id: Mapped[str] = mapped_column(String(36), ForeignKey("predictions.id"), index=True)
    question_instance_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("question_instances.id"), index=True
    )
    credits: Mapped[int] = mapped_column(Integer)

    prediction: Mapped[Prediction] = relationship(back_populates="confidence_allocations")


class ScoreEntry(Base):
    __tablename__ = "score_entries"
    __table_args__ = (
        UniqueConstraint(
            "user_id",
            "session_id",
            "question_instance_id",
            "reason",
            name="uq_score_entry_reason",
        ),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_str)
    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"), index=True)
    session_id: Mapped[str] = mapped_column(String(36), ForeignKey("sessions.id"), index=True)
    question_instance_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("question_instances.id"), nullable=True, index=True
    )
    base_points: Mapped[float] = mapped_column(Numeric(10, 2), default=0)
    confidence_multiplier: Mapped[float] = mapped_column(Numeric(10, 2), default=1)
    awarded_points: Mapped[float] = mapped_column(Numeric(10, 2), default=0)
    reason: Mapped[str] = mapped_column(String(120), default="SESSION_SCORE")
    is_correction: Mapped[bool] = mapped_column(Boolean, default=False)
    metadata_json: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)


class LeaderboardSnapshot(Base):
    __tablename__ = "leaderboard_snapshots"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_str)
    scope: Mapped[LeaderboardScope] = mapped_column(Enum(LeaderboardScope), index=True)
    scope_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)
    session_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("sessions.id"), nullable=True)
    computed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    rows_json: Mapped[list[dict]] = mapped_column(JSON)


class League(Base):
    __tablename__ = "leagues"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_str)
    name: Mapped[str] = mapped_column(String(120), index=True)
    visibility: Mapped[LeagueVisibility] = mapped_column(Enum(LeagueVisibility), index=True)
    join_policy: Mapped[JoinPolicy] = mapped_column(Enum(JoinPolicy), index=True)
    moderation_state: Mapped[ModerationState] = mapped_column(
        Enum(ModerationState), default=ModerationState.ACTIVE, index=True
    )
    invite_code: Mapped[str | None] = mapped_column(String(12), nullable=True, unique=True)
    created_by: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)


class LeagueMember(Base):
    __tablename__ = "league_members"
    __table_args__ = (UniqueConstraint("league_id", "user_id", name="uq_league_member"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_str)
    league_id: Mapped[str] = mapped_column(String(36), ForeignKey("leagues.id"), index=True)
    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"), index=True)
    role: Mapped[MemberRole] = mapped_column(Enum(MemberRole), default=MemberRole.MEMBER)
    joined_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)


class LeagueInvite(Base):
    __tablename__ = "league_invites"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_str)
    league_id: Mapped[str] = mapped_column(String(36), ForeignKey("leagues.id"), index=True)
    code: Mapped[str] = mapped_column(String(12), unique=True)
    created_by: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"), index=True)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)


class LeagueSnapshot(Base):
    __tablename__ = "league_snapshots"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_str)
    league_id: Mapped[str] = mapped_column(String(36), ForeignKey("leagues.id"), index=True)
    computed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    rows_json: Mapped[list[dict]] = mapped_column(JSON)


class AIPreview(Base):
    __tablename__ = "ai_previews"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_str)
    event_id: Mapped[str] = mapped_column(String(36), ForeignKey("events.id"), unique=True, index=True)
    summary: Mapped[str] = mapped_column(Text)
    confidence_band: Mapped[str] = mapped_column(String(20))
    data_sources: Mapped[list[str]] = mapped_column(JSON)
    generated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)


class AIInsight(Base):
    __tablename__ = "ai_insights"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_str)
    session_id: Mapped[str] = mapped_column(String(36), ForeignKey("sessions.id"), index=True)
    question_instance_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("question_instances.id"), nullable=True
    )
    explanation: Mapped[str] = mapped_column(Text)
    confidence_band: Mapped[str] = mapped_column(String(20))
    data_sources: Mapped[list[str]] = mapped_column(JSON)
    generated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)


class AIGenerationLog(Base):
    __tablename__ = "ai_generation_logs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_str)
    entity_type: Mapped[str] = mapped_column(String(40), index=True)
    entity_id: Mapped[str] = mapped_column(String(36), index=True)
    status: Mapped[JobStatus] = mapped_column(Enum(JobStatus), default=JobStatus.SUCCESS)
    prompt_hash: Mapped[str] = mapped_column(String(64))
    provider: Mapped[str] = mapped_column(String(40), default="heuristic")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)


class ProviderSyncLog(Base):
    __tablename__ = "provider_sync_logs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_str)
    provider_name: Mapped[str] = mapped_column(String(40), index=True)
    resource: Mapped[str] = mapped_column(String(40), index=True)
    status: Mapped[JobStatus] = mapped_column(Enum(JobStatus), index=True)
    details: Mapped[str | None] = mapped_column(Text, nullable=True)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class JobRun(Base):
    __tablename__ = "job_runs"
    __table_args__ = (UniqueConstraint("idempotency_key", name="uq_job_run_idempotency"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_str)
    idempotency_key: Mapped[str] = mapped_column(String(120), index=True)
    job_type: Mapped[str] = mapped_column(String(80), index=True)
    status: Mapped[JobStatus] = mapped_column(Enum(JobStatus), default=JobStatus.PENDING)
    payload_json: Mapped[dict] = mapped_column(JSON, default=dict)
    result_json: Mapped[dict] = mapped_column(JSON, default=dict)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class ModerationReport(Base):
    __tablename__ = "moderation_reports"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_str)
    reporter_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"), index=True)
    target_type: Mapped[str] = mapped_column(String(40), index=True)
    target_id: Mapped[str] = mapped_column(String(36), index=True)
    reason: Mapped[str] = mapped_column(String(500))
    status: Mapped[ReportStatus] = mapped_column(Enum(ReportStatus), default=ReportStatus.OPEN, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)


class ModerationAction(Base):
    __tablename__ = "moderation_actions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_str)
    report_id: Mapped[str] = mapped_column(String(36), ForeignKey("moderation_reports.id"), index=True)
    actor_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"), index=True)
    action: Mapped[str] = mapped_column(String(80))
    notes: Mapped[str | None] = mapped_column(String(500), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_str)
    actor_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("users.id"), nullable=True)
    action: Mapped[str] = mapped_column(String(120), index=True)
    entity_type: Mapped[str] = mapped_column(String(60), index=True)
    entity_id: Mapped[str] = mapped_column(String(36), index=True)
    metadata_json: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
