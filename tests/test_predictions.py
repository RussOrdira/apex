from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import update

from apex_predict.enums import SessionState
from apex_predict.models import Session


def now_utc() -> datetime:
    return datetime.now(tz=timezone.utc)


@pytest.mark.anyio
async def test_submit_predictions_success(client, auth_headers, seeded_core):
    payload = {
        "client_version": "ios-0.1.0",
        "answers": [
            {
                "question_instance_id": seeded_core["question_one"],
                "selected_option": "VER",
                "confidence_credits": 60,
            },
            {
                "question_instance_id": seeded_core["question_two"],
                "selected_option": "NOR",
                "confidence_credits": 40,
            },
        ],
    }

    response = await client.post(
        f"/v1/sessions/{seeded_core['session_id']}/predictions",
        json=payload,
        headers=auth_headers,
    )
    assert response.status_code == 200
    body = response.json()
    assert body["session_id"] == seeded_core["session_id"]
    assert len(body["answers"]) == 2


@pytest.mark.anyio
async def test_submit_predictions_requires_100_credits(client, auth_headers, seeded_core):
    payload = {
        "client_version": "ios-0.1.0",
        "answers": [
            {
                "question_instance_id": seeded_core["question_one"],
                "selected_option": "VER",
                "confidence_credits": 30,
            },
            {
                "question_instance_id": seeded_core["question_two"],
                "selected_option": "NOR",
                "confidence_credits": 40,
            },
        ],
    }

    response = await client.post(
        f"/v1/sessions/{seeded_core['session_id']}/predictions",
        json=payload,
        headers=auth_headers,
    )
    assert response.status_code == 422
    assert "confidence_credits_must_sum_to_100" in response.json()["detail"]


@pytest.mark.anyio
async def test_submit_predictions_rejected_when_locked(client, auth_headers, seeded_core, db_session):
    await db_session.execute(
        update(Session)
        .where(Session.id == seeded_core["session_id"])
        .values(lock_at=now_utc() - timedelta(minutes=2), state=SessionState.OPEN)
    )
    await db_session.commit()

    payload = {
        "answers": [
            {
                "question_instance_id": seeded_core["question_one"],
                "selected_option": "VER",
                "confidence_credits": 50,
            },
            {
                "question_instance_id": seeded_core["question_two"],
                "selected_option": "NOR",
                "confidence_credits": 50,
            },
        ]
    }

    response = await client.post(
        f"/v1/sessions/{seeded_core['session_id']}/predictions",
        json=payload,
        headers=auth_headers,
    )
    assert response.status_code == 409
    assert response.json()["detail"] == "session_locked"
