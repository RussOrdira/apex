from __future__ import annotations

import pytest
from sqlalchemy import func, select

from apex_predict.enums import LeaderboardScope
from apex_predict.models import LeaderboardSnapshot, LeagueSnapshot, ScoreEntry


@pytest.mark.anyio
async def test_admin_scoring_idempotent(client, auth_headers, admin_headers, seeded_core, db_session):
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

    submit = await client.post(
        f"/v1/sessions/{seeded_core['session_id']}/predictions",
        json=payload,
        headers=auth_headers,
    )
    assert submit.status_code == 200

    first = await client.post(
        "/v1/admin/scoring/run",
        json={"session_id": seeded_core["session_id"]},
        headers=admin_headers,
    )
    assert first.status_code == 200
    assert first.json()["entries_created"] == 2

    second = await client.post(
        "/v1/admin/scoring/run",
        json={"session_id": seeded_core["session_id"]},
        headers=admin_headers,
    )
    assert second.status_code == 200
    assert second.json()["entries_created"] == 0

    count = await db_session.scalar(select(func.count()).select_from(ScoreEntry))
    assert count == 2

    global_snapshot_count = await db_session.scalar(
        select(func.count())
        .select_from(LeaderboardSnapshot)
        .where(
            LeaderboardSnapshot.scope == LeaderboardScope.GLOBAL,
            LeaderboardSnapshot.session_id == seeded_core["session_id"],
        )
    )
    assert global_snapshot_count == 1


@pytest.mark.anyio
async def test_global_leaderboard_returns_scored_user(client, auth_headers, admin_headers, seeded_core):
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

    await client.post(
        f"/v1/sessions/{seeded_core['session_id']}/predictions",
        json=payload,
        headers=auth_headers,
    )
    await client.post(
        "/v1/admin/scoring/run",
        json={"session_id": seeded_core["session_id"]},
        headers=admin_headers,
    )

    board = await client.get("/v1/leaderboards/global", headers=auth_headers)
    assert board.status_code == 200
    rows = board.json()["rows"]
    assert rows
    assert rows[0]["user_id"] == "user-alpha"


@pytest.mark.anyio
async def test_scoring_publishes_global_and_league_snapshots(
    client,
    auth_headers,
    admin_headers,
    seeded_core,
    db_session,
):
    create_league = await client.post(
        "/v1/leagues",
        json={"name": "Snapshot League", "visibility": "PUBLIC"},
        headers=auth_headers,
    )
    assert create_league.status_code == 201
    league_id = create_league.json()["id"]

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

    submit = await client.post(
        f"/v1/sessions/{seeded_core['session_id']}/predictions",
        json=payload,
        headers=auth_headers,
    )
    assert submit.status_code == 200

    score = await client.post(
        "/v1/admin/scoring/run",
        json={"session_id": seeded_core["session_id"]},
        headers=admin_headers,
    )
    assert score.status_code == 200

    global_snapshot = await db_session.scalar(
        select(LeaderboardSnapshot).where(
            LeaderboardSnapshot.scope == LeaderboardScope.GLOBAL,
            LeaderboardSnapshot.session_id == seeded_core["session_id"],
        )
    )
    assert global_snapshot is not None
    assert global_snapshot.rows_json
    assert global_snapshot.rows_json[0]["user_id"] == "user-alpha"

    league_scope_snapshot = await db_session.scalar(
        select(LeaderboardSnapshot).where(
            LeaderboardSnapshot.scope == LeaderboardScope.LEAGUE,
            LeaderboardSnapshot.scope_id == league_id,
            LeaderboardSnapshot.session_id == seeded_core["session_id"],
        )
    )
    assert league_scope_snapshot is not None
    assert league_scope_snapshot.rows_json
    assert league_scope_snapshot.rows_json[0]["user_id"] == "user-alpha"

    league_snapshot = await db_session.scalar(
        select(LeagueSnapshot).where(LeagueSnapshot.league_id == league_id)
    )
    assert league_snapshot is not None
    assert league_snapshot.rows_json
    assert league_snapshot.rows_json[0]["user_id"] == "user-alpha"
