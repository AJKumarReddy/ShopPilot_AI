import hashlib
from typing import Annotated

from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.errors import CommerceError
from app.db.session import get_db
from app.models.entities import User

DEMO_USER_ID = "00000000-0000-4000-8000-000000000001"
bearer = HTTPBearer(auto_error=False)


def token_hash(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


async def current_user(
    db: Annotated[AsyncSession, Depends(get_db)],
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer)],
) -> User:
    settings = get_settings()
    if credentials:
        user = await db.scalar(
            select(User).where(User.token_hash == token_hash(credentials.credentials))
        )
    elif settings.auth_mode == "demo":
        user = await db.get(User, DEMO_USER_ID)
    else:
        raise CommerceError("Authentication required.", 401)
    if not user:
        raise CommerceError("Invalid account or demo account has not been seeded.", 401)
    return user
