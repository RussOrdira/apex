from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

import pytest

from apex_predict.enums import QuestionType
from apex_predict.models import QuestionInstance
from apex_predict.services.ingestion import resolve_question_option


def _question(question_type: QuestionType, options: list[str]) -> QuestionInstance:
    now = datetime.now(tz=timezone.utc)
    return QuestionInstance(
        id=str(uuid4()),
        session_id=str(uuid4()),
        question_type=question_type,
        prompt=f"prompt-{question_type.value}",
        options=options,
        lock_at=now,
        scoring_rule_id=str(uuid4()),
        created_at=now,
    )


@pytest.mark.unit
@pytest.mark.parametrize(
    ("question_type", "options", "facts", "expected"),
    [
        (QuestionType.POLE, ["VER", "NOR"], {"pole": "VER"}, "VER"),
        (QuestionType.WINNER, ["VER", "NOR"], {"winner": "NOR"}, "NOR"),
        (QuestionType.TOP5, ["HAM", "PIA", "RUS"], {"top5": ["PIA", "NOR"]}, "PIA"),
        (QuestionType.DNF, ["HUL", "GAS"], {"dnf_driver_codes": ["GAS"]}, "GAS"),
        (QuestionType.FASTEST_LAP, ["VER", "NOR"], {"fastest_lap": "NOR"}, "NOR"),
        (QuestionType.SAFETY_CAR, ["YES", "NO"], {"safety_car": True}, "YES"),
        (
            QuestionType.MIDFIELD_CONSTRUCTOR,
            ["WILLIAMS", "HAAS"],
            {"midfield_constructor": "WILLIAMS"},
            "WILLIAMS",
        ),
        (
            QuestionType.FIRST_PIT_STOP_TEAM,
            ["FERRARI", "MCLAREN"],
            {"first_pit_stop_team": "FERRARI"},
            "FERRARI",
        ),
        (
            QuestionType.FIRST_SAFETY_CAR_LAP,
            ["5", "10", "NONE"],
            {"first_safety_car_lap": 10},
            "10",
        ),
    ],
)
def test_resolve_question_option_all_categories(
    question_type: QuestionType,
    options: list[str],
    facts: dict,
    expected: str,
) -> None:
    question = _question(question_type, options)
    assert resolve_question_option(question, facts) == expected


@pytest.mark.unit
def test_resolve_question_option_handles_missing_safety_car_lap() -> None:
    question = _question(QuestionType.FIRST_SAFETY_CAR_LAP, ["NONE", "5", "10"])
    facts = {"first_safety_car_lap": None}
    assert resolve_question_option(question, facts) == "NONE"
