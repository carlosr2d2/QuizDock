from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import User
from app.models.audit import AuditEvent


class AuditRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def add(self, event: AuditEvent) -> AuditEvent:
        self.session.add(event)
        await self.session.flush()
        return event

    async def list_for_org(
        self,
        organization_id: UUID,
        *,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[tuple[AuditEvent, str | None, str | None]], int]:
        filters = AuditEvent.organization_id == organization_id
        total_result = await self.session.execute(
            select(func.count(AuditEvent.id)).where(filters)
        )
        total = int(total_result.scalar_one() or 0)
        result = await self.session.execute(
            select(AuditEvent, User.email, User.full_name)
            .outerjoin(User, User.id == AuditEvent.actor_user_id)
            .where(filters)
            .order_by(AuditEvent.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        rows = [
            (event, email, full_name) for event, email, full_name in result.all()
        ]
        return rows, total
