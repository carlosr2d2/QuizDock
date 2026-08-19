from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import RequestContext, get_context, get_db
from app.schemas.auth import OrganizationRead
from app.schemas.content import CreditBalanceRead
from app.services.billing import BillingService

router = APIRouter(tags=["organizations"])


@router.get("/organizations/current", response_model=OrganizationRead)
async def current_organization(ctx: RequestContext = Depends(get_context)) -> OrganizationRead:
    membership = next(
        (m for m in ctx.user.memberships if m.organization_id == ctx.organization_id),
        None,
    )
    if membership is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Organization not found")
    return OrganizationRead.model_validate(membership.organization)


@router.get("/billing/credits", response_model=CreditBalanceRead)
async def credit_balance(
    ctx: RequestContext = Depends(get_context),
    db: AsyncSession = Depends(get_db),
) -> CreditBalanceRead:
    return await BillingService(db).get_balance(ctx.organization_id)
