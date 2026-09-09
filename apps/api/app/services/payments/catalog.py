from __future__ import annotations

from dataclasses import dataclass

from app.models.identity import PlanTier
from app.services.payments.port import Money


@dataclass(frozen=True)
class CreditPack:
    id: str
    credits: int
    prices: dict[str, Money]


@dataclass(frozen=True)
class SubscriptionPlan:
    id: str
    tier: PlanTier
    monthly_credits: int
    personal_only: bool
    seats: int | None
    prices: dict[str, Money]


PLAN_PERIOD_DAYS = 30

# Amounts are in the currency's minor unit (USD cents, COP cents).
PACKS: tuple[CreditPack, ...] = (
    CreditPack(
        id="starter",
        credits=50,
        prices={
            "stripe": Money(900, "usd"),
            "wompi": Money(3_600_000, "cop"),
            "simulated": Money(3_600_000, "cop"),
        },
    ),
    CreditPack(
        id="plus",
        credits=200,
        prices={
            "stripe": Money(1_900, "usd"),
            "wompi": Money(7_600_000, "cop"),
            "simulated": Money(7_600_000, "cop"),
        },
    ),
    CreditPack(
        id="team",
        credits=1000,
        prices={
            "stripe": Money(19_900, "usd"),
            "wompi": Money(79_900_000, "cop"),
            "simulated": Money(79_900_000, "cop"),
        },
    ),
)

PACKS_BY_ID = {pack.id: pack for pack in PACKS}

PLANS: tuple[SubscriptionPlan, ...] = (
    SubscriptionPlan(
        id="individual",
        tier=PlanTier.INDIVIDUAL,
        monthly_credits=80,
        personal_only=True,
        seats=1,
        prices={
            "stripe": Money(900, "usd"),
            "wompi": Money(3_600_000, "cop"),
            "simulated": Money(3_600_000, "cop"),
        },
    ),
    SubscriptionPlan(
        id="individual_plus",
        tier=PlanTier.INDIVIDUAL,
        monthly_credits=200,
        personal_only=True,
        seats=1,
        prices={
            "stripe": Money(1_900, "usd"),
            "wompi": Money(7_600_000, "cop"),
            "simulated": Money(7_600_000, "cop"),
        },
    ),
    SubscriptionPlan(
        id="team",
        tier=PlanTier.TEAM,
        monthly_credits=1000,
        personal_only=False,
        seats=25,
        prices={
            "stripe": Money(19_900, "usd"),
            "wompi": Money(79_900_000, "cop"),
            "simulated": Money(79_900_000, "cop"),
        },
    ),
    SubscriptionPlan(
        id="enterprise",
        tier=PlanTier.ENTERPRISE,
        monthly_credits=5000,
        personal_only=False,
        seats=None,
        prices={
            "stripe": Money(49_900, "usd"),
            "wompi": Money(199_900_000, "cop"),
            "simulated": Money(199_900_000, "cop"),
        },
    ),
)

PLANS_BY_ID = {plan.id: plan for plan in PLANS}

# Ordered allowlist per ISO country. Only configured ids in the tuple are offered.
# To add a local method (e.g. ePayco in CO, Mercado Pago in MX):
#   1. Implement PaymentGateway (create_checkout + parse_webhook).
#   2. Register it in build_gateways.
#   3. Add pack prices keyed by that id.
#   4. Insert the id in the country tuple below (position = preference).
COUNTRY_PROVIDER_ORDER: dict[str, tuple[str, ...]] = {
    "CO": ("wompi", "simulated", "stripe"),
}

# Used when the country has no specific tuple.
DEFAULT_PROVIDER_ORDER: tuple[str, ...] = ("stripe", "simulated")


def pack_by_id(pack_id: str) -> CreditPack | None:
    return PACKS_BY_ID.get(pack_id)


def plan_by_id(plan_id: str) -> SubscriptionPlan | None:
    return PLANS_BY_ID.get(plan_id)


def provider_order_for(country: str) -> tuple[str, ...]:
    return COUNTRY_PROVIDER_ORDER.get(country.upper(), DEFAULT_PROVIDER_ORDER)
