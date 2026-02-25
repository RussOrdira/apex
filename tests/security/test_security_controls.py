from __future__ import annotations

import pytest


@pytest.mark.security
@pytest.mark.anyio
async def test_prediction_requires_authentication(client, seeded_core):
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

    response = await client.post(f"/v1/sessions/{seeded_core['session_id']}/predictions", json=payload)
    assert response.status_code == 401
    assert response.json()["detail"] == "unauthenticated"


@pytest.mark.security
@pytest.mark.anyio
async def test_admin_scoring_requires_admin_key(client, auth_headers, seeded_core):
    submit = await client.post(
        f"/v1/sessions/{seeded_core['session_id']}/predictions",
        json={
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
        },
        headers=auth_headers,
    )
    assert submit.status_code == 200

    missing_admin_key = await client.post(
        "/v1/admin/scoring/run",
        json={"session_id": seeded_core["session_id"]},
        headers=auth_headers,
    )
    assert missing_admin_key.status_code == 403

    invalid_admin_key = await client.post(
        "/v1/admin/scoring/run",
        json={"session_id": seeded_core["session_id"]},
        headers={"X-User-Id": "user-alpha", "X-Admin-Key": "wrong"},
    )
    assert invalid_admin_key.status_code == 403


@pytest.mark.security
@pytest.mark.anyio
async def test_admin_rule_upsert_requires_admin_key(client, auth_headers):
    response = await client.post(
        "/v1/admin/rules",
        json={
            "name": "Security Rule",
            "question_type": "POLE",
            "base_points": 10,
            "metadata_json": {},
        },
        headers=auth_headers,
    )
    assert response.status_code == 403


@pytest.mark.security
@pytest.mark.anyio
async def test_league_name_blocks_injection_payloads(client, auth_headers):
    response = await client.post(
        "/v1/leagues",
        json={"name": "DROP TABLE leagues;--", "visibility": "PUBLIC"},
        headers=auth_headers,
    )
    assert response.status_code == 422
    assert response.json()["detail"] == "league_name_not_allowed"
