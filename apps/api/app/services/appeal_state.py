from __future__ import annotations

from app.models.appeal import AppealStatus
from app.services.errors import DomainError

TRANSITIONS: dict[AppealStatus, set[AppealStatus]] = {
    AppealStatus.PENDING: {
        AppealStatus.IN_REVIEW,
        AppealStatus.NEEDS_INFO,
        AppealStatus.ACCEPTED,
        AppealStatus.REJECTED,
        AppealStatus.CLOSED,
    },
    AppealStatus.IN_REVIEW: {
        AppealStatus.NEEDS_INFO,
        AppealStatus.ACCEPTED,
        AppealStatus.REJECTED,
        AppealStatus.CLOSED,
    },
    AppealStatus.NEEDS_INFO: {
        AppealStatus.IN_REVIEW,
        AppealStatus.ACCEPTED,
        AppealStatus.REJECTED,
        AppealStatus.CLOSED,
    },
    AppealStatus.ACCEPTED: {AppealStatus.CLOSED},
    AppealStatus.REJECTED: {AppealStatus.CLOSED},
    AppealStatus.CLOSED: set(),
}


def assert_transition(current: AppealStatus, target: AppealStatus) -> None:
    if current == target:
        return
    allowed = TRANSITIONS.get(current, set())
    if target not in allowed:
        raise DomainError(
            f"Transición de estado no permitida: {current.value} → {target.value}",
            409,
        )


def is_open(status: AppealStatus) -> bool:
    return status in {
        AppealStatus.PENDING,
        AppealStatus.IN_REVIEW,
        AppealStatus.NEEDS_INFO,
    }
