from __future__ import annotations

from app.core.config import Settings
from app.services.payments.port import PaymentGateway
from app.services.payments.simulated import SimulatedGateway
from app.services.payments.stripe_gateway import StripeGateway
from app.services.payments.wompi import WompiGateway


def build_gateways(settings: Settings) -> dict[str, PaymentGateway]:
    """Instantiate every known adapter. Unconfigured ones are omitted.

    Adding a country-specific method does not change CheckoutService: add the
    class here, pack prices, and the id in COUNTRY_PROVIDER_ORDER.
    """
    candidates: list[PaymentGateway] = [
        StripeGateway(
            secret_key=settings.stripe_secret_key,
            webhook_secret=settings.stripe_webhook_secret,
            api_base=settings.stripe_api_base,
        ),
        WompiGateway(
            private_key=settings.wompi_private_key,
            events_secret=settings.wompi_events_secret,
            api_base=settings.wompi_api_base,
            checkout_base=settings.wompi_checkout_base,
        ),
    ]
    if settings.environment != "production" and settings.payment_allow_simulated:
        candidates.append(SimulatedGateway(settings.app_public_url))
    return {gateway.id: gateway for gateway in candidates if gateway.is_configured()}
