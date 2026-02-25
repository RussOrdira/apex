from __future__ import annotations

from apex_predict.providers.base import DataProvider
from apex_predict.providers.fallback import FallbackProvider
from apex_predict.providers.openf1 import OpenF1Provider


class ProviderRouter:
    def __init__(self) -> None:
        self.primary = OpenF1Provider()
        self.fallback = FallbackProvider()

    async def active_provider(self) -> DataProvider:
        if await self.primary.health_check():
            return self.primary
        return self.fallback

    async def fetch_events(self, season_year: int) -> tuple[str, list[dict]]:
        provider = await self.active_provider()
        try:
            return provider.name, await provider.fetch_events(season_year)
        except Exception:
            return self.fallback.name, await self.fallback.fetch_events(season_year)

    async def fetch_session_results(self, session_external_id: str) -> tuple[str, list[dict]]:
        provider = await self.active_provider()
        try:
            return provider.name, await provider.fetch_session_results(session_external_id)
        except Exception:
            return self.fallback.name, await self.fallback.fetch_session_results(session_external_id)

    async def fetch_session_facts(self, session_external_id: str) -> tuple[str, dict]:
        provider = await self.active_provider()
        try:
            return provider.name, await provider.fetch_session_facts(session_external_id)
        except Exception:
            return self.fallback.name, await self.fallback.fetch_session_facts(session_external_id)

    async def fetch_weather(self, event_external_id: str) -> tuple[str, dict]:
        provider = await self.active_provider()
        try:
            return provider.name, await provider.fetch_weather(event_external_id)
        except Exception:
            return self.fallback.name, await self.fallback.fetch_weather(event_external_id)
