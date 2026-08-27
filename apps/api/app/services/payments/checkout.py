from __future__ import annotations

from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings, get_settings
from app.models import MembershipRole, PaymentOrder, PaymentStatus, User
from app.models.mixins import utcnow
from app.repositories.identity import OrganizationRepository
from app.repositories.payments import PaymentOrderRepository
from app.services.billing import BillingService
from app.services.errors import ConflictError, DomainError, ForbiddenError, NotFoundError
from app.services.payments import build_gateways
from app.services.payments.catalog import pack_by_id, PACKS, provider_order_for
from app.services.payments.port import CheckoutRequest, GatewayEventStatus, PaymentGateway, PaymentEvent
from app.services.permissions import AUTHOR_ROLES

BILLING_DENIED = "Solo el propietario o un administrador puede comprar créditos."


class CheckoutService:
    def __init__(
        self,
        session: AsyncSession,
        *,
        settings: Settings | None = None,
        gateways: dict[str, PaymentGateway] | None = None,
    ) -> None:
        self.session = session
        self.settings = settings or get_settings()
        self.gateways = gateways if gateways is not None else build_gateways(self.settings)
        self.orgs = OrganizationRepository(session)
        self.orders = PaymentOrderRepository(session)
        self.billing = BillingService(session)

    def available_providers(self, country: str) -> list[str]:
        return [provider_id for provider_id in provider_order_for(country) if provider_id in self.gateways]

    async def catalog(self, organization_id: UUID, role: MembershipRole) -> dict:
        org = await self.orgs.get(organization_id)
        if org is None:
            raise NotFoundError("Organization not found")
        country = (org.billing_country or self.settings.payment_default_country).upper()
        providers = self.available_providers(country)
        default_provider = providers[0] if providers else None
        packs = []
        for pack in PACKS:
            prices = []
            for provider_id in providers:
                money = pack.prices.get(provider_id)
                gateway = self.gateways.get(provider_id)
                if money is None or gateway is None:
                    continue
                if money.currency not in gateway.currencies:
                    continue
                prices.append(
                    {
                        "provider": provider_id,
                        "amount": money.amount,
                        "currency": money.currency,
                    }
                )
            packs.append({"id": pack.id, "credits": pack.credits, "prices": prices})
        return {
            "billing_country": country,
            "default_provider": default_provider,
            "can_purchase": role in AUTHOR_ROLES,
            "providers": [
                {
                    "id": provider_id,
                    "label": getattr(self.gateways[provider_id], "label", provider_id),
                    "recommended": provider_id == default_provider,
                    "currencies": sorted(self.gateways[provider_id].currencies),
                }
                for provider_id in providers
            ],
            "packs": packs,
        }

    async def update_country(self, organization_id: UUID, role: MembershipRole, country: str) -> dict:
        self._require_buyer(role)
        org = await self.orgs.get(organization_id)
        if org is None:
            raise NotFoundError("Organization not found")
        resolved = country.strip().upper()
        if len(resolved) != 2 or not resolved.isalpha():
            raise DomainError("Invalid billing country", 400)
        org.billing_country = resolved
        await self.session.commit()
        return await self.catalog(organization_id, role)

    async def start_checkout(
        self,
        organization_id: UUID,
        user: User,
        role: MembershipRole,
        pack_id: str,
        provider_id: str | None,
    ) -> PaymentOrder:
        self._require_buyer(role)
        org = await self.orgs.get(organization_id)
        if org is None:
            raise NotFoundError("Organization not found")
        pack = pack_by_id(pack_id)
        if pack is None:
            raise NotFoundError("Unknown credit pack")
        country = (org.billing_country or self.settings.payment_default_country).upper()
        providers = self.available_providers(country)
        if not providers:
            raise DomainError("No payment provider is configured", 503)
        resolved_provider = provider_id or providers[0]
        if resolved_provider not in self.gateways or resolved_provider not in providers:
            raise DomainError("Payment provider is not available", 400)
        gateway = self.gateways[resolved_provider]
        money = pack.prices.get(resolved_provider)
        if money is None or money.currency not in gateway.currencies:
            raise DomainError("This pack is not available for the selected provider", 400)

        order = PaymentOrder(
            organization_id=organization_id,
            user_id=user.id,
            provider=resolved_provider,
            pack_id=pack.id,
            credits=pack.credits,
            amount=money.amount,
            currency=money.currency,
            status=PaymentStatus.PENDING,
        )
        await self.orders.add(order)
        public = self.settings.app_public_url.rstrip("/")
        try:
            session = await gateway.create_checkout(
                CheckoutRequest(
                    order_id=order.id,
                    pack_id=pack.id,
                    credits=pack.credits,
                    money=money,
                    customer_email=user.email,
                    success_url=f"{public}/account?payment=success",
                    cancel_url=f"{public}/account?payment=cancel",
                    description=f"QuizDock {pack.credits} credits",
                )
            )
        except DomainError:
            order.status = PaymentStatus.FAILED
            await self.session.commit()
            raise
        order.provider_session_id = session.provider_session_id
        order.checkout_url = session.checkout_url
        await self.session.commit()
        return order

    async def simulate(
        self,
        organization_id: UUID,
        user: User,
        role: MembershipRole,
        order_id: UUID,
    ) -> PaymentOrder:
        self._require_buyer(role)
        order = await self.orders.get(order_id, organization_id)
        if order is None:
            raise NotFoundError("Payment order not found")
        if order.provider != "simulated":
            raise DomainError("Only simulated checkouts can be confirmed locally", 400)
        if order.user_id != user.id:
            raise ForbiddenError(BILLING_DENIED)
        return await self._apply_event(
            PaymentEvent(
                provider="simulated",
                status=GatewayEventStatus.PAID,
                event_id=f"sim_{order.id}",
                order_id=order.id,
                provider_session_id=order.provider_session_id,
            )
        )

    async def handle_webhook(self, provider_id: str, headers: dict[str, str], body: bytes) -> None:
        gateway = self.gateways.get(provider_id)
        if gateway is None:
            raise NotFoundError("Unknown payment provider")
        event = gateway.parse_webhook(headers, body)
        if event.status is GatewayEventStatus.IGNORED:
            return
        await self._apply_event(event)

    async def list_orders(self, organization_id: UUID) -> list[PaymentOrder]:
        return await self.orders.list_for_org(organization_id)

    async def _apply_event(self, event: PaymentEvent) -> PaymentOrder:
        order = None
        if event.order_id is not None:
            order = await self.orders.get_for_update(event.order_id)
        if order is None and event.provider_session_id:
            order = await self.orders.get_by_provider_session(event.provider, event.provider_session_id)
            if order is not None:
                locked = await self.orders.get_for_update(order.id)
                order = locked
        if order is None:
            raise NotFoundError("Payment order not found")
        if event.provider != order.provider:
            raise DomainError("Payment provider mismatch", 400)

        if event.status is GatewayEventStatus.PAID:
            if order.status == PaymentStatus.COMPLETED:
                return order
            if order.status != PaymentStatus.PENDING:
                raise ConflictError("Payment order cannot be completed")
            await self.billing.credit(
                order.organization_id,
                order.user_id,
                order.credits,
                f"pack_{order.pack_id}",
            )
            order.status = PaymentStatus.COMPLETED
            order.completed_at = utcnow()
            order.provider_event_id = event.event_id
            await self.session.commit()
            return order

        if order.status == PaymentStatus.PENDING:
            order.status = (
                PaymentStatus.CANCELED if event.status is GatewayEventStatus.CANCELED else PaymentStatus.FAILED
            )
            order.provider_event_id = event.event_id
            await self.session.commit()
        return order

    def _require_buyer(self, role: MembershipRole) -> None:
        if role not in AUTHOR_ROLES:
            raise ForbiddenError(BILLING_DENIED)
