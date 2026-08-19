import pytest

from app.models.billing import CreditTransaction
from app.services.billing import BillingService
from app.services.errors import InsufficientCreditsError, NotFoundError
from tests.fakes import FakeOrgRepo, FakeSession, FakeTxRepo, make_org
from uuid import uuid4


def _billing(org=None) -> tuple[BillingService, object]:
    service = BillingService(FakeSession())
    service.orgs = FakeOrgRepo()
    service.txs = FakeTxRepo()
    if org is not None:
        service.orgs.by_id[org.id] = org
        service.orgs.slugs.add(org.slug)
    return service, org


@pytest.mark.asyncio
async def test_debit_reduces_balance_and_records_transaction():
    org = make_org(credit_balance=50)
    service, _ = _billing(org)
    user_id = uuid4()

    remaining = await service.debit(org.id, user_id, 8, "exam_generate")

    assert remaining == 42
    assert org.credit_balance == 42
    tx = service.txs.items[0]
    assert isinstance(tx, CreditTransaction)
    assert tx.amount == -8
    assert tx.reason == "exam_generate"
    assert tx.balance_after == 42
    assert tx.user_id == user_id


@pytest.mark.asyncio
async def test_debit_raises_when_credits_are_short():
    org = make_org(credit_balance=3)
    service, _ = _billing(org)

    with pytest.raises(InsufficientCreditsError) as caught:
        await service.debit(org.id, uuid4(), 8, "exam_generate")

    assert caught.value.status_code == 402
    assert caught.value.required == 8
    assert caught.value.available == 3
    assert org.credit_balance == 3
    assert service.txs.items == []


@pytest.mark.asyncio
async def test_credit_refunds_generation_cost():
    org = make_org(credit_balance=42)
    service, _ = _billing(org)

    remaining = await service.credit(org.id, uuid4(), 8, "exam_generate_refund")

    assert remaining == 50
    assert org.credit_balance == 50
    assert service.txs.items[0].amount == 8
    assert service.txs.items[0].reason == "exam_generate_refund"


@pytest.mark.asyncio
async def test_zero_amount_does_not_create_a_transaction():
    org = make_org(credit_balance=50)
    service, _ = _billing(org)

    remaining = await service.debit(org.id, uuid4(), 0, "exam_generate")

    assert remaining == 50
    assert service.txs.items == []


@pytest.mark.asyncio
async def test_billing_missing_organization():
    service, _ = _billing()
    with pytest.raises(NotFoundError):
        await service.debit(uuid4(), uuid4(), 1, "exam_generate")
