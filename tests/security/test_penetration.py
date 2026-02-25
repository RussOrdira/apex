from __future__ import annotations

import pytest


@pytest.mark.penetration
@pytest.mark.anyio
async def test_idor_league_leaderboard_denied_for_non_member(client, auth_headers):
    create = await client.post(
        "/v1/leagues",
        json={"name": "PenTest Grid", "visibility": "PUBLIC"},
        headers=auth_headers,
    )
    assert create.status_code == 201
    league_id = create.json()["id"]

    outsider = await client.get(
        f"/v1/leagues/{league_id}/leaderboard",
        headers={"X-User-Id": "outsider-user"},
    )
    assert outsider.status_code == 403
    assert outsider.json()["detail"] == "not_a_league_member"


@pytest.mark.penetration
@pytest.mark.anyio
async def test_private_league_invite_bruteforce_attempts_fail(client, auth_headers):
    create = await client.post(
        "/v1/leagues",
        json={"name": "Private Vault", "visibility": "PRIVATE"},
        headers=auth_headers,
    )
    assert create.status_code == 201
    league_id = create.json()["id"]

    attacker_headers = {"X-User-Id": "attacker"}
    bad_codes = ["AAAA", "BBBBBBBB", "' OR 1=1 --", "../../etc/passwd", "FFFFFFFFFF"]
    for code in bad_codes:
        result = await client.post(
            f"/v1/leagues/{league_id}/join",
            json={"invite_code": code},
            headers=attacker_headers,
        )
        assert result.status_code == 403

    still_blocked = await client.get(
        f"/v1/leagues/{league_id}/leaderboard",
        headers=attacker_headers,
    )
    assert still_blocked.status_code == 403


@pytest.mark.penetration
@pytest.mark.anyio
async def test_prediction_tamper_duplicate_question_answer_rejected(client, auth_headers, seeded_core):
    response = await client.post(
        f"/v1/sessions/{seeded_core['session_id']}/predictions",
        json={
            "answers": [
                {
                    "question_instance_id": seeded_core["question_one"],
                    "selected_option": "VER",
                    "confidence_credits": 50,
                },
                {
                    "question_instance_id": seeded_core["question_one"],
                    "selected_option": "NOR",
                    "confidence_credits": 50,
                },
            ]
        },
        headers=auth_headers,
    )
    assert response.status_code == 422
    assert response.json()["detail"] == "duplicate_question_answer"
