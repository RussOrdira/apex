from __future__ import annotations

import json
import time
from dataclasses import dataclass

import httpx
import jwt
from fastapi import Header, HTTPException, status
from jwt import InvalidTokenError
from jwt.algorithms import RSAAlgorithm
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from apex_predict.config import get_settings
from apex_predict.models import Profile, User


@dataclass
class JwksCache:
    payload: dict | None = None
    expires_at: float = 0


jwks_cache = JwksCache()


def _unauthenticated(detail: str = "unauthenticated") -> HTTPException:
    return HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=detail)


def _parse_bearer_token(authorization: str | None) -> str | None:
    if not authorization:
        return None
    parts = authorization.split(" ", 1)
    if len(parts) != 2:
        return None
    token_type, token_value = parts
    if token_type.lower() != "bearer" or not token_value:
        return None
    return token_value


async def _get_jwks() -> dict:
    settings = get_settings()
    now = time.time()
    if jwks_cache.payload is not None and now < jwks_cache.expires_at:
        return jwks_cache.payload

    if not settings.supabase_url:
        raise _unauthenticated("supabase_url_not_configured")

    jwks_url = f"{settings.supabase_url.rstrip('/')}/auth/v1/.well-known/jwks.json"
    async with httpx.AsyncClient(timeout=settings.provider_timeout_seconds) as client:
        response = await client.get(jwks_url)
        response.raise_for_status()
        payload = response.json()

    jwks_cache.payload = payload
    jwks_cache.expires_at = now + max(settings.jwks_cache_ttl_seconds, 60)
    return payload


def _jwk_for_token(token: str, jwks: dict) -> object:
    header = jwt.get_unverified_header(token)
    kid = header.get("kid")
    if not kid:
        raise _unauthenticated("jwt_missing_kid")

    for key in jwks.get("keys", []):
        if key.get("kid") == kid:
            return RSAAlgorithm.from_jwk(json.dumps(key))

    raise _unauthenticated("jwt_unknown_kid")


async def verify_supabase_jwt(token: str) -> dict:
    settings = get_settings()

    if settings.supabase_jwt_secret:
        key = settings.supabase_jwt_secret
    else:
        try:
            jwks = await _get_jwks()
            key = _jwk_for_token(token, jwks)
        except httpx.HTTPError as exc:
            raise _unauthenticated(f"jwks_fetch_failed:{exc}") from exc

    issuer = settings.supabase_jwt_issuer or f"{settings.supabase_url.rstrip('/')}/auth/v1"
    decode_kwargs = {
        "algorithms": ["RS256", "HS256"],
        "issuer": issuer,
    }

    if settings.supabase_jwt_audience:
        decode_kwargs["audience"] = settings.supabase_jwt_audience

    try:
        payload = jwt.decode(token, key=key, **decode_kwargs)
    except InvalidTokenError as exc:
        raise _unauthenticated("invalid_token") from exc

    if not payload.get("sub"):
        raise _unauthenticated("token_missing_sub")

    return payload


async def get_current_user_id(
    authorization: str | None = Header(default=None),
    x_user_id: str | None = Header(default=None),
) -> str:
    settings = get_settings()

    if settings.auth_mode == "dev":
        if x_user_id:
            return x_user_id
        token = _parse_bearer_token(authorization)
        if token:
            payload = await verify_supabase_jwt(token)
            return str(payload["sub"])
        raise _unauthenticated()

    token = _parse_bearer_token(authorization)
    if token is None:
        raise _unauthenticated()

    payload = await verify_supabase_jwt(token)
    return str(payload["sub"])


async def ensure_user(session: AsyncSession, user_id: str) -> User:
    user = await session.get(User, user_id)
    if user is not None:
        return user

    user = User(id=user_id)
    session.add(user)
    await session.flush()

    existing_username = await session.scalar(select(Profile).where(Profile.username == user_id))
    username = user_id if existing_username is None else f"{user_id[:20]}-{user_id[-4:]}"
    session.add(Profile(user_id=user.id, username=username))
    await session.flush()
    return user
