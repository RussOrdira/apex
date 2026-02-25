from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from apex_predict.enums import LeaderboardScope
from apex_predict.models import (
    LeaderboardSnapshot,
    League,
    LeagueMember,
    LeagueSnapshot,
    Profile,
    ScoreEntry,
)


def _now_utc() -> datetime:
    return datetime.now(tz=timezone.utc)


async def build_global_leaderboard(session: AsyncSession) -> list[dict]:
    rows = (
        await session.execute(
            select(
                ScoreEntry.user_id,
                func.coalesce(Profile.username, ScoreEntry.user_id).label("username"),
                func.coalesce(func.sum(ScoreEntry.awarded_points), 0).label("total_points"),
            )
            .join(Profile, Profile.user_id == ScoreEntry.user_id, isouter=True)
            .group_by(ScoreEntry.user_id, Profile.username)
            .order_by(func.sum(ScoreEntry.awarded_points).desc())
        )
    ).all()

    result: list[dict] = []
    for i, row in enumerate(rows, start=1):
        result.append(
            {
                "rank": i,
                "user_id": row.user_id,
                "username": row.username or row.user_id,
                "total_points": float(row.total_points),
            }
        )
    return result


async def build_league_leaderboard(session: AsyncSession, league_id: str) -> list[dict]:
    rows = (
        await session.execute(
            select(
                LeagueMember.user_id,
                func.coalesce(Profile.username, LeagueMember.user_id).label("username"),
                func.coalesce(func.sum(ScoreEntry.awarded_points), 0).label("total_points"),
            )
            .join(Profile, Profile.user_id == LeagueMember.user_id, isouter=True)
            .join(ScoreEntry, ScoreEntry.user_id == LeagueMember.user_id, isouter=True)
            .where(LeagueMember.league_id == league_id)
            .group_by(LeagueMember.user_id, Profile.username)
            .order_by(func.coalesce(func.sum(ScoreEntry.awarded_points), 0).desc())
        )
    ).all()

    result: list[dict] = []
    for i, row in enumerate(rows, start=1):
        result.append(
            {
                "rank": i,
                "user_id": row.user_id,
                "username": row.username or row.user_id,
                "total_points": float(row.total_points),
            }
        )
    return result


async def _upsert_leaderboard_snapshot(
    session: AsyncSession,
    *,
    scope: LeaderboardScope,
    scope_id: str | None,
    session_id: str | None,
    rows: list[dict],
) -> LeaderboardSnapshot:
    query = select(LeaderboardSnapshot).where(
        LeaderboardSnapshot.scope == scope,
        LeaderboardSnapshot.scope_id == scope_id,
    )
    if session_id is None:
        query = query.where(LeaderboardSnapshot.session_id.is_(None))
    else:
        query = query.where(LeaderboardSnapshot.session_id == session_id)

    snapshot = await session.scalar(query)
    if snapshot is None:
        snapshot = LeaderboardSnapshot(
            scope=scope,
            scope_id=scope_id,
            session_id=session_id,
            computed_at=_now_utc(),
            rows_json=rows,
        )
        session.add(snapshot)
    else:
        snapshot.rows_json = rows
        snapshot.computed_at = _now_utc()

    return snapshot


async def publish_leaderboard_snapshots(
    session: AsyncSession,
    *,
    session_id: str | None,
) -> dict[str, int]:
    global_rows = await build_global_leaderboard(session)
    await _upsert_leaderboard_snapshot(
        session,
        scope=LeaderboardScope.GLOBAL,
        scope_id=None,
        session_id=session_id,
        rows=global_rows,
    )

    league_ids = (await session.scalars(select(League.id))).all()
    league_snapshot_rows = 0
    for league_id in league_ids:
        league_rows = await build_league_leaderboard(session, league_id)
        await _upsert_leaderboard_snapshot(
            session,
            scope=LeaderboardScope.LEAGUE,
            scope_id=league_id,
            session_id=session_id,
            rows=league_rows,
        )
        session.add(
            LeagueSnapshot(
                league_id=league_id,
                computed_at=_now_utc(),
                rows_json=league_rows,
            )
        )
        league_snapshot_rows += 1

    await session.flush()
    return {
        "leaderboard_snapshots": 1 + league_snapshot_rows,
        "league_snapshots": league_snapshot_rows,
    }
