from __future__ import annotations

import random
import string

import pytest


def random_text(min_len: int = 1, max_len: int = 140) -> str:
    size = random.randint(min_len, max_len)
    alphabet = string.ascii_letters + string.digits + string.punctuation + " _-"
    return "".join(random.choice(alphabet) for _ in range(size))


@pytest.mark.fuzz
@pytest.mark.anyio
async def test_fuzz_league_creation_inputs_do_not_500(client, auth_headers):
    random.seed(20260225)

    for _ in range(80):
        candidate = random_text()
        response = await client.post(
            "/v1/leagues",
            json={"name": candidate, "visibility": "PUBLIC"},
            headers=auth_headers,
        )
        assert response.status_code in {201, 422}


@pytest.mark.fuzz
@pytest.mark.anyio
async def test_fuzz_prediction_payloads_do_not_500(client, auth_headers, seeded_core):
    random.seed(20260226)

    valid_options = ["VER", "NOR", "LEC", "YES", "NO"]
    for _ in range(60):
        option_a = random.choice(valid_options + [random_text(1, 5)])
        option_b = random.choice(valid_options + [random_text(1, 5)])
        credits_a = random.randint(-20, 120)
        credits_b = random.randint(-20, 120)

        payload = {
            "answers": [
                {
                    "question_instance_id": seeded_core["question_one"],
                    "selected_option": option_a,
                    "confidence_credits": credits_a,
                },
                {
                    "question_instance_id": seeded_core["question_two"],
                    "selected_option": option_b,
                    "confidence_credits": credits_b,
                },
            ]
        }

        response = await client.post(
            f"/v1/sessions/{seeded_core['session_id']}/predictions",
            json=payload,
            headers=auth_headers,
        )
        assert response.status_code in {200, 409, 422}
