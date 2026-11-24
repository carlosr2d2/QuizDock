import pytest

from app.models.appeal import AppealStatus
from app.services.appeal_state import TRANSITIONS, assert_transition, is_open
from app.services.errors import DomainError


def test_pending_can_move_to_review_and_terminal():
    assert AppealStatus.IN_REVIEW in TRANSITIONS[AppealStatus.PENDING]
    assert AppealStatus.ACCEPTED in TRANSITIONS[AppealStatus.PENDING]
    assert AppealStatus.REJECTED in TRANSITIONS[AppealStatus.PENDING]


def test_closed_is_terminal():
    assert TRANSITIONS[AppealStatus.CLOSED] == set()
    assert_transition(AppealStatus.CLOSED, AppealStatus.CLOSED)
    with pytest.raises(DomainError, match="no permitida"):
        assert_transition(AppealStatus.CLOSED, AppealStatus.PENDING)


def test_needs_info_can_return_to_review():
    assert_transition(AppealStatus.NEEDS_INFO, AppealStatus.IN_REVIEW)


def test_is_open_flags():
    assert is_open(AppealStatus.PENDING)
    assert is_open(AppealStatus.IN_REVIEW)
    assert is_open(AppealStatus.NEEDS_INFO)
    assert not is_open(AppealStatus.ACCEPTED)
    assert not is_open(AppealStatus.REJECTED)
    assert not is_open(AppealStatus.CLOSED)
