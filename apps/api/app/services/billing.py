from datetime import timedelta, timezone
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.models import CreditTransaction, PlanTier
from app.models.mixins import utcnow
from app.repositories.content import BillingRepository
from app.repositories.identity import OrganizationRepository
from app.schemas.content import CreditBalanceRead
from app.services.errors import InsufficientCreditsError, NotFoundError
from app.services.payments.catalog import PLAN_PERIOD_DAYS, plan_by_id


class BillingService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.orgs = OrganizationRepository(session)
        self.txs = BillingRepository(session)

    async def get_balance(self, organization_id: UUID) -> CreditBalanceRead:
        org = await self.ensure_period(organization_id)
        sku = plan_by_id(org.plan_sku) if org.plan_sku else None
        return CreditBalanceRead(
            organization_id=organization_id,
            balance=org.credit_balance,
            plan=org.plan.value if hasattr(org.plan, "value") else str(org.plan),
            plan_sku=org.plan_sku,
            plan_renews_at=org.plan_renews_at,
            monthly_credits=sku.monthly_credits if sku else None,
        )

    async def ensure_period(self, organization_id: UUID):
        org = await self.orgs.get_for_update(organization_id)
        if org is None:
            raise NotFoundError("Organization not found")
        sku = plan_by_id(org.plan_sku) if org.plan_sku else None
        if sku is None or org.plan_renews_at is None:
            return org
        now = utcnow()
        renews_at = org.plan_renews_at
        if renews_at.tzinfo is None:
            renews_at = renews_at.replace(tzinfo=timezone.utc)
            org.plan_renews_at = renews_at
        granted = 0
        while org.plan_renews_at <= now and granted < 24:
            org.credit_balance += sku.monthly_credits
            await self.txs.add_transaction(
                CreditTransaction(
                    organization_id=organization_id,
                    user_id=None,
                    amount=sku.monthly_credits,
                    reason=f"plan_{sku.id}_renew",
                    balance_after=org.credit_balance,
                )
            )
            org.plan_renews_at = org.plan_renews_at + timedelta(days=PLAN_PERIOD_DAYS)
            granted += 1
        if granted:
            await self.session.commit()
        return org

    async def cancel_subscription(self, organization_id: UUID):
        org = await self.orgs.get_for_update(organization_id)
        if org is None:
            raise NotFoundError("Organization not found")
        org.plan = PlanTier.FREE
        org.plan_sku = None
        org.plan_renews_at = None
        await self.session.commit()
        return org

    async def debit(
        self,
        organization_id: UUID,
        user_id: UUID | None,
        amount: int,
        reason: str,
    ) -> int:
        if amount <= 0:
            org = await self.orgs.get(organization_id)
            if org is None:
                raise NotFoundError("Organization not found")
            return org.credit_balance

        org = await self.orgs.get_for_update(organization_id)
        if org is None:
            raise NotFoundError("Organization not found")
        if org.credit_balance < amount:
            raise InsufficientCreditsError(amount, org.credit_balance)
        org.credit_balance -= amount
        await self.txs.add_transaction(
            CreditTransaction(
                organization_id=organization_id,
                user_id=user_id,
                amount=-amount,
                reason=reason,
                balance_after=org.credit_balance,
            )
        )
        await self.session.flush()
        return org.credit_balance

    async def credit(
        self,
        organization_id: UUID,
        user_id: UUID | None,
        amount: int,
        reason: str,
    ) -> int:
        if amount <= 0:
            org = await self.orgs.get(organization_id)
            if org is None:
                raise NotFoundError("Organization not found")
            return org.credit_balance

        org = await self.orgs.get_for_update(organization_id)
        if org is None:
            raise NotFoundError("Organization not found")
        org.credit_balance += amount
        await self.txs.add_transaction(
            CreditTransaction(
                organization_id=organization_id,
                user_id=user_id,
                amount=amount,
                reason=reason,
                balance_after=org.credit_balance,
            )
        )
        await self.session.flush()
        return org.credit_balance

    async def list_transactions(self, organization_id: UUID, *, limit: int = 40):
        org = await self.orgs.get(organization_id)
        if org is None:
            raise NotFoundError("Organization not found")
        return await self.txs.list_for_org(organization_id, limit=limit)
