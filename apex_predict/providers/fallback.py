from __future__ import annotations

import httpx

from apex_predict.config import get_settings
from apex_predict.providers.base import DataProvider


class FallbackProvider(DataProvider):
    name = "fallback"

    def __init__(self) -> None:
        self.settings = get_settings()

    async def health_check(self) -> bool:
        try:
            async with httpx.AsyncClient(timeout=self.settings.provider_timeout_seconds) as client:
                response = await client.get(
                    f"{self.settings.fallback_base_url}/current.json", params={"limit": 1}
                )
                return response.status_code == 200
        except httpx.HTTPError:
            return False

    async def fetch_events(self, season_year: int) -> list[dict]:
        async with httpx.AsyncClient(timeout=self.settings.provider_timeout_seconds) as client:
            response = await client.get(f"{self.settings.fallback_base_url}/{season_year}.json")
            response.raise_for_status()
            payload = response.json()

        races = payload.get("MRData", {}).get("RaceTable", {}).get("Races", [])
        events: list[dict] = []
        for race in races:
            date_raw = race.get("date")
            time_raw = race.get("time") or "00:00:00Z"
            dt = self.normalize_timestamp(f"{date_raw}T{time_raw}") if date_raw else None
            events.append(
                {
                    "external_id": race.get("round"),
                    "name": race.get("raceName", "Grand Prix"),
                    "slug": f"{season_year}-{race.get('round', 'x')}",
                    "country": race.get("Circuit", {}).get("Location", {}).get("country", "Unknown"),
                    "start_at": dt,
                    "end_at": dt,
                }
            )
        return events

    async def fetch_session_results(self, session_external_id: str) -> list[dict]:
        # Fallback API does not expose in-session live positions with this endpoint shape.
        return []

    async def fetch_session_facts(self, session_external_id: str) -> dict:
        return {
            "winner": None,
            "pole": None,
            "top5": [],
            "dnf_driver_codes": [],
            "fastest_lap": None,
            "safety_car": False,
            "first_pit_stop_team": None,
            "first_safety_car_lap": None,
            "constructor_points": {},
            "midfield_constructor": None,
            "provider": self.name,
        }

    async def fetch_weather(self, event_external_id: str) -> dict:
        return {}
