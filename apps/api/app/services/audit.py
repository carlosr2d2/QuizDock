from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.models import MembershipRole, Organization
from app.models.audit import AuditAction, AuditEvent
from app.models.mixins import utcnow
from app.repositories.audit import AuditRepository
from app.repositories.identity import OrganizationRepository
from app.schemas.audit import AuditEventList, AuditEventRead
from app.services.errors import DomainError, ForbiddenError

READ_ROLES = {MembershipRole.OWNER, MembershipRole.ADMIN, MembershipRole.AUDITOR}


class AuditService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.repo = AuditRepository(session)
        self.orgs = OrganizationRepository(session)

    async def record(
        self,
        organization_id: UUID,
        action: AuditAction,
        *,
        actor_user_id: UUID | None = None,
        actor_role: MembershipRole | None = None,
        target_type: str,
        target_id: UUID | None = None,
        summary: str,
        payload: dict | None = None,
    ) -> AuditEvent | None:
        org = await self._auditable_org(organization_id)
        if org is None:
            return None
        event = AuditEvent(
            organization_id=organization_id,
            actor_user_id=actor_user_id,
            actor_role=actor_role,
            action=action,
            target_type=target_type,
            target_id=target_id,
            summary=summary[:240],
            payload=payload or {},
            created_at=utcnow(),
        )
        return await self.repo.add(event)

    async def list_events(
        self,
        organization_id: UUID,
        role: MembershipRole,
        *,
        limit: int = 50,
        offset: int = 0,
    ) -> AuditEventList:
        org = await self._org(organization_id)
        if org.is_personal:
            raise DomainError("El registro de auditoría está en un workspace de empresa.")
        if role not in READ_ROLES:
            raise ForbiddenError("Solo el propietario, un administrador o un auditor puede ver la auditoría.")
        rows, total = await self.repo.list_for_org(organization_id, limit=limit, offset=offset)
        return AuditEventList(
            items=[
                AuditEventRead(
                    id=event.id,
                    organization_id=event.organization_id,
                    actor_user_id=event.actor_user_id,
                    actor_email=email,
                    actor_full_name=full_name,
                    actor_role=event.actor_role,
                    action=event.action,
                    target_type=event.target_type,
                    target_id=event.target_id,
                    summary=event.summary,
                    payload=event.payload or {},
                    created_at=event.created_at,
                )
                for event, email, full_name in rows
            ],
            total=total,
            limit=limit,
            offset=offset,
        )

    async def _org(self, organization_id: UUID) -> Organization:
        org = await self.orgs.get(organization_id)
        if org is None:
            raise DomainError("Organization not found", status_code=404)
        return org

    async def _auditable_org(self, organization_id: UUID) -> Organization | None:
        org = await self.orgs.get(organization_id)
        if org is None or org.is_personal:
            return None
        return org
