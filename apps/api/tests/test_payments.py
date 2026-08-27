import hashlib
import hmac
import time
from types import SimpleNamespace

import pytest

from app.models import MembershipRole, PaymentStatus
from app.services.errors import DomainError, ForbiddenError
from app.services.payments.checkout import CheckoutService
from app.services.payments.port import CheckoutRequest, CheckoutSession, GatewayEventStatus, PaymentEvent
from app.services.payments.simulated import SimulatedGateway
from app.services.payments.stripe_gateway import StripeGateway, _verify_stripe_signature
from tests.fakes import (
    FakeOrgRepo,
    FakePaymentOrderRepo,
    FakeSession,
    FakeTxRepo,
    make_org,
    make_user,
)
from app.services.billing import BillingService


class StubGateway:
    def __init__(self, provider_id: str, currencies: set[str], *, label: str | None = None) -> None:
        self.id = provider_id
        self.label = label or provider_id
        self.currencies = frozenset(currencies)
        self.requests: list[CheckoutRequest] = []
        self.fail = False

    def is_configured(self) -> bool:
        return True

    async def create_checkout(self, request: CheckoutRequest) -> CheckoutSession:
        if self.fail:
            raise DomainError("gateway down", 502)
        self.requests.append(request)
        return CheckoutSession(
            provider_session_id=f"{self.id}_{request.order_id}",
            checkout_url=f"https://pay.example/{self.id}/{request.order_id}",
        )

    def parse_webhook(self, headers: dict[str, str], body: bytes) -> PaymentEvent:
        raise AssertionError("use handle_webhook with an injected event")


def _service(org, *, country: str = "CO", gateways: dict | None = None) -> CheckoutService:
    if gateways is None:
        gateways = {
            "wompi": StubGateway("wompi", {"cop"}),
            "stripe": StubGateway("stripe", {"usd"}),
            "simulated": SimulatedGateway("http://localhost:3000"),
        }
    service = CheckoutService(
        FakeSession(),
        settings=SimpleNamespace(app_public_url="http://localhost:3000", payment_default_country="CO"),
        gateways=gateways,
    )
    org.billing_country = country
    service.orgs = FakeOrgRepo()
    service.orgs.by_id[org.id] = org
    service.orders = FakePaymentOrderRepo()
    service.billing = BillingService(FakeSession())
    service.billing.orgs = service.orgs
    service.billing.txs = FakeTxRepo()
    return service


@pytest.mark.asyncio
async def test_colombia_prefers_wompi_over_stripe():
    org = make_org()
    service = _service(org, country="CO")
    catalog = await service.catalog(org.id, MembershipRole.OWNER)
    assert catalog["default_provider"] == "wompi"
    assert [item["id"] for item in catalog["providers"]][0] == "wompi"
    starter = next(item for item in catalog["packs"] if item["id"] == "starter")
    assert {price["provider"] for price in starter["prices"]} >= {"wompi", "stripe", "simulated"}


@pytest.mark.asyncio
async def test_us_prefers_stripe():
    org = make_org()
    service = _service(org, country="US")
    catalog = await service.catalog(org.id, MembershipRole.OWNER)
    assert catalog["default_provider"] == "stripe"
    assert [item["id"] for item in catalog["providers"]] == ["stripe", "simulated"]


@pytest.mark.asyncio
async def test_local_provider_is_offered_only_in_its_country(monkeypatch):
    from app.services.payments import catalog as catalog_mod
    from app.services.payments import checkout as checkout_mod
    from app.services.payments.catalog import CreditPack
    from app.services.payments.port import Money

    monkeypatch.setattr(
        catalog_mod,
        "COUNTRY_PROVIDER_ORDER",
        {"CO": ("wompi", "epayco", "simulated", "stripe")},
    )
    monkeypatch.setattr(catalog_mod, "DEFAULT_PROVIDER_ORDER", ("stripe", "simulated"))
    packs = tuple(
        CreditPack(
            id=pack.id,
            credits=pack.credits,
            prices={**pack.prices, "epayco": Money(3_600_000, "cop")},
        )
        for pack in catalog_mod.PACKS
    )
    monkeypatch.setattr(catalog_mod, "PACKS", packs)
    monkeypatch.setattr(catalog_mod, "PACKS_BY_ID", {pack.id: pack for pack in packs})
    monkeypatch.setattr(checkout_mod, "PACKS", packs)

    org_co = make_org(billing_country="CO")
    org_us = make_org(billing_country="US")
    gateways = {
        "wompi": StubGateway("wompi", {"cop"}),
        "epayco": StubGateway("epayco", {"cop"}, label="ePayco"),
        "stripe": StubGateway("stripe", {"usd"}),
        "simulated": SimulatedGateway("http://localhost:3000"),
    }
    colombia = _service(org_co, country="CO", gateways=gateways)
    united_states = _service(org_us, country="US", gateways=gateways)

    catalog_co = await colombia.catalog(org_co.id, MembershipRole.OWNER)
    catalog_us = await united_states.catalog(org_us.id, MembershipRole.OWNER)

    assert [item["id"] for item in catalog_co["providers"]] == ["wompi", "epayco", "simulated", "stripe"]
    assert catalog_co["providers"][1]["label"] == "ePayco"
    assert "epayco" not in [item["id"] for item in catalog_us["providers"]]

    user = make_user()
    order = await colombia.start_checkout(org_co.id, user, MembershipRole.OWNER, "starter", "epayco")
    assert order.provider == "epayco"
    assert order.currency == "cop"


