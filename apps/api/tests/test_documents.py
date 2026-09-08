from uuid import uuid4

import pytest

from app.models import MembershipRole
from app.services.content import DocumentService
from app.services.errors import ForbiddenError, NotFoundError
from tests.fakes import FakeAuditService, FakeDocumentRepo, FakeSession, make_document, make_org


def _documents(org, document=None) -> DocumentService:
    service = DocumentService(FakeSession())
    service.repo = FakeDocumentRepo()
    service.audit = FakeAuditService()
    if document is not None:
        service.repo.by_id[document.id] = document
    return service


@pytest.mark.asyncio
async def test_owner_can_delete_document():
    org = make_org()
    document = make_document(org.id, uuid4())
    service = _documents(org, document)

    await service.delete(document.id, org.id, MembershipRole.OWNER)

    assert document.id not in service.repo.by_id
    assert service.session.commits == 1


@pytest.mark.asyncio
async def test_member_cannot_delete_document():
    org = make_org()
    document = make_document(org.id, uuid4())
    service = _documents(org, document)

    with pytest.raises(ForbiddenError):
        await service.delete(document.id, org.id, MembershipRole.MEMBER)

    assert document.id in service.repo.by_id


@pytest.mark.asyncio
async def test_delete_does_not_cross_organizations():
    org = make_org()
    other = make_org(slug="other")
    document = make_document(other.id, uuid4())
    service = _documents(org, document)

    with pytest.raises(NotFoundError):
        await service.delete(document.id, org.id, MembershipRole.OWNER)

    assert document.id in service.repo.by_id
