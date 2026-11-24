from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest

from app.models.ai_audit import AiDecisionEvent, AiFeature
from app.models.identity import MembershipRole
from app.services.ai_audit import AiAuditService
from app.services.errors import DomainError, ForbiddenError, NotFoundError
from app.services.rate_limit import RateLimitExceeded, check_rate_limit
from tests.fakes import FakeOrgRepo, FakeSession, FakeUserRepo, ensure_id, make_org, make_user


class FakeAiRepo:
    def __init__(self) -> None:
        self.items: list[AiDecisionEvent] = []

    async def add(self, row: AiDecisionEvent) -> AiDecisionEvent:
        ensure_id(row)
        if getattr(row, "created_at", None) is None:
            row.created_at = datetime.now(timezone.utc)
        self.items.append(row)
        return row

    async def list_for_org(self, organization_id, *, feature=None, limit=50, offset=0):
        rows = [item for item in self.items if item.organization_id == organization_id]
        if feature is not None:
            rows = [item for item in rows if item.feature == feature]
        rows.sort(key=lambda item: item.created_at, reverse=True)
        total = len(rows)
        sliced = rows[offset : offset + limit]
        return [(item, None, None) for item in sliced], total

    async def list_for_appeal(self, organization_id, appeal_id):
        target = str(appeal_id)
        return [
            item
            for item in self.items
            if item.organization_id == organization_id
            and item.feature == AiFeature.APPEAL_REVIEW
            and str((item.payload or {}).get("appeal_id") or "") == target
        ]

    async def purge_before(self, cutoff, *, organization_id=None):
        keep = []
        deleted = 0
        for item in self.items:
            if organization_id is not None and item.organization_id != organization_id:
                keep.append(item)
                continue
            if item.created_at < cutoff:
                deleted += 1
            else:
                keep.append(item)
        self.items = keep
        return deleted

    @staticmethod
    def parse_feature(value):
        from app.repositories.ai_audit import AiAuditRepository

        return AiAuditRepository.parse_feature(value)


@pytest.mark.asyncio
async def test_record_and_list_ai_events():
    org = make_org(is_personal=False)
    admin = make_user(email="admin@example.com")
    service = AiAuditService(FakeSession())
    service.repo = FakeAiRepo()
    service.orgs = FakeOrgRepo()
    service.orgs.by_id[org.id] = org
    service.users = FakeUserRepo()

    await service.record(
        organization_id=org.id,
        feature=AiFeature.GENERATION,
        outcome="exam_ready",
        actor_user_id=admin.id,
        payload={"exam_id": str(uuid4()), "kind": "exam"},
    )
    await service.record(
        organization_id=org.id,
        feature=AiFeature.CHAT,
        outcome="answered",
        actor_user_id=admin.id,
    )
    listed = await service.list_events(org.id, MembershipRole.ADMIN, feature="generation")
    assert listed.total == 1
    assert listed.items[0].feature == "generation"
    assert listed.items[0].outcome == "exam_ready"


@pytest.mark.asyncio
async def test_list_ai_events_forbidden_for_member():
    org = make_org(is_personal=False)
    service = AiAuditService(FakeSession())
    service.repo = FakeAiRepo()
    service.orgs = FakeOrgRepo()
    service.orgs.by_id[org.id] = org
    with pytest.raises(ForbiddenError):
        await service.list_events(org.id, MembershipRole.MEMBER)


@pytest.mark.asyncio
async def test_purge_respects_retention():
    org = make_org(is_personal=False)
    service = AiAuditService(FakeSession())
    service.repo = FakeAiRepo()
    service.orgs = FakeOrgRepo()
    service.orgs.by_id[org.id] = org
    old = AiDecisionEvent(
        organization_id=org.id,
        feature=AiFeature.CHAT,
        outcome="answered",
        created_at=datetime.now(timezone.utc) - timedelta(days=120),
    )
    ensure_id(old)
    recent = AiDecisionEvent(
        organization_id=org.id,
        feature=AiFeature.CHAT,
        outcome="answered",
        created_at=datetime.now(timezone.utc),
    )
    ensure_id(recent)
    service.repo.items.extend([old, recent])
    result = await service.purge(org.id, MembershipRole.OWNER, retention_days=90)
    assert result.deleted == 1
    assert len(service.repo.items) == 1


@pytest.mark.asyncio
async def test_export_appeal_not_found():
    org = make_org(is_personal=False)
    service = AiAuditService(FakeSession())
    service.orgs = FakeOrgRepo()
    service.orgs.by_id[org.id] = org

    class EmptyAppeals:
        async def get(self, *_args, **_kwargs):
            return None

    service.appeals = EmptyAppeals()
    with pytest.raises(NotFoundError):
        await service.export_appeal(org.id, uuid4(), MembershipRole.ADMIN, uuid4())


def test_rate_limit_blocks_burst():
    key = f"test:{uuid4()}"
    for _ in range(3):
        check_rate_limit(key, limit=3, window_seconds=60)
    with pytest.raises(RateLimitExceeded):
        check_rate_limit(key, limit=3, window_seconds=60)


@pytest.mark.asyncio
async def test_personal_workspace_cannot_list_ai_audit():
    org = make_org(is_personal=True)
    service = AiAuditService(FakeSession())
    service.repo = FakeAiRepo()
    service.orgs = FakeOrgRepo()
    service.orgs.by_id[org.id] = org
    with pytest.raises(DomainError, match="empresa"):
        await service.list_events(org.id, MembershipRole.OWNER)
