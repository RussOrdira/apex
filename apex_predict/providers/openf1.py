from __future__ import annotations

from collections import defaultdict

import httpx

from apex_predict.config import get_settings
from apex_predict.providers.base import DataProvider

RACE_POINTS_BY_POSITION = {
    1: 25,
    2: 18,
    3: 15,
    4: 12,
    5: 10,
    6: 8,
    7: 6,
    8: 4,
    9: 2,
    10: 1,
}


class OpenF1Provider(DataProvider):
    name = "openf1"

    def __init__(self) -> None:
        self.settings = get_settings()

    async def health_check(self) -> bool:
        try:
            async with httpx.AsyncClient(timeout=self.settings.provider_timeout_seconds) as client:
                response = await client.get(f"{self.settings.openf1_base_url}/meetings", params={"year": 2025})
                return response.status_code == 200
        except httpx.HTTPError:
            return False

    async def fetch_events(self, season_year: int) -> list[dict]:
        async with httpx.AsyncClient(timeout=self.settings.provider_timeout_seconds) as client:
            response = await client.get(
                f"{self.settings.openf1_base_url}/meetings", params={"year": season_year}
            )
            response.raise_for_status()
            payload = response.json()

        events: list[dict] = []
        for item in payload:
            event_name = item.get("meeting_name") or "Grand Prix"
            slug = (event_name.lower().replace(" ", "-").replace("_", "-"))[:100]
            start_raw = item.get("date_start")
            end_raw = item.get("date_end") or start_raw
            events.append(
                {
                    "external_id": str(item.get("meeting_key")),
                    "name": event_name,
                    "slug": f"{season_year}-{slug}",
                    "country": item.get("country_name") or "Unknown",
                    "start_at": self.normalize_timestamp(start_raw),
                    "end_at": self.normalize_timestamp(end_raw),
                }
            )
        return events

    async def fetch_session_results(self, session_external_id: str) -> list[dict]:
        async with httpx.AsyncClient(timeout=self.settings.provider_timeout_seconds) as client:
            response = await client.get(
                f"{self.settings.openf1_base_url}/position", params={"session_key": session_external_id}
            )
            response.raise_for_status()
            payload = response.json()

        return [
            {
                "driver_number": item.get("driver_number"),
                "position": item.get("position"),
                "date": item.get("date"),
            }
            for item in payload
        ]

    async def fetch_session_facts(self, session_external_id: str) -> dict:
        async with httpx.AsyncClient(timeout=self.settings.provider_timeout_seconds) as client:
            drivers_response = await client.get(
                f"{self.settings.openf1_base_url}/drivers", params={"session_key": session_external_id}
            )
            positions_response = await client.get(
                f"{self.settings.openf1_base_url}/position", params={"session_key": session_external_id}
            )
            laps_response = await client.get(
                f"{self.settings.openf1_base_url}/laps", params={"session_key": session_external_id}
            )
            pit_response = await client.get(
                f"{self.settings.openf1_base_url}/pit", params={"session_key": session_external_id}
            )
            race_control_response = await client.get(
                f"{self.settings.openf1_base_url}/race_control", params={"session_key": session_external_id}
            )

        drivers_response.raise_for_status()
        positions_response.raise_for_status()
        laps_response.raise_for_status()
        pit_response.raise_for_status()
        race_control_response.raise_for_status()

        drivers_payload = drivers_response.json()
        positions_payload = positions_response.json()
        laps_payload = laps_response.json()
        pit_payload = pit_response.json()
        race_control_payload = race_control_response.json()

        driver_map: dict[int, dict] = {}
        for row in drivers_payload:
            number = row.get("driver_number")
            if number is None:
                continue
            code = str(row.get("name_acronym") or row.get("broadcast_name") or number).upper()[:8]
            constructor = str(row.get("team_name") or "UNK").upper().replace(" ", "_")[:12]
            driver_map[int(number)] = {
                "driver_code": code,
                "constructor_code": constructor,
            }

        latest_position: dict[int, dict] = {}
        for row in positions_payload:
            number = row.get("driver_number")
            if number is None:
                continue
            key = int(number)
            existing = latest_position.get(key)
            if existing is None or str(row.get("date") or "") > str(existing.get("date") or ""):
                latest_position[key] = row

        positions: list[dict] = []
        dnf_driver_codes: set[str] = set()
        for number, row in latest_position.items():
            position = row.get("position")
            driver_details = driver_map.get(number)
            if driver_details is None:
                continue
            if position is None:
                dnf_driver_codes.add(driver_details["driver_code"])
                continue
            positions.append(
                {
                    "position": int(position),
                    "driver_code": driver_details["driver_code"],
                    "constructor_code": driver_details["constructor_code"],
                }
            )
        positions.sort(key=lambda item: item["position"])

        fastest_lap_driver_code: str | None = None
        fastest_lap_duration: float | None = None
        for row in laps_payload:
            lap_duration = row.get("lap_duration")
            driver_number = row.get("driver_number")
            if lap_duration is None or driver_number is None:
                continue
            duration = float(lap_duration)
            if duration <= 0:
                continue
            if fastest_lap_duration is None or duration < fastest_lap_duration:
                details = driver_map.get(int(driver_number))
                if details is None:
                    continue
                fastest_lap_duration = duration
                fastest_lap_driver_code = details["driver_code"]

        first_pit_stop_team: str | None = None
        earliest_pit_date: str | None = None
        for row in pit_payload:
            pit_date = row.get("date")
            driver_number = row.get("driver_number")
            if pit_date is None or driver_number is None:
                continue
            if earliest_pit_date is None or str(pit_date) < earliest_pit_date:
                details = driver_map.get(int(driver_number))
                if details is None:
                    continue
                earliest_pit_date = str(pit_date)
                first_pit_stop_team = details["constructor_code"]

        safety_car_deployed = False
        first_safety_car_lap: int | None = None
        for row in race_control_payload:
            message = str(row.get("message") or "").upper()
            category = str(row.get("category") or "").upper()
            lap_number = row.get("lap_number")
            driver_number = row.get("driver_number")

            if "SAFETY CAR" in message and "VIRTUAL" not in message:
                safety_car_deployed = True
                if lap_number is not None:
                    lap_int = int(lap_number)
                    if first_safety_car_lap is None or lap_int < first_safety_car_lap:
                        first_safety_car_lap = lap_int

            retired_terms = ["RETIRED", "DNF", "STOPPED", "WITHDRAW"]
            if any(term in message for term in retired_terms) or "RETIRE" in category:
                if driver_number is not None:
                    details = driver_map.get(int(driver_number))
                    if details is not None:
                        dnf_driver_codes.add(details["driver_code"])

        constructor_points: dict[str, int] = defaultdict(int)
        for row in positions:
            pos = row["position"]
            pts = RACE_POINTS_BY_POSITION.get(pos, 0)
            constructor_points[row["constructor_code"]] += pts

        if fastest_lap_driver_code:
            for row in positions:
                if row["driver_code"] == fastest_lap_driver_code and row["position"] <= 10:
                    constructor_points[row["constructor_code"]] += 1
                    break

        sorted_constructors = sorted(
            constructor_points.items(), key=lambda item: item[1], reverse=True
        )
        top_three = {name for name, _ in sorted_constructors[:3]}
        midfield_constructor = None
        for constructor, _points in sorted_constructors:
            if constructor not in top_three:
                midfield_constructor = constructor
                break

        winner = positions[0]["driver_code"] if positions else None
        top5 = [row["driver_code"] for row in positions[:5]]

        return {
            "winner": winner,
            "pole": winner,
            "top5": top5,
            "dnf_driver_codes": sorted(dnf_driver_codes),
            "fastest_lap": fastest_lap_driver_code,
            "safety_car": safety_car_deployed,
            "first_pit_stop_team": first_pit_stop_team,
            "first_safety_car_lap": first_safety_car_lap,
            "constructor_points": dict(constructor_points),
            "midfield_constructor": midfield_constructor,
            "provider": self.name,
        }

    async def fetch_weather(self, event_external_id: str) -> dict:
        async with httpx.AsyncClient(timeout=self.settings.provider_timeout_seconds) as client:
            response = await client.get(
                f"{self.settings.openf1_base_url}/weather", params={"meeting_key": event_external_id}
            )
            response.raise_for_status()
            payload = response.json()

        if not payload:
            return {}
        sample = payload[-1]
        return {
            "air_temperature": sample.get("air_temperature"),
            "rainfall": sample.get("rainfall"),
            "track_temperature": sample.get("track_temperature"),
            "wind_speed": sample.get("wind_speed"),
        }
