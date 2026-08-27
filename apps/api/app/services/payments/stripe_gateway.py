from __future__ import annotations

import hashlib
import hmac
import json
import time
from typing import Mapping
from uuid import UUID

import httpx

from app.services.errors import DomainError
from app.services.payments.port import (
    CheckoutRequest,
    CheckoutSession,
    GatewayEventStatus,
    PaymentEvent,
)


class StripeGateway:
    id = "stripe"
    label = "Stripe"
    currencies = frozenset({"usd"})

    def __init__(self, secret_key: str, webhook_secret: str, api_base: str) -> None:
        self.secret_key = secret_key
        self.webhook_secret = webhook_secret
        self.api_base = api_base.rstrip("/")

    def is_configured(self) -> bool:
        return bool(self.secret_key)

    async def create_checkout(self, request: CheckoutRequest) -> CheckoutSession:
        data = {
            "mode": "payment",
            "success_url": request.success_url,
            "cancel_url": request.cancel_url,
            "client_reference_id": str(request.order_id),
            "customer_email": request.customer_email,
            "line_items[0][quantity]": "1",
            "line_items[0][price_data][currency]": request.money.currency,
            "line_items[0][price_data][unit_amount]": str(request.money.amount),
            "line_items[0][price_data][product_data][name]": request.description,
            "metadata[order_id]": str(request.order_id),
            "metadata[pack_id]": request.pack_id,
        }
        try:
            async with httpx.AsyncClient(timeout=20.0) as client:
                response = await client.post(
                    f"{self.api_base}/v1/checkout/sessions",
                    data=data,
                    auth=(self.secret_key, ""),
                )
        except httpx.HTTPError as exc:
            raise DomainError("Stripe is unreachable", 502) from exc
        if response.status_code >= 400:
            raise DomainError("Stripe rejected the checkout session", 502)
        payload = response.json()
        session_id = payload.get("id")
        url = payload.get("url")
        if not session_id or not url:
            raise DomainError("Stripe returned an incomplete checkout session", 502)
        return CheckoutSession(provider_session_id=str(session_id), checkout_url=str(url))

    def parse_webhook(self, headers: Mapping[str, str], body: bytes) -> PaymentEvent:
        signature = _header(headers, "stripe-signature")
        if not self.webhook_secret:
            raise DomainError("Stripe webhook secret is not configured", 503)
        if not signature or not _verify_stripe_signature(body, signature, self.webhook_secret):
            raise DomainError("Invalid Stripe webhook signature", 400)
        try:
            payload = json.loads(body.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise DomainError("Invalid Stripe webhook payload", 400) from exc

        event_id = str(payload.get("id") or "")
        event_type = str(payload.get("type") or "")
        session = (payload.get("data") or {}).get("object") or {}
        session_id = str(session.get("id") or "") or None
        order_id = _parse_uuid(session.get("client_reference_id") or (session.get("metadata") or {}).get("order_id"))

        if event_type == "checkout.session.completed" and session.get("payment_status") == "paid":
            status = GatewayEventStatus.PAID
        elif event_type in {"checkout.session.expired", "checkout.session.async_payment_failed"}:
            status = GatewayEventStatus.CANCELED if event_type.endswith("expired") else GatewayEventStatus.FAILED
        else:
            status = GatewayEventStatus.IGNORED

        return PaymentEvent(
            provider=self.id,
            status=status,
            event_id=event_id or session_id or "stripe",
            order_id=order_id,
            provider_session_id=session_id,
        )


def _header(headers: Mapping[str, str], name: str) -> str:
    wanted = name.lower()
    for key, value in headers.items():
        if key.lower() == wanted:
            return value
    return ""


def _parse_uuid(value: object) -> UUID | None:
    if not value:
        return None
    try:
        return UUID(str(value))
    except ValueError:
        return None


def _verify_stripe_signature(payload: bytes, header: str, secret: str, tolerance: int = 300) -> bool:
    timestamp = ""
    signatures: list[str] = []
    for item in header.split(","):
        key, _, value = item.partition("=")
        if key == "t":
            timestamp = value
        elif key == "v1":
            signatures.append(value)
    if not timestamp or not signatures:
        return False
    try:
        issued = int(timestamp)
    except ValueError:
        return False
    if abs(time.time() - issued) > tolerance:
        return False
    signed = f"{timestamp}.".encode() + payload
    expected = hmac.new(secret.encode(), signed, hashlib.sha256).hexdigest()
    return any(hmac.compare_digest(expected, candidate) for candidate in signatures)
