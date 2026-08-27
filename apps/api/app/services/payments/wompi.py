from __future__ import annotations

import hashlib
import json
from typing import Any, Mapping
from uuid import UUID

import httpx

from app.services.errors import DomainError
from app.services.payments.port import (
    CheckoutRequest,
    CheckoutSession,
    GatewayEventStatus,
    PaymentEvent,
)


class WompiGateway:
    id = "wompi"
    label = "Wompi"
    currencies = frozenset({"cop"})

    def __init__(
        self,
        private_key: str,
        events_secret: str,
        api_base: str,
        checkout_base: str,
    ) -> None:
        self.private_key = private_key
        self.events_secret = events_secret
        self.api_base = api_base.rstrip("/")
        self.checkout_base = checkout_base.rstrip("/")

    def is_configured(self) -> bool:
        return bool(self.private_key)

    async def create_checkout(self, request: CheckoutRequest) -> CheckoutSession:
        payload = {
            "name": request.description,
            "description": request.pack_id,
            "single_use": True,
            "collect_shipping": False,
            "currency": request.money.currency.upper(),
            "amount_in_cents": request.money.amount,
            "redirect_url": request.success_url,
        }
        try:
            async with httpx.AsyncClient(timeout=20.0) as client:
                response = await client.post(
                    f"{self.api_base}/payment_links",
                    json=payload,
                    headers={"Authorization": f"Bearer {self.private_key}"},
                )
        except httpx.HTTPError as exc:
            raise DomainError("Wompi is unreachable", 502) from exc
        if response.status_code >= 400:
            raise DomainError("Wompi rejected the payment link", 502)
        data = (response.json() or {}).get("data") or {}
        link_id = data.get("id")
        if not link_id:
            raise DomainError("Wompi returned an incomplete payment link", 502)
        return CheckoutSession(
            provider_session_id=str(link_id),
            checkout_url=f"{self.checkout_base}/{link_id}",
        )

    def parse_webhook(self, headers: Mapping[str, str], body: bytes) -> PaymentEvent:
        try:
            payload = json.loads(body.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise DomainError("Invalid Wompi webhook payload", 400) from exc

        if not self.events_secret:
            raise DomainError("Wompi events secret is not configured", 503)
        if not _verify_wompi_signature(payload, self.events_secret):
            raise DomainError("Invalid Wompi webhook signature", 400)

        transaction = ((payload.get("data") or {}).get("transaction")) or {}
        status_raw = str(transaction.get("status") or "").upper()
        if status_raw == "APPROVED":
            status = GatewayEventStatus.PAID
        elif status_raw in {"DECLINED", "ERROR", "VOIDED"}:
            status = GatewayEventStatus.FAILED
        else:
            status = GatewayEventStatus.IGNORED

        event_id = str(payload.get("id") or transaction.get("id") or "wompi")
        return PaymentEvent(
            provider=self.id,
            status=status,
            event_id=event_id,
            order_id=_parse_uuid(transaction.get("reference")),
            provider_session_id=str(transaction.get("payment_link_id") or "") or None,
        )


def _parse_uuid(value: object) -> UUID | None:
    if not value:
        return None
    try:
        return UUID(str(value))
    except ValueError:
        return None


def _nested_get(payload: dict[str, Any], path: str) -> str:
    current: Any = payload.get("data") or payload
    for part in path.split("."):
        if not isinstance(current, dict):
            return ""
        current = current.get(part)
    return "" if current is None else str(current)


def _verify_wompi_signature(payload: dict[str, Any], secret: str) -> bool:
    signature = payload.get("signature") or {}
    checksum = str(signature.get("checksum") or "")
    properties = signature.get("properties") or []
    if not checksum or not isinstance(properties, list):
        return False
    concatenated = "".join(_nested_get(payload, str(item)) for item in properties) + secret
    expected = hashlib.sha256(concatenated.encode()).hexdigest()
    return expected.lower() == checksum.lower()
