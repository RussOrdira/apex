from __future__ import annotations

from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest
from sqlalchemy import func, select

from apex_predict.enums import QuestionType, SessionState, SessionType
from apex_predict.models import (
    Event,
    Prediction,
    PredictionAnswer,
    PredictionConfidenceAllocation,
    Profile,
    QuestionInstance,
    ScoreEntry,
    ScoringRule,
    Season,
    Session,
    User,
)
from apex_predict.services.ingestion import auto_finalize_ended_sessions


class FakeProviderRouter:
    async def fetch_session_facts(self, session_external_id: str) -> tuple[str, dict]:
        assert session_external_id == "openf1-session-77"
        return (
            "fake-openf1",
            {
                "winner": "NOR",
                "pole": "VER",
                "top5": ["NOR", "VER", "LEC", "PIA", "HAM"],
                "dnf_driver_codes": ["GAS"],
                "fastest_lap": "PIA",
                "safety_car": True,
                "first_pit_stop_team": "MCLAREN",
                "first_safety_car_lap": 7,
                "constructor_points": {
                    "MCLAREN": 43,
                    "RED_BULL_RACING": 33,
                    "FERRARI": 27,
                    "WILLIAMS": 12,
                    "HAAS": 8,
                },
                "midfield_constructor": "WILLIAMS",
            },
        )


def now_utc() -> datetime:
    return datetime.now(tz=timezone.utc)


@pytest.mark.anyio
async def test_auto_finalize_session_ingests_all_categories_and_scores(db_session):
    user = User(id="scorer-user", email="scorer@example.com")
    db_session.add(user)
    db_session.add(Profile(user_id=user.id, username="scorer"))

    season = Season(id=str(uuid4()), year=2026, is_current=True)
    db_session.add(season)

    start = now_utc() - timedelta(days=1)
    event = Event(
        id=str(uuid4()),
        season_id=season.id,
        external_id="openf1-meeting-1",
        name="Italian GP",
        slug=f"2026-italian-{uuid4().hex[:6]}",
        country="Italy",
        start_at=start,
        end_at=start + timedelta(hours=6),
    )
    db_session.add(event)

    session = Session(
        id=str(uuid4()),
        event_id=event.id,
        external_id="openf1-session-77",
        provider_name="openf1",
        name="Race",
        session_type=SessionType.RACE,
        state=SessionState.LOCKED,
        starts_at=start,
        lock_at=start + timedelta(minutes=5),
        ends_at=start + timedelta(hours=2),
    )
    db_session.add(session)

    question_specs = [
        (QuestionType.POLE, ["VER", "NOR"]),
        (QuestionType.WINNER, ["NOR", "VER"]),
        (QuestionType.TOP5, ["PIA", "HAM", "NOR"]),
        (QuestionType.DNF, ["GAS", "HUL"]),
        (QuestionType.FASTEST_LAP, ["PIA", "LEC"]),
        (QuestionType.SAFETY_CAR, ["YES", "NO"]),
        (QuestionType.MIDFIELD_CONSTRUCTOR, ["WILLIAMS", "HAAS"]),
        (QuestionType.FIRST_PIT_STOP_TEAM, ["MCLAREN", "FERRARI"]),
        (QuestionType.FIRST_SAFETY_CAR_LAP, ["7", "10", "NONE"]),
    ]

    rule_by_type: dict[QuestionType, ScoringRule] = {}
    for qtype, _ in question_specs:
        rule = ScoringRule(
            id=str(uuid4()),
            name=f"rule-{qtype.value}-{uuid4().hex[:6]}",
            question_type=qtype,
            base_points=10,
        )
        db_session.add(rule)
        rule_by_type[qtype] = rule

    await db_session.flush()

    question_rows: list[QuestionInstance] = []
    for qtype, options in question_specs:
        question = QuestionInstance(
            id=str(uuid4()),
            session_id=session.id,
            question_type=qtype,
            prompt=f"Prompt {qtype.value}",
            options=options,
            lock_at=session.lock_at,
            scoring_rule_id=rule_by_type[qtype].id,
        )
        db_session.add(question)
        question_rows.append(question)

    prediction = Prediction(
        id=str(uuid4()),
        user_id=user.id,
        session_id=session.id,
        client_version="test",
    )
    db_session.add(prediction)
    await db_session.flush()

    answer_by_type = {
        QuestionType.POLE: "VER",
        QuestionType.WINNER: "NOR",
        QuestionType.TOP5: "NOR",
        QuestionType.DNF: "GAS",
        QuestionType.FASTEST_LAP: "PIA",
        QuestionType.SAFETY_CAR: "YES",
        QuestionType.MIDFIELD_CONSTRUCTOR: "WILLIAMS",
        QuestionType.FIRST_PIT_STOP_TEAM: "MCLAREN",
        QuestionType.FIRST_SAFETY_CAR_LAP: "7",
    }

    credits_by_type = {
        QuestionType.POLE: 10,
        QuestionType.WINNER: 10,
        QuestionType.TOP5: 10,
        QuestionType.DNF: 10,
        QuestionType.FASTEST_LAP: 10,
        QuestionType.SAFETY_CAR: 10,
        QuestionType.MIDFIELD_CONSTRUCTOR: 10,
        QuestionType.FIRST_PIT_STOP_TEAM: 10,
        QuestionType.FIRST_SAFETY_CAR_LAP: 20,
    }

    for question in question_rows:
        db_session.add(
            PredictionAnswer(
                id=str(uuid4()),
                prediction_id=prediction.id,
                user_id=user.id,
                question_instance_id=question.id,
                selected_option=answer_by_type[question.question_type],
            )
        )
        db_session.add(
            PredictionConfidenceAllocation(
                id=str(uuid4()),
                prediction_id=prediction.id,
                question_instance_id=question.id,
                credits=credits_by_type[question.question_type],
            )
        )

    await db_session.commit()

    result = await auto_finalize_ended_sessions(
        db_session,
        initiated_by="test:auto",
        provider_router=FakeProviderRouter(),
    )
    await db_session.commit()

    assert result["candidates"] == 1
    assert result["finalized"] == 1
    assert result["failed"] == 0

    refreshed_session = await db_session.get(Session, session.id)
    assert refreshed_session is not None
    assert refreshed_session.state == SessionState.FINALIZED

    resolved_count = await db_session.scalar(
        select(func.count())
        .select_from(QuestionInstance)
        .where(QuestionInstance.session_id == session.id, QuestionInstance.correct_option.is_not(None))
    )
    assert resolved_count == 9

    score_count = await db_session.scalar(
        select(func.count()).select_from(ScoreEntry).where(ScoreEntry.session_id == session.id)
    )
    assert score_count == 9
