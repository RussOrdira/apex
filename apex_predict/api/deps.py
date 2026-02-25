from typing import Annotated

from fastapi import Depends, Header, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from apex_predict.auth import ensure_user, get_current_user_id
from apex_predict.config import get_settings
from apex_predict.db import get_async_session

DbSession = Annotated[AsyncSession, Depends(get_async_session)]


async def get_authed_user_id(
    session: DbSession,
    user_id: Annotated[str, Depends(get_current_user_id)],
) -> str:
    await ensure_user(session, user_id)
    return user_id


AuthedUserId = Annotated[str, Depends(get_authed_user_id)]

settings = get_settings()


async def require_admin_key(x_admin_key: str | None = Header(default=None)) -> None:
    if x_admin_key != settings.admin_api_key:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="admin_forbidden",
        )


AdminAuthorized = Annotated[None, Depends(require_admin_key)]
