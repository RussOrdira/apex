from __future__ import annotations

import asyncio
import logging
import time
from collections.abc import Awaitable, Callable
from contextlib import AbstractAsyncContextManager
from dataclasses import dataclass
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)

JobRunner = Callable[[AsyncSession], Awaitable[dict[str, Any]]]
SessionFactory = Callable[[], AbstractAsyncContextManager[AsyncSession]]


@dataclass(frozen=True)
class ScheduledJob:
    name: str
    interval_seconds: float
    runner: JobRunner


class WorkerScheduler:
    def __init__(
        self,
        *,
        jobs: list[ScheduledJob],
        session_factory: SessionFactory,
        startup_delay_seconds: float = 0.0,
    ) -> None:
        self.jobs = jobs
        self.session_factory = session_factory
        self.startup_delay_seconds = max(startup_delay_seconds, 0.0)
        self._stop = asyncio.Event()
        self._tasks: list[asyncio.Task[None]] = []

    @property
    def is_running(self) -> bool:
        return bool(self._tasks)

    async def start(self) -> None:
        if self.is_running:
            return

        self._stop.clear()
        for job in self.jobs:
            task = asyncio.create_task(
                self._run_job_loop(job),
                name=f"worker-job-{job.name}",
            )
            self._tasks.append(task)

    async def stop(self) -> None:
        if not self._tasks:
            return

        self._stop.set()
        for task in self._tasks:
            task.cancel()

        await asyncio.gather(*self._tasks, return_exceptions=True)
        self._tasks.clear()

    async def _run_job_loop(self, job: ScheduledJob) -> None:
        if self.startup_delay_seconds > 0:
            try:
                await asyncio.wait_for(self._stop.wait(), timeout=self.startup_delay_seconds)
                return
            except TimeoutError:
                pass

        interval = max(job.interval_seconds, 0.1)
        while not self._stop.is_set():
            started = time.monotonic()
            try:
                async with self.session_factory() as db:
                    result = await job.runner(db)
                    await db.commit()
                logger.info("worker_job_success job=%s result=%s", job.name, result)
            except asyncio.CancelledError:
                raise
            except Exception:
                logger.exception("worker_job_failed job=%s", job.name)

            elapsed = time.monotonic() - started
            sleep_for = max(interval - elapsed, 0.1)
            try:
                await asyncio.wait_for(self._stop.wait(), timeout=sleep_for)
            except TimeoutError:
                continue
