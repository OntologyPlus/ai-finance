from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from models.database import get_db
from models.user import User
from api.auth import _resolve_user_from_token

security_scheme = HTTPBearer(auto_error=False)


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security_scheme),
    db: AsyncSession = Depends(get_db),
) -> User:
    """Extract and validate current user from JWT token in Authorization header.

    Returns a User object or raises 401.
    """
    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing authentication token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    token = credentials.credentials
    user = await _resolve_user_from_token(token, db)
    return user


def get_center_filter_for_user(user: User) -> str | None:
    """Determine center_id filter based on user role.

    - employee / dept_head: filter by their center_id
    - center_manager: filter by their center_id
    - cfo / admin: no filter (see all)
    """
    if user.role in ("cfo", "admin"):
        return None
    return user.center_id
