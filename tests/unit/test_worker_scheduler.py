from __future__ import annotations

import asyncio

import pytest

from apex_predict.worker.scheduler import ScheduledJob, WorkerScheduler


class _FakeSession:
    def __init__(self) -> None:
        self.commit_count = 0

    async def commit(self) -> None:
        self.commit_count += 1


class _FakeSessionContext:
    def __init__(self, session: _FakeSession) -> None:
        self._session = session

    async def __aenter__(self) -> _FakeSession:
        return self._session

    async def __aexit__(self, exc_type, exc, tb) -> bool:
        return False


@pytest.mark.unit
@pytest.mark.anyio
async def test_worker_scheduler_runs_jobs_and_commits_sessions() -> None:
    run_count = 0
    sessions: list[_FakeSession] = []

    async def _runner(db: _FakeSession) -> dict[str, int]:
        nonlocal run_count
        run_count += 1
        return {"run_count": run_count}

    def _session_factory() -> _FakeSessionContext:
        session = _FakeSession()
        sessions.append(session)
        return _FakeSessionContext(session)

    scheduler = WorkerScheduler(
        jobs=[ScheduledJob(name="test", interval_seconds=0.05, runner=_runner)],
        session_factory=_session_factory,
        startup_delay_seconds=0.0,
    )
    await scheduler.start()
    await asyncio.sleep(0.18)
    await scheduler.stop()

    assert run_count >= 2
    assert sessions
    assert all(session.commit_count == 1 for session in sessions)
    assert scheduler.is_running is False


@pytest.mark.unit
@pytest.mark.anyio
async def test_worker_scheduler_keeps_running_after_job_error() -> None:
    attempts = 0

    async def _failing_runner(_: _FakeSession) -> dict:
        nonlocal attempts
        attempts += 1
        raise RuntimeError("boom")

    def _session_factory() -> _FakeSessionContext:
        return _FakeSessionContext(_FakeSession())

    scheduler = WorkerScheduler(
        jobs=[ScheduledJob(name="failing", interval_seconds=0.05, runner=_failing_runner)],
        session_factory=_session_factory,
        startup_delay_seconds=0.0,
    )
    await scheduler.start()
    await asyncio.sleep(0.18)
    await scheduler.stop()

    assert attempts >= 2
