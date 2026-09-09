from dataclasses import dataclass

from app.models.identity import Organization, PlanTier
from app.services.payments.catalog import PLANS, plan_by_id


@dataclass(frozen=True)
class PlanLimits:
    tier: PlanTier
    seats: int | None
    can_invite: bool


def _tier(org: Organization) -> PlanTier:
    plan = org.plan
    if isinstance(plan, PlanTier):
        return plan
    raw = str(plan).split(".")[-1].lower()
    try:
        return PlanTier(raw)
    except ValueError:
        return PlanTier.FREE


def limits_for(org: Organization) -> PlanLimits:
    sku = plan_by_id(org.plan_sku) if getattr(org, "plan_sku", None) else None
    if sku is not None:
        return PlanLimits(tier=sku.tier, seats=sku.seats, can_invite=not sku.personal_only)
    return _fallback(_tier(org))


def _fallback(tier: PlanTier) -> PlanLimits:
    if tier == PlanTier.FREE:
        return PlanLimits(tier=tier, seats=1, can_invite=False)
    match = next((item for item in PLANS if item.tier == tier and item.id == tier.value), None)
    if match is None:
        match = next((item for item in PLANS if item.tier == tier), None)
    if match is None:
        return PlanLimits(tier=tier, seats=1, can_invite=False)
    return PlanLimits(tier=tier, seats=match.seats, can_invite=not match.personal_only)
