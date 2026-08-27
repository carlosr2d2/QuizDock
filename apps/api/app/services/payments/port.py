from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Mapping, Protocol
from uuid import UUID


class GatewayEventStatus(StrEnum):
    PAID = "paid"
    FAILED = "failed"
    CANCELED = "canceled"
    IGNORED = "ignored"


@dataclass(frozen=True)
class Money:
    amount: int
    currency: str


@dataclass(frozen=True)
class CheckoutRequest:
    order_id: UUID
    pack_id: str
    credits: int
    money: Money
    customer_email: str
    success_url: str
    cancel_url: str
    description: str


@dataclass(frozen=True)
class CheckoutSession:
    provider_session_id: str
    checkout_url: str


@dataclass(frozen=True)
class PaymentEvent:
    provider: str
    status: GatewayEventStatus
    event_id: str
    order_id: UUID | None = None
    provider_session_id: str | None = None


class PaymentGateway(Protocol):
    id: str
    label: str
    currencies: frozenset[str]

    def is_configured(self) -> bool: ...

    async def create_checkout(self, request: CheckoutRequest) -> CheckoutSession: ...

    def parse_webhook(self, headers: Mapping[str, str], body: bytes) -> PaymentEvent: ...