@pytest.mark.asyncio
async def test_member_cannot_start_checkout():
    org = make_org()
    user = make_user()
    service = _service(org)
    with pytest.raises(ForbiddenError):
        await service.start_checkout(org.id, user, MembershipRole.MEMBER, "starter", "wompi")


@pytest.mark.asyncio
async def test_checkout_creates_pending_order_with_provider_url():
    org = make_org(credit_balance=10)
    user = make_user()
    service = _service(org)
    order = await service.start_checkout(org.id, user, MembershipRole.OWNER, "starter", "wompi")
    assert order.status == PaymentStatus.PENDING
    assert order.provider == "wompi"
    assert order.credits == 50
    assert order.currency == "cop"
    assert order.checkout_url.startswith("https://pay.example/wompi/")
    assert org.credit_balance == 10


@pytest.mark.asyncio
async def test_webhook_credits_once():
    org = make_org(credit_balance=10)
    user = make_user()
    service = _service(org)
    order = await service.start_checkout(org.id, user, MembershipRole.OWNER, "starter", "wompi")
    event = PaymentEvent(
        provider="wompi",
        status=GatewayEventStatus.PAID,
        event_id="evt_1",
        order_id=order.id,
        provider_session_id=order.provider_session_id,
    )
    first = await service._apply_event(event)
    second = await service._apply_event(event)
    assert first.status == PaymentStatus.COMPLETED
    assert second.status == PaymentStatus.COMPLETED
    assert org.credit_balance == 60
    assert len(service.billing.txs.items) == 1


@pytest.mark.asyncio
async def test_simulate_checkout_adds_credits():
    org = make_org(credit_balance=0)
    user = make_user()
    service = _service(org)
    order = await service.start_checkout(org.id, user, MembershipRole.OWNER, "starter", "simulated")
    completed = await service.simulate(org.id, user, MembershipRole.OWNER, order.id)
    assert completed.status == PaymentStatus.COMPLETED
    assert org.credit_balance == 50


def test_stripe_signature_roundtrip():
    payload = b'{"id":"evt_1"}'
    secret = "whsec_test"
    timestamp = "1700000000"
    signed = timestamp.encode() + b"." + payload
    digest = hmac.new(secret.encode(), signed, hashlib.sha256).hexdigest()
    header = f"t={timestamp},v1={digest}"
    assert _verify_stripe_signature(payload, header, secret, tolerance=10**9)


def test_stripe_parse_paid_session():
    secret = "whsec_test"
    gateway = StripeGateway("sk_test", secret, "https://api.stripe.com")
    body = (
        b'{"id":"evt_1","type":"checkout.session.completed","data":{"object":{'
        b'"id":"cs_test","payment_status":"paid","client_reference_id":'
        b'"aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"}}}'
    )
    timestamp = str(int(time.time()))
    digest = hmac.new(secret.encode(), f"{timestamp}.".encode() + body, hashlib.sha256).hexdigest()
    event = gateway.parse_webhook({"stripe-signature": f"t={timestamp},v1={digest}"}, body)
    assert event.status is GatewayEventStatus.PAID
    assert str(event.order_id) == "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"
    assert event.provider_session_id == "cs_test"


def test_production_omits_simulated_gateway():
    from app.services.payments import build_gateways

    gateways = build_gateways(
        SimpleNamespace(
            environment="production",
            payment_allow_simulated=True,
            app_public_url="http://localhost:3000",
            stripe_secret_key="sk_live",
            stripe_webhook_secret="whsec",
            stripe_api_base="https://api.stripe.com",
            wompi_private_key="prv_live",
            wompi_events_secret="evts",
            wompi_api_base="https://production.wompi.co/v1",
            wompi_checkout_base="https://checkout.wompi.co/l",
        )
    )
    assert "simulated" not in gateways
    assert set(gateways) == {"stripe", "wompi"}
