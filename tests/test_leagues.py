from __future__ import annotations

import pytest


@pytest.mark.anyio
async def test_create_public_league_and_discover(client, auth_headers):
    create = await client.post(
        "/v1/leagues",
        json={"name": "Global Pace Hunters", "visibility": "PUBLIC"},
        headers=auth_headers,
    )
    assert create.status_code == 201

    listing = await client.get("/v1/leagues/public", headers=auth_headers)
    assert listing.status_code == 200
    names = [league["name"] for league in listing.json()]
    assert "Global Pace Hunters" in names


@pytest.mark.anyio
async def test_private_league_join_requires_invite(client, auth_headers):
    create = await client.post(
        "/v1/leagues",
        json={"name": "Closed Paddock", "visibility": "PRIVATE"},
        headers=auth_headers,
    )
    assert create.status_code == 201
    league = create.json()

    no_invite = await client.post(
        f"/v1/leagues/{league['id']}/join",
        json={},
        headers={"X-User-Id": "user-beta"},
    )
    assert no_invite.status_code == 403

    with_invite = await client.post(
        f"/v1/leagues/{league['id']}/join",
        json={"invite_code": league["invite_code"]},
        headers={"X-User-Id": "user-beta"},
    )
    assert with_invite.status_code == 204


@pytest.mark.anyio
async def test_league_leaderboard_access_control(client, auth_headers):
    create = await client.post(
        "/v1/leagues",
        json={"name": "Friends Grid", "visibility": "PUBLIC"},
        headers=auth_headers,
    )
    assert create.status_code == 201
    league_id = create.json()["id"]

    forbidden = await client.get(
        f"/v1/leagues/{league_id}/leaderboard", headers={"X-User-Id": "outsider"}
    )
    assert forbidden.status_code == 403

    allowed = await client.get(f"/v1/leagues/{league_id}/leaderboard", headers=auth_headers)
    assert allowed.status_code == 200
