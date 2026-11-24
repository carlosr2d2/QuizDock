from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import User
from app.models.ai_audit import AiDecisionEvent, AiFeature
from app.models.exam import parse_str_enum


class AiAuditRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def add(self, row: AiDecisionEvent) -> AiDecisionEvent:
        self.session.add(row)
        await self.session.flush()
        return row

    async def list_for_org(
        self,
        organization_id: UUID,
        *,
        feature: AiFeature | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[tuple[AiDecisionEvent, str | None, str | None]], int]:
        conditions = [AiDecisionEvent.organization_id == organization_id]
        if feature is not None:
            conditions.append(AiDecisionEvent.feature == feature)
        total_result = await self.session.execute(
            select(func.count(AiDecisionEvent.id)).where(*conditions)
        )
        total = int(total_result.scalar_one() or 0)
        result = await self.session.execute(
            select(AiDecisionEvent, User.email, User.full_name)
            .outerjoin(User, User.id == AiDecisionEvent.actor_user_id)
            .where(*conditions)
            .order_by(AiDecisionEvent.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        rows = [(event, email, full_name) for event, email, full_name in result.all()]
        return rows, total

    async def list_for_appeal(
        self, organization_id: UUID, appeal_id: UUID
    ) -> list[AiDecisionEvent]:
        result = await self.session.execute(
            select(AiDecisionEvent)
            .where(
                AiDecisionEvent.organization_id == organization_id,
                AiDecisionEvent.feature == AiFeature.APPEAL_REVIEW,
            )
            .order_by(AiDecisionEvent.created_at.asc())
        )
        target = str(appeal_id)
        return [
            row
            for row in result.scalars().all()
            if str((row.payload or {}).get("appeal_id") or "") == target
        ]

    async def purge_before(self, cutoff: datetime, *, organization_id: UUID | None = None) -> int:
        conditions = [AiDecisionEvent.created_at < cutoff]
        if organization_id is not None:
            conditions.append(AiDecisionEvent.organization_id == organization_id)
        result = await self.session.execute(delete(AiDecisionEvent).where(*conditions))
        await self.session.flush()
        return int(result.rowcount or 0)

    @staticmethod
    def parse_feature(value: str | None) -> AiFeature | None:
        if not value:
            return None
        return parse_str_enum(AiFeature, value)
