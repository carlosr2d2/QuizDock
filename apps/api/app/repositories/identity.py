from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models import Invitation, Membership, Organization, User
from app.models.identity import InvitationStatus


class UserRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_by_email(self, email: str) -> User | None:
        result = await self.session.execute(select(User).where(User.email == email.lower()))
        return result.scalar_one_or_none()

    async def get_by_id(self, user_id: UUID) -> User | None:
        result = await self.session.execute(
            select(User)
            .options(selectinload(User.memberships).selectinload(Membership.organization))
            .where(User.id == user_id)
        )
        return result.scalar_one_or_none()

    async def add(self, user: User) -> User:
        self.session.add(user)
        await self.session.flush()
        return user


class OrganizationRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get(self, org_id: UUID) -> Organization | None:
        result = await self.session.execute(select(Organization).where(Organization.id == org_id))
        return result.scalar_one_or_none()

    async def get_for_update(self, org_id: UUID) -> Organization | None:
        result = await self.session.execute(
            select(Organization).where(Organization.id == org_id).with_for_update()
        )
        return result.scalar_one_or_none()

    async def slug_exists(self, slug: str) -> bool:
        result = await self.session.execute(select(Organization.id).where(Organization.slug == slug))
        return result.scalar_one_or_none() is not None

    async def add(self, organization: Organization) -> Organization:
        self.session.add(organization)
        await self.session.flush()
        return organization


class MembershipRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get(self, user_id: UUID, organization_id: UUID) -> Membership | None:
        result = await self.session.execute(
            select(Membership).where(
                Membership.user_id == user_id,
                Membership.organization_id == organization_id,
            )
        )
        return result.scalar_one_or_none()

    async def get_with_user(self, user_id: UUID, organization_id: UUID) -> Membership | None:
        result = await self.session.execute(
            select(Membership)
            .options(selectinload(Membership.user))
            .where(
                Membership.user_id == user_id,
                Membership.organization_id == organization_id,
            )
        )
        return result.scalar_one_or_none()

    async def add(self, membership: Membership) -> Membership:
        self.session.add(membership)
        await self.session.flush()
        return membership

    async def list_with_users(self, organization_id: UUID) -> list[Membership]:
        result = await self.session.execute(
            select(Membership)
            .options(selectinload(Membership.user))
            .where(Membership.organization_id == organization_id)
            .order_by(Membership.created_at)
        )
        return list(result.scalars().all())

    async def delete(self, membership: Membership) -> None:
        await self.session.delete(membership)
        await self.session.flush()


class InvitationRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def add(self, invitation: Invitation) -> Invitation:
        self.session.add(invitation)
        await self.session.flush()
        return invitation

    async def get(self, invitation_id: UUID, organization_id: UUID) -> Invitation | None:
        result = await self.session.execute(
            select(Invitation).where(
                Invitation.id == invitation_id,
                Invitation.organization_id == organization_id,
            )
        )
        return result.scalar_one_or_none()

    async def get_by_token(self, token: str) -> Invitation | None:
        result = await self.session.execute(
            select(Invitation)
            .options(selectinload(Invitation.organization))
            .where(Invitation.token == token)
        )
        return result.scalar_one_or_none()

    async def get_pending(self, organization_id: UUID, email: str) -> Invitation | None:
        result = await self.session.execute(
            select(Invitation).where(
                Invitation.organization_id == organization_id,
                func.lower(Invitation.email) == email.lower(),
                Invitation.status == InvitationStatus.PENDING,
            )
        )
        return result.scalar_one_or_none()

    async def list_for_org(self, organization_id: UUID) -> list[Invitation]:
        result = await self.session.execute(
            select(Invitation)
            .where(Invitation.organization_id == organization_id)
            .order_by(Invitation.created_at.desc())
        )
        return list(result.scalars().all())

    async def list_pending_for_email(self, email: str) -> list[Invitation]:
        result = await self.session.execute(
            select(Invitation)
            .options(selectinload(Invitation.organization))
            .where(
                func.lower(Invitation.email) == email.lower(),
                Invitation.status == InvitationStatus.PENDING,
            )
            .order_by(Invitation.created_at.desc())
        )
        return list(result.scalars().all())
