from dataclasses import dataclass
from uuid import UUID

from fastapi import Depends, Header, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_db
from app.core.security import decode_token
from app.models import MembershipRole, User
from app.repositories.identity import MembershipRepository, UserRepository

bearer = HTTPBearer(auto_error=False)


@dataclass
class RequestContext:
    user: User
    organization_id: UUID
    role: MembershipRole


async def get_current_user(
    creds: HTTPAuthorizationCredentials | None = Depends(bearer),
    db: AsyncSession = Depends(get_db),
) -> User:
    if creds is None or creds.scheme.lower() != "bearer":
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Not authenticated")
    try:
        payload = decode_token(creds.credentials)
        user_id = UUID(payload["sub"])
    except (ValueError, KeyError):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid token") from None

    user = await UserRepository(db).get_by_id(user_id)
    if user is None or not user.is_active:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "User not found")
    return user


async def get_context(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    x_organization_id: str | None = Header(default=None, alias="X-Organization-Id"),
) -> RequestContext:
    org_id: UUID | None = None
    if x_organization_id:
        try:
            org_id = UUID(x_organization_id)
        except ValueError:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "Invalid organization id") from None
    elif user.personal_organization_id:
        org_id = user.personal_organization_id

    if org_id is None:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Organization context required")

    memberships = MembershipRepository(db)
    membership = await memberships.get(user.id, org_id)
    if membership is None:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Not a member of this organization")
    await memberships.touch_last_seen(user.id, org_id)

    return RequestContext(user=user, organization_id=org_id, role=membership.role)


def require_roles(*roles: MembershipRole, detail: str = "No tienes permiso para esta acción."):
    async def _guard(ctx: RequestContext = Depends(get_context)) -> RequestContext:
        if ctx.role not in roles:
            raise HTTPException(status.HTTP_403_FORBIDDEN, detail)
        return ctx

    return _guard
