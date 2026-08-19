from dataclasses import dataclass
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.security import create_access_token, hash_password, verify_password
from app.core.text import slugify
from app.models import CreditTransaction, Membership, MembershipRole, Organization, PlanTier, User
from app.repositories.identity import MembershipRepository, OrganizationRepository, UserRepository

settings = get_settings()


class AuthError(Exception):
    def __init__(self, message: str, status_code: int = 400) -> None:
        self.message = message
        self.status_code = status_code
        super().__init__(message)


@dataclass
class AuthResult:
    user: User
    access_token: str
    organization_id: UUID


class AuthService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.users = UserRepository(session)
        self.orgs = OrganizationRepository(session)
        self.memberships = MembershipRepository(session)

    async def register(
        self, email: str, password: str, full_name: str, invite_token: str | None = None
    ) -> AuthResult:
        normalized = email.lower()
        if await self.users.get_by_email(normalized):
            raise AuthError("Email already registered", 409)

        user = User(email=normalized, hashed_password=hash_password(password), full_name=full_name)
        await self.users.add(user)

        slug = await self._unique_slug(slugify(full_name) or normalized.split("@")[0])
        org = Organization(
            name=f"{full_name}'s workspace",
            slug=slug,
            plan=PlanTier.FREE,
            is_personal=True,
            credit_balance=settings.signup_bonus_credits,
        )
        await self.orgs.add(org)

        membership = Membership(
            user_id=user.id,
            organization_id=org.id,
            role=MembershipRole.OWNER,
        )
        await self.memberships.add(membership)

        user.personal_organization_id = org.id
        self.session.add(
            CreditTransaction(
                organization_id=org.id,
                user_id=user.id,
                amount=settings.signup_bonus_credits,
                reason="signup_bonus",
                balance_after=settings.signup_bonus_credits,
            )
        )
        await self.session.commit()

        hydrated = await self.users.get_by_id(user.id)
        assert hydrated is not None
        return await self._finish_auth(hydrated, invite_token)

    async def login(self, email: str, password: str, invite_token: str | None = None) -> AuthResult:
        user = await self.users.get_by_email(email.lower())
        if user is None or not verify_password(password, user.hashed_password):
            raise AuthError("Invalid email or password", 401)
        if not user.is_active:
            raise AuthError("Account is disabled", 403)

        hydrated = await self.users.get_by_id(user.id)
        assert hydrated is not None
        return await self._finish_auth(hydrated, invite_token)

    async def _finish_auth(self, user: User, invite_token: str | None) -> AuthResult:
        from app.services.team import TeamService

        joined_id = await TeamService(self.session).claim_pending(user, invite_token)
        if joined_id is not None:
            hydrated = await self.users.get_by_id(user.id)
            assert hydrated is not None
            user = hydrated
        org_id = joined_id or user.personal_organization_id
        if org_id is None and user.memberships:
            org_id = user.memberships[0].organization_id
        if org_id is None:
            raise AuthError("No hay workspace asociado", 400)
        return AuthResult(user=user, access_token=create_access_token(user.id), organization_id=org_id)

    async def _unique_slug(self, base: str) -> str:
        candidate = base
        suffix = 2
        while await self.orgs.slug_exists(candidate):
            candidate = f"{base}-{suffix}"
            suffix += 1
        return candidate


async def get_membership(
    session: AsyncSession,
    user_id: UUID,
    organization_id: UUID,
) -> Membership | None:
    return await MembershipRepository(session).get(user_id, organization_id)
