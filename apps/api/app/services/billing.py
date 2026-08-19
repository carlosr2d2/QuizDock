from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.models import CreditTransaction
from app.repositories.content import BillingRepository
from app.repositories.identity import OrganizationRepository
from app.schemas.content import CreditBalanceRead
from app.services.errors import InsufficientCreditsError, NotFoundError


class BillingService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.orgs = OrganizationRepository(session)
        self.txs = BillingRepository(session)

    async def get_balance(self, organization_id: UUID) -> CreditBalanceRead:
        org = await self.orgs.get(organization_id)
        if org is None:
            raise NotFoundError("Organization not found")
        return CreditBalanceRead(
            organization_id=organization_id,
            balance=org.credit_balance,
            plan=org.plan.value,
        )

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
