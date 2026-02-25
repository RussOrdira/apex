from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime


class DataProvider(ABC):
    name: str

    @abstractmethod
    async def health_check(self) -> bool:
        raise NotImplementedError

    @abstractmethod
    async def fetch_events(self, season_year: int) -> list[dict]:
        raise NotImplementedError

    @abstractmethod
    async def fetch_session_results(self, session_external_id: str) -> list[dict]:
        raise NotImplementedError

    @abstractmethod
    async def fetch_session_facts(self, session_external_id: str) -> dict:
        raise NotImplementedError

    @abstractmethod
    async def fetch_weather(self, event_external_id: str) -> dict:
        raise NotImplementedError

    @staticmethod
    def normalize_timestamp(raw: str | None) -> datetime | None:
        if raw is None:
            return None
        return datetime.fromisoformat(raw.replace("Z", "+00:00"))
