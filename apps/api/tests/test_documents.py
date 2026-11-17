from uuid import uuid4

import pytest

from app.models import MembershipRole
from app.schemas.content import DocumentCreate
from app.services.content import DocumentService
from app.services.errors import ConflictError, ForbiddenError, NotFoundError
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


@pytest.mark.asyncio
async def test_create_rejects_duplicate_filename(monkeypatch):
    org = make_org()
    existing = make_document(org.id, uuid4(), filename="guia.pdf")
    service = _documents(org, existing)
    monkeypatch.setattr("app.services.content.enqueue", lambda *args, **kwargs: True)

    with pytest.raises(ConflictError, match=r"(?i)guia\.pdf"):
        await service.create(
            org.id,
            uuid4(),
            MembershipRole.OWNER,
            DocumentCreate(filename="Guia.PDF", content_type="application/pdf"),
        )

    assert len(service.repo.by_id) == 1


@pytest.mark.asyncio
async def test_create_allows_same_filename_in_another_workspace(monkeypatch):
    org = make_org()
    other = make_org(slug="other-workspace")
    existing = make_document(other.id, uuid4(), filename="guia.pdf")
    service = _documents(org, existing)
    monkeypatch.setattr("app.services.content.enqueue", lambda *args, **kwargs: True)

    document = await service.create(
        org.id,
        uuid4(),
        MembershipRole.OWNER,
        DocumentCreate(filename="guia.pdf", content_type="application/pdf"),
    )

    assert document.filename == "guia.pdf"
    assert document.organization_id == org.id
    assert len(service.repo.by_id) == 2
