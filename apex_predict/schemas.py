from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field

from apex_predict.enums import JoinPolicy, LeagueVisibility, ModerationState, QuestionType, SessionState


class SeasonOut(BaseModel):
    id: str
    year: int
    is_current: bool


class EventOut(BaseModel):
    id: str
    season_id: str
    external_id: str | None = None
    name: str
    slug: str
    country: str
    start_at: datetime
    end_at: datetime


class SessionOut(BaseModel):
    id: str
    event_id: str
    external_id: str | None = None
    provider_name: str | None = None
    name: str
    session_type: str
    state: SessionState
    starts_at: datetime
    lock_at: datetime
    ends_at: datetime


class PredictionQuestion(BaseModel):
    id: str
    question_type: QuestionType
    prompt: str
    options: list[str]
    lock_at: datetime
    scoring_rule_id: str


class PredictionAnswerIn(BaseModel):
    question_instance_id: str
    selected_option: str
    confidence_credits: int = Field(ge=0)


class PredictionSubmission(BaseModel):
    answers: list[PredictionAnswerIn]
    client_version: str | None = None


class PredictionAnswerOut(BaseModel):
    question_instance_id: str
    selected_option: str
    confidence_credits: int


class PredictionOut(BaseModel):
    id: str
    user_id: str
    session_id: str
    client_version: str | None
    updated_at: datetime
    answers: list[PredictionAnswerOut]


class LeaderboardRow(BaseModel):
    user_id: str
    username: str
    total_points: float
    rank: int


class LeaderboardOut(BaseModel):
    scope: str
    rows: list[LeaderboardRow]


class LeagueCreateIn(BaseModel):
    name: str = Field(min_length=3, max_length=120)
    visibility: LeagueVisibility
    join_policy: JoinPolicy | None = None


class LeagueOut(BaseModel):
    id: str
    name: str
    visibility: LeagueVisibility
    join_policy: JoinPolicy
    moderation_state: ModerationState
    invite_code: str | None
    created_by: str
    created_at: datetime


class LeagueJoinIn(BaseModel):
    invite_code: str | None = None


class LeagueInviteOut(BaseModel):
    id: str
    league_id: str
    code: str
    expires_at: datetime | None


class AIInsightOut(BaseModel):
    id: str
    confidence_band: str
    explanation: str
    data_sources: list[str]
    generated_at: datetime


class AIPreviewOut(BaseModel):
    id: str
    event_id: str
    summary: str
    confidence_band: str
    data_sources: list[str]
    generated_at: datetime


class ReportIn(BaseModel):
    target_type: str = Field(min_length=2, max_length=40)
    target_id: str = Field(min_length=2, max_length=36)
    reason: str = Field(min_length=5, max_length=500)


class RuleUpsertIn(BaseModel):
    name: str = Field(min_length=3, max_length=120)
    question_type: QuestionType
    base_points: int = Field(gt=0)
    metadata_json: dict = Field(default_factory=dict)


class RuleOut(BaseModel):
    id: str
    name: str
    question_type: QuestionType
    base_points: int
    metadata_json: dict


class ScoringRunIn(BaseModel):
    session_id: str


class ScoringRunOut(BaseModel):
    session_id: str
    entries_created: int
    finalized: bool
