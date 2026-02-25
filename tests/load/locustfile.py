from __future__ import annotations

import os
import random
import uuid

from locust import HttpUser, between, task

SESSION_ID = os.getenv("APEX_LOCUST_SESSION_ID", "")
QUESTION_ONE_ID = os.getenv("APEX_LOCUST_QUESTION_ONE_ID", "")
QUESTION_TWO_ID = os.getenv("APEX_LOCUST_QUESTION_TWO_ID", "")


class ApexPredictUser(HttpUser):
    wait_time = between(0.5, 2.0)

    def on_start(self) -> None:
        self.user_id = f"locust-{uuid.uuid4().hex[:8]}"

    @property
    def headers(self) -> dict[str, str]:
        return {"X-User-Id": self.user_id}

    @task(5)
    def get_events(self) -> None:
        self.client.get("/v1/events")

    @task(5)
    def get_global_leaderboard(self) -> None:
        self.client.get("/v1/leaderboards/global", headers=self.headers)

    @task(2)
    def list_public_leagues(self) -> None:
        self.client.get("/v1/leagues/public", headers=self.headers)

    @task(2)
    def create_public_league(self) -> None:
        payload = {
            "name": f"load-league-{random.randint(10000, 99999)}",
            "visibility": "PUBLIC",
        }
        self.client.post("/v1/leagues", json=payload, headers=self.headers)

    @task(3)
    def submit_predictions(self) -> None:
        if not all([SESSION_ID, QUESTION_ONE_ID, QUESTION_TWO_ID]):
            return

        payload = {
            "client_version": "locust-0.1",
            "answers": [
                {
                    "question_instance_id": QUESTION_ONE_ID,
                    "selected_option": "VER",
                    "confidence_credits": 50,
                },
                {
                    "question_instance_id": QUESTION_TWO_ID,
                    "selected_option": "NOR",
                    "confidence_credits": 50,
                },
            ],
        }
        self.client.post(
            f"/v1/sessions/{SESSION_ID}/predictions",
            json=payload,
            headers=self.headers,
        )
