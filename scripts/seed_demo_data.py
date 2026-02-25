from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone

from sqlalchemy import select

from apex_predict.db import AsyncSessionLocal, init_db
from apex_predict.enums import QuestionType, SessionState, SessionType
from apex_predict.models import Event, QuestionInstance, ScoringRule, Season, Session


def now_utc() -> datetime:
    return datetime.now(tz=timezone.utc)


async def main() -> None:
    await init_db()

    async with AsyncSessionLocal() as db:
        season = await db.scalar(select(Season).where(Season.is_current.is_(True)))
        if season is None:
            season = Season(year=now_utc().year, is_current=True)
            db.add(season)
            await db.flush()

        event = await db.scalar(select(Event).where(Event.slug == f"{season.year}-australian-gp"))
        if event is None:
            start = now_utc() + timedelta(days=7)
            event = Event(
                season_id=season.id,
                external_id="demo-meeting-1",
                name="Australian Grand Prix",
                slug=f"{season.year}-australian-gp",
                country="Australia",
                start_at=start,
                end_at=start + timedelta(days=3),
            )
            db.add(event)
            await db.flush()

        session = await db.scalar(
            select(Session).where(
                Session.event_id == event.id,
                Session.session_type == SessionType.QUALIFYING,
            )
        )
        if session is None:
            start = event.start_at + timedelta(days=1)
            session = Session(
                event_id=event.id,
                external_id="demo-session-quali-1",
                provider_name="openf1",
                name="Qualifying",
                session_type=SessionType.QUALIFYING,
                state=SessionState.OPEN,
                starts_at=start,
                lock_at=start + timedelta(minutes=5),
                ends_at=start + timedelta(hours=1),
            )
            db.add(session)
            await db.flush()

        rule_specs = [
            ("Pole Base", QuestionType.POLE, 20),
            ("Winner Base", QuestionType.WINNER, 25),
            ("Top5 Base", QuestionType.TOP5, 30),
            ("DNF Base", QuestionType.DNF, 15),
            ("Fastest Lap Base", QuestionType.FASTEST_LAP, 10),
            ("Safety Car Base", QuestionType.SAFETY_CAR, 8),
        ]
        rule_by_type: dict[QuestionType, ScoringRule] = {}

        for name, qtype, points in rule_specs:
            rule = await db.scalar(select(ScoringRule).where(ScoringRule.name == name))
            if rule is None:
                rule = ScoringRule(name=name, question_type=qtype, base_points=points)
                db.add(rule)
                await db.flush()
            rule_by_type[qtype] = rule

        questions = [
            (QuestionType.POLE, "Who takes pole?", ["VER", "NOR", "LEC"], "VER"),
            (QuestionType.WINNER, "Who wins race?", ["VER", "NOR", "LEC"], "NOR"),
            (
                QuestionType.TOP5,
                "Which driver finishes top 5?",
                ["HAM", "RUS", "ALO", "PIA"],
                "PIA",
            ),
            (QuestionType.DNF, "Which driver DNFs?", ["SAR", "HUL", "GAS"], "GAS"),
            (
                QuestionType.FASTEST_LAP,
                "Who gets fastest lap?",
                ["VER", "NOR", "LEC"],
                "NOR",
            ),
            (QuestionType.SAFETY_CAR, "Safety car deployed?", ["YES", "NO"], "YES"),
        ]

        for qtype, prompt, options, correct in questions:
            exists = await db.scalar(
                select(QuestionInstance).where(
                    QuestionInstance.session_id == session.id,
                    QuestionInstance.prompt == prompt,
                )
            )
            if exists is None:
                db.add(
                    QuestionInstance(
                        session_id=session.id,
                        question_type=qtype,
                        prompt=prompt,
                        options=options,
                        lock_at=session.lock_at,
                        scoring_rule_id=rule_by_type[qtype].id,
                        correct_option=correct,
                    )
                )

        await db.commit()


if __name__ == "__main__":
    asyncio.run(main())
