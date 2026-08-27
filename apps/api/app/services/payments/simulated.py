from __future__ import annotations

from app.services.payments.port import CheckoutRequest, CheckoutSession, PaymentEvent
from app.services.errors import DomainError


class SimulatedGateway:
    id = "simulated"
    label = "Simulated"
    currencies = frozenset({"usd", "cop"})

    def __init__(self, public_url: str) -> None:
        self.public_url = public_url.rstrip("/")

    def is_configured(self) -> bool:
        return True

    async def create_checkout(self, request: CheckoutRequest) -> CheckoutSession:
        return CheckoutSession(
            provider_session_id=f"sim_{request.order_id}",
            checkout_url=f"{self.public_url}/account?payment=simulate&order={request.order_id}",
        )

    def parse_webhook(self, headers: dict[str, str], body: bytes) -> PaymentEvent:
        raise DomainError("Simulated payments have no webhooks", 400)
