from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.group import Group, GroupMember


class GroupRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def add(self, group: Group) -> Group:
        self.session.add(group)
        await self.session.flush()
        return group

    async def get(self, group_id: UUID, organization_id: UUID) -> Group | None:
        result = await self.session.execute(
            select(Group)
            .options(selectinload(Group.members))
            .where(Group.id == group_id, Group.organization_id == organization_id)
        )
        return result.scalar_one_or_none()

    async def get_by_name(self, organization_id: UUID, name: str) -> Group | None:
        result = await self.session.execute(
            select(Group).where(Group.organization_id == organization_id, Group.name == name)
        )
        return result.scalar_one_or_none()

    async def list_for_org(self, organization_id: UUID) -> list[Group]:
        result = await self.session.execute(
            select(Group)
            .options(selectinload(Group.members))
            .where(Group.organization_id == organization_id)
            .order_by(Group.created_at)
        )
        return list(result.scalars().all())

    async def delete(self, group: Group) -> None:
        await self.session.delete(group)
        await self.session.flush()

    async def add_member(self, member: GroupMember) -> GroupMember:
        self.session.add(member)
        await self.session.flush()
        return member

    async def get_member(
        self, group_id: UUID, user_id: UUID, organization_id: UUID
    ) -> GroupMember | None:
        result = await self.session.execute(
            select(GroupMember).where(
                GroupMember.group_id == group_id,
                GroupMember.user_id == user_id,
                GroupMember.organization_id == organization_id,
            )
        )
        return result.scalar_one_or_none()

    async def delete_member(self, member: GroupMember) -> None:
        await self.session.delete(member)
        await self.session.flush()

    async def member_user_ids(self, group_id: UUID, organization_id: UUID) -> set[UUID]:
        result = await self.session.execute(
            select(GroupMember.user_id).where(
                GroupMember.group_id == group_id,
                GroupMember.organization_id == organization_id,
            )
        )
        return set(result.scalars().all())

    async def delete_user_from_org(self, organization_id: UUID, user_id: UUID) -> None:
        result = await self.session.execute(
            select(GroupMember).where(
                GroupMember.organization_id == organization_id,
                GroupMember.user_id == user_id,
            )
        )
        for item in result.scalars().all():
            await self.session.delete(item)
        await self.session.flush()

    async def replace_members(
        self, group: Group, organization_id: UUID, user_ids: set[UUID]
    ) -> None:
        current = {item.user_id: item for item in group.members}
        for user_id, item in list(current.items()):
            if user_id not in user_ids:
                await self.session.delete(item)
        for user_id in user_ids:
            if user_id in current:
                continue
            self.session.add(
                GroupMember(organization_id=organization_id, group_id=group.id, user_id=user_id)
            )
        await self.session.flush()
