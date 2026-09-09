from uuid import UUID

from fastapi import APIRouter, Depends, Request, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import RequestContext, get_db, require_roles
from app.schemas.content import (
    BillingCatalogRead,
    BillingCountryUpdate,
    CheckoutRead,
    CheckoutStartRequest,
    CreditBalanceRead,
    CreditTransactionRead,
)
from app.services.billing import BillingService
from app.services.payments.checkout import BILLING_DENIED, CheckoutService
from app.services.permissions import AUTHOR_ROLES

router = APIRouter(tags=["billing"])


@router.get("/billing/credits", response_model=CreditBalanceRead)
async def credit_balance(
    ctx: RequestContext = Depends(require_roles(*AUTHOR_ROLES, detail=BILLING_DENIED)),
    db: AsyncSession = Depends(get_db),
) -> CreditBalanceRead:
    return await BillingService(db).get_balance(ctx.organization_id)


@router.get("/billing/catalog", response_model=BillingCatalogRead)
async def billing_catalog(
    ctx: RequestContext = Depends(require_roles(*AUTHOR_ROLES, detail=BILLING_DENIED)),
    db: AsyncSession = Depends(get_db),
) -> BillingCatalogRead:
    payload = await CheckoutService(db).catalog(ctx.organization_id, ctx.role)
    return BillingCatalogRead.model_validate(payload)


@router.patch("/billing/country", response_model=BillingCatalogRead)
async def update_billing_country(
    payload: BillingCountryUpdate,
    ctx: RequestContext = Depends(require_roles(*AUTHOR_ROLES, detail=BILLING_DENIED)),
    db: AsyncSession = Depends(get_db),
) -> BillingCatalogRead:
    result = await CheckoutService(db).update_country(
        ctx.organization_id, ctx.role, payload.billing_country
    )
    return BillingCatalogRead.model_validate(result)


@router.post("/billing/checkout", response_model=CheckoutRead)
async def start_checkout(
    payload: CheckoutStartRequest,
    ctx: RequestContext = Depends(require_roles(*AUTHOR_ROLES, detail=BILLING_DENIED)),
    db: AsyncSession = Depends(get_db),
) -> CheckoutRead:
    order = await CheckoutService(db).start_checkout(
        ctx.organization_id,
        ctx.user,
        ctx.role,
        payload.pack_id,
        payload.provider,
        plan_id=payload.plan_id,
    )
    return CheckoutRead.model_validate(order)


@router.post("/billing/subscription/cancel", response_model=BillingCatalogRead)
async def cancel_subscription(
    ctx: RequestContext = Depends(require_roles(*AUTHOR_ROLES, detail=BILLING_DENIED)),
    db: AsyncSession = Depends(get_db),
) -> BillingCatalogRead:
    result = await CheckoutService(db).cancel_subscription(ctx.organization_id, ctx.role)
    return BillingCatalogRead.model_validate(result)


@router.post("/billing/orders/{order_id}/simulate", response_model=CheckoutRead)
async def simulate_checkout(
    order_id: UUID,
    ctx: RequestContext = Depends(require_roles(*AUTHOR_ROLES, detail=BILLING_DENIED)),
    db: AsyncSession = Depends(get_db),
) -> CheckoutRead:
    order = await CheckoutService(db).simulate(ctx.organization_id, ctx.user, ctx.role, order_id)
    return CheckoutRead.model_validate(order)


@router.get("/billing/orders", response_model=list[CheckoutRead])
async def list_orders(
    ctx: RequestContext = Depends(require_roles(*AUTHOR_ROLES, detail=BILLING_DENIED)),
    db: AsyncSession = Depends(get_db),
) -> list[CheckoutRead]:
    orders = await CheckoutService(db).list_orders(ctx.organization_id)
    return [CheckoutRead.model_validate(item) for item in orders]


@router.get("/billing/transactions", response_model=list[CreditTransactionRead])
async def list_transactions(
    ctx: RequestContext = Depends(require_roles(*AUTHOR_ROLES, detail=BILLING_DENIED)),
    db: AsyncSession = Depends(get_db),
) -> list[CreditTransactionRead]:
    items = await BillingService(db).list_transactions(ctx.organization_id)
    return [CreditTransactionRead.model_validate(item) for item in items]


@router.post("/billing/webhooks/{provider_id}", status_code=200)
async def payment_webhook(
    provider_id: str,
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> Response:
    body = await request.body()
    headers = {key: value for key, value in request.headers.items()}
    await CheckoutService(db).handle_webhook(provider_id, headers, body)
    return Response(status_code=status.HTTP_200_OK)
