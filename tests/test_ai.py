from __future__ import annotations

import pytest


@pytest.mark.anyio
async def test_ai_preview_endpoint_returns_advisory(client, seeded_core, auth_headers):
    response = await client.get(f"/v1/events/{seeded_core['event_id']}/ai-preview", headers=auth_headers)
    assert response.status_code == 200
    body = response.json()
    assert body["event_id"] == seeded_core["event_id"]
    assert body["data_sources"]


@pytest.mark.anyio
async def test_ai_insight_endpoint_returns_advisory(client, seeded_core, auth_headers):
    response = await client.get(
        f"/v1/sessions/{seeded_core['session_id']}/ai-insights", headers=auth_headers
    )
    assert response.status_code == 200
    body = response.json()
    assert "aggregate" in body["explanation"].lower()
    assert body["confidence_band"] in ["LOW", "MEDIUM", "HIGH"]
