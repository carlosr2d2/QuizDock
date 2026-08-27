from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from uuid import UUID
import logging
import secrets

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.security import create_access_token, hash_password, hash_reset_token, verify_password
from app.core.text import slugify
from app.models import CreditTransaction, Membership, MembershipRole, Organization, PlanTier, User
from app.models.identity import PasswordResetToken
from app.models.mixins import utcnow
from app.repositories.identity import (
    MembershipRepository,
    OrganizationRepository,
    PasswordResetRepository,
    UserRepository,
)
from app.services.mail import MailError, Mailer, build_recovery_email, get_mailer, recovery_url

settings = get_settings()
logger = logging.getLogger(__name__)


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
    def __init__(self, session: AsyncSession, mailer: Mailer | None = None) -> None:
        self.session = session
        self.users = UserRepository(session)
        self.orgs = OrganizationRepository(session)
        self.memberships = MembershipRepository(session)
        self.resets = PasswordResetRepository(session)
        self.mailer = mailer if mailer is not None else get_mailer()

    async def register(
        self,
        email: str,
        password: str,
        full_name: str,
        invite_token: str | None = None,
        locale: str = "es",
    ) -> AuthResult:
        normalized = email.lower()
        if await self.users.get_by_email(normalized):
            raise AuthError("Email already registered", 409)

        user = User(
            email=normalized,
            hashed_password=hash_password(password),
            full_name=full_name,
            locale="en" if locale == "en" else "es",
        )
        await self.users.add(user)

        slug = await self._unique_slug(slugify(full_name) or normalized.split("@")[0])
        org = Organization(
            name=f"{full_name}'s workspace",
            slug=slug,
            plan=PlanTier.FREE,
            is_personal=True,
            credit_balance=settings.signup_bonus_credits,
            billing_country=settings.payment_default_country,
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

    async def request_recovery(self, email: str) -> None:
        user = await self.users.get_by_email(email.lower())
        if user is None or not user.is_active:
            return

        await self.resets.expire_unused_for_user(user.id)
        raw = secrets.token_urlsafe(32)
        reset = PasswordResetToken(
            user_id=user.id,
            token_hash=hash_reset_token(raw),
            expires_at=utcnow() + timedelta(minutes=settings.password_reset_expire_minutes),
        )
        await self.resets.add(reset)
        await self.session.commit()

        url = recovery_url(raw)
        message = build_recovery_email(
            to=user.email,
            reset_url=url,
            expires_minutes=settings.password_reset_expire_minutes,
            locale=user.locale,
        )
        if not self.mailer.configured:
            logger.info("Password reset for %s (SMTP not configured): %s", user.email, url)
            return
        try:
            self.mailer.send(message)
        except MailError:
            logger.exception("Failed to send password reset to %s", user.email)

    async def assert_recovery_token(self, token: str) -> PasswordResetToken:
        reset = await self.resets.get_by_hash(hash_reset_token(token))
        if reset is None or reset.used_at is not None:
            raise AuthError("El enlace no es válido o caducó.", 400)
        expires = reset.expires_at
        if expires.tzinfo is None:
            expires = expires.replace(tzinfo=timezone.utc)
        if expires <= datetime.now(timezone.utc):
            raise AuthError("El enlace no es válido o caducó.", 400)
        user = await self.users.get_by_id(reset.user_id)
        if user is None or not user.is_active:
            raise AuthError("El enlace no es válido o caducó.", 400)
        return reset

    async def reset_password(self, token: str, password: str) -> AuthResult:
        reset = await self.assert_recovery_token(token)
        user = await self.users.get_by_id(reset.user_id)
        assert user is not None
        user.hashed_password = hash_password(password)
        reset.used_at = utcnow()
        await self.resets.expire_unused_for_user(user.id, except_id=reset.id)
        await self.session.commit()
        hydrated = await self.users.get_by_id(user.id)
        assert hydrated is not None
        return await self._finish_auth(hydrated, None)

    async def update_locale(self, user: User, locale: str) -> User:
        return await self.update_profile(user, locale=locale)

    async def update_profile(
        self,
        user: User,
        *,
        locale: str | None = None,
        full_name: str | None = None,
        current_password: str | None = None,
        password: str | None = None,
    ) -> User:
        persisted = await self.users.get_by_id(user.id)
        if persisted is None:
            raise AuthError("User not found", 404)
        if locale is not None:
            persisted.locale = "en" if locale == "en" else "es"
        if full_name is not None:
            persisted.full_name = full_name.strip()
        if password is not None:
            if not current_password or not verify_password(current_password, persisted.hashed_password):
                raise AuthError("Current password is incorrect", 400)
            persisted.hashed_password = hash_password(password)
        await self.session.commit()
        return persisted

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
