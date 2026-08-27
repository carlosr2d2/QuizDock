from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import PaymentOrder


class PaymentOrderRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def add(self, order: PaymentOrder) -> PaymentOrder:
        self.session.add(order)
        await self.session.flush()
        return order

    async def get(self, order_id: UUID, organization_id: UUID | None = None) -> PaymentOrder | None:
        query = select(PaymentOrder).where(PaymentOrder.id == order_id)
        if organization_id is not None:
            query = query.where(PaymentOrder.organization_id == organization_id)
        result = await self.session.execute(query)
        return result.scalar_one_or_none()

    async def get_for_update(self, order_id: UUID) -> PaymentOrder | None:
        result = await self.session.execute(
            select(PaymentOrder).where(PaymentOrder.id == order_id).with_for_update()
        )
        return result.scalar_one_or_none()

    async def get_by_provider_session(self, provider: str, provider_session_id: str) -> PaymentOrder | None:
        result = await self.session.execute(
            select(PaymentOrder).where(
                PaymentOrder.provider == provider,
                PaymentOrder.provider_session_id == provider_session_id,
            )
        )
        return result.scalar_one_or_none()

    async def list_for_org(self, organization_id: UUID, *, limit: int = 40) -> list[PaymentOrder]:
        result = await self.session.execute(
            select(PaymentOrder)
            .where(PaymentOrder.organization_id == organization_id)
            .order_by(PaymentOrder.created_at.desc())
            .limit(limit)
        )
        return list(result.scalars().all())
