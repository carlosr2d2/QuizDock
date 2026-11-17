from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from uuid import UUID
import logging
import secrets

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.text import slugify
from app.models import Invitation, Membership, MembershipRole, Organization, PlanTier, User
from app.models.audit import AuditAction
from app.models.group import Group, GroupMember
from app.models.identity import InvitationStatus
from app.models.mixins import utcnow
from app.repositories.groups import GroupRepository
from app.repositories.identity import (
    InvitationRepository,
    MembershipRepository,
    OrganizationRepository,
    UserRepository,
)
from app.schemas.auth import OrganizationRead
from app.schemas.team import (
    GroupRead,
    InvitationAcceptRead,
    InvitationPublic,
    InvitationRead,
    MemberRead,
    MyInvitationRead,
    TeamSnapshot,
)
from app.services.audit import AuditService
from app.services.errors import ConflictError, DomainError, ForbiddenError, NotFoundError
from app.services.mail import MailError, Mailer, build_invite_email, get_mailer, invite_accept_url
from app.services.plans import limits_for

MANAGE_ROLES = {MembershipRole.OWNER, MembershipRole.ADMIN}
INVITABLE_ROLES = {MembershipRole.ADMIN, MembershipRole.MEMBER, MembershipRole.AUDITOR}
INVITE_DAYS = 14

logger = logging.getLogger(__name__)


@dataclass
class InviteOutcome:
    invitation: Invitation
    email_sent: bool


class TeamService:
    def __init__(self, session: AsyncSession, mailer: Mailer | None = None) -> None:
        self.session = session
        self.users = UserRepository(session)
        self.orgs = OrganizationRepository(session)
        self.memberships = MembershipRepository(session)
        self.invitations = InvitationRepository(session)
        self.groups = GroupRepository(session)
        self.mailer = mailer if mailer is not None else get_mailer()
        self.audit = AuditService(session)

    async def create_organization(self, user: User, name: str) -> Organization:
        slug = await self._unique_slug(slugify(name) or "equipo")
        org = Organization(
            name=name.strip(),
            slug=slug,
            plan=PlanTier.FREE,
            is_personal=False,
            credit_balance=0,
            billing_country="CO",
        )
        await self.orgs.add(org)
        await self.memberships.add(
            Membership(user_id=user.id, organization_id=org.id, role=MembershipRole.OWNER)
        )
        await self._record(
            org.id,
            AuditAction.ORGANIZATION_CREATED,
            actor_user_id=user.id,
            actor_role=MembershipRole.OWNER,
            target_type="organization",
            target_id=org.id,
            summary=f"Creó el equipo «{org.name}»",
            payload={"name": org.name},
        )
        await self.session.commit()
        await self.session.refresh(user)
        created = await self.orgs.get(org.id)
        assert created is not None
        return created

    async def snapshot(self, organization_id: UUID, role: MembershipRole) -> TeamSnapshot:
        org = await self._org(organization_id)
        members = await self.memberships.list_with_users(organization_id)
        member_reads = [self._member_read(item) for item in members]
        by_user = {item.user_id: item for item in member_reads}
        invitations = await self.invitations.list_for_org(organization_id)
        groups = [
            self._group_read(group, by_user) for group in await self.groups.list_for_org(organization_id)
        ]
        can_manage = role in MANAGE_ROLES and not org.is_personal
        limits = limits_for(org)
        seat_used = await self._occupied_seats(organization_id)
        return TeamSnapshot(
            organization=OrganizationRead.model_validate(org),
            role=role,
            can_manage=can_manage,
            can_create_content=role in MANAGE_ROLES,
            can_invite=can_manage and limits.can_invite,
            seat_limit=limits.seats,
            seat_used=seat_used,
            members=member_reads,
            invitations=[
                self._invitation_read(item, include_token=can_manage) for item in invitations
            ],
            groups=groups,
        )

    async def invite(
        self,
        organization_id: UUID,
        actor: User,
        actor_role: MembershipRole,
        email: str,
        role: MembershipRole,
    ) -> InviteOutcome:
        org = await self._org(organization_id)
        self._require_team_features(org, actor_role)
        if role not in INVITABLE_ROLES:
            raise DomainError("El rol propietario no se asigna por invitación.")
        if email.lower() == actor.email.lower():
            raise DomainError("No puedes invitarte a ti mismo.")

        existing_user = await self.users.get_by_email(email.lower())
        if existing_user is not None:
            membership = await self.memberships.get(existing_user.id, organization_id)
            if membership is not None:
                raise ConflictError("Ese correo ya es miembro de este workspace.")

        await self._require_available_seat(org, email)

        pending = await self.invitations.get_pending(organization_id, email)
        if pending is not None:
            pending.role = role
            pending.invited_by_user_id = actor.id
            pending.expires_at = utcnow() + timedelta(days=INVITE_DAYS)
            pending.token = secrets.token_urlsafe(32)
            await self._record(
                organization_id,
                AuditAction.MEMBER_INVITED,
                actor_user_id=actor.id,
                actor_role=actor_role,
                target_type="invitation",
                target_id=pending.id,
                summary=f"Invitó a {email.lower()} como {role.value}",
                payload={"email": email.lower(), "role": role.value},
            )
            await self.session.commit()
            refreshed = await self.invitations.get(pending.id, organization_id)
            assert refreshed is not None
            return InviteOutcome(invitation=refreshed, email_sent=self._deliver_invite(org, actor, refreshed))

        invitation = Invitation(
            organization_id=organization_id,
            invited_by_user_id=actor.id,
            email=email.lower(),
            role=role,
            token=secrets.token_urlsafe(32),
            status=InvitationStatus.PENDING,
            expires_at=utcnow() + timedelta(days=INVITE_DAYS),
        )
        await self.invitations.add(invitation)
        await self._record(
            organization_id,
            AuditAction.MEMBER_INVITED,
            actor_user_id=actor.id,
            actor_role=actor_role,
            target_type="invitation",
            target_id=invitation.id,
            summary=f"Invitó a {email.lower()} como {role.value}",
            payload={"email": email.lower(), "role": role.value},
        )
        await self.session.commit()
        created = await self.invitations.get(invitation.id, organization_id)
        assert created is not None
        return InviteOutcome(invitation=created, email_sent=self._deliver_invite(org, actor, created))

    async def resend(
        self,
        organization_id: UUID,
        actor: User,
        actor_role: MembershipRole,
        invitation_id: UUID,
    ) -> InviteOutcome:
        org = await self._org(organization_id)
        self._require_manage(org, actor_role)
        invitation = await self.invitations.get(invitation_id, organization_id)
        if invitation is None:
            raise NotFoundError("Invitación no encontrada")
        if not await self._ensure_pending(invitation):
            raise DomainError("Solo se pueden reenviar invitaciones pendientes.")
        await self._record(
            organization_id,
            AuditAction.MEMBER_INVITE_RESENT,
            actor_user_id=actor.id,
            actor_role=actor_role,
            target_type="invitation",
            target_id=invitation.id,
            summary=f"Reenvió la invitación a {invitation.email}",
            payload={"email": invitation.email, "role": invitation.role.value if hasattr(invitation.role, "value") else str(invitation.role)},
        )
        return InviteOutcome(invitation=invitation, email_sent=self._deliver_invite(org, actor, invitation))

    async def revoke(
        self,
        organization_id: UUID,
        actor_role: MembershipRole,
        invitation_id: UUID,
        actor_id: UUID | None = None,
    ) -> None:
        org = await self._org(organization_id)
        self._require_manage(org, actor_role)
        invitation = await self.invitations.get(invitation_id, organization_id)
        if invitation is None:
            raise NotFoundError("Invitación no encontrada")
        if invitation.status != InvitationStatus.PENDING:
            raise DomainError("Solo se pueden anular invitaciones pendientes.")
        invitation.status = InvitationStatus.REVOKED
        await self._record(
            organization_id,
            AuditAction.MEMBER_INVITE_REVOKED,
            actor_user_id=actor_id,
            actor_role=actor_role,
            target_type="invitation",
            target_id=invitation.id,
            summary=f"Anuló la invitación a {invitation.email}",
            payload={"email": invitation.email},
        )
        await self.session.commit()

    async def remove_member(
        self,
        organization_id: UUID,
        actor_id: UUID,
        actor_role: MembershipRole,
        user_id: UUID,
    ) -> None:
        org = await self._org(organization_id)
        self._require_manage(org, actor_role)
        if user_id == actor_id:
            raise DomainError("No puedes quitarte a ti mismo.")
        membership = await self.memberships.get(user_id, organization_id)
        if membership is None:
            raise NotFoundError("Miembro no encontrado")
        if membership.role == MembershipRole.OWNER:
            raise ForbiddenError("No puedes quitar al propietario.")
        if actor_role != MembershipRole.OWNER and membership.role in MANAGE_ROLES:
            raise ForbiddenError("Solo el propietario puede quitar a un admin.")
        await self.groups.delete_user_from_org(organization_id, user_id)
        person = await self.users.get_by_id(user_id)
        email = person.email if person else str(user_id)
        await self.memberships.delete(membership)
        await self._record(
            organization_id,
            AuditAction.MEMBER_REMOVED,
            actor_user_id=actor_id,
            actor_role=actor_role,
            target_type="member",
            target_id=user_id,
            summary=f"Quitó a {email}",
            payload={"email": email, "role": membership.role.value if hasattr(membership.role, "value") else str(membership.role)},
        )
        await self.session.commit()

    async def preview(self, token: str) -> InvitationPublic:
        invitation = await self._usable_or_public(token)
        return InvitationPublic(
            organization_id=invitation.organization_id,
            organization_name=invitation.organization.name,
            email=invitation.email,
            role=invitation.role,
            status=invitation.status,
            expires_at=invitation.expires_at,
        )

    async def list_for_email(self, email: str) -> list[MyInvitationRead]:
        items = await self.invitations.list_pending_for_email(email)
        usable: list[MyInvitationRead] = []
        for item in items:
            if not await self._ensure_pending(item):
                continue
            usable.append(
                MyInvitationRead(
                    id=item.id,
                    token=item.token,
                    organization_id=item.organization_id,
                    organization_name=item.organization.name,
                    email=item.email,
                    role=item.role,
                    status=item.status,
                    expires_at=item.expires_at,
                )
            )
        return usable

    async def accept(self, token: str, user: User) -> InvitationAcceptRead:
        invitation = await self._usable_or_public(token)
        if invitation.email.lower() != user.email.lower():
            raise ForbiddenError("Esta invitación es para otro correo.")

        existing = await self.memberships.get(user.id, invitation.organization_id)
        if invitation.status == InvitationStatus.ACCEPTED and existing is not None:
            org = await self._org(invitation.organization_id)
            return InvitationAcceptRead(
                organization=OrganizationRead.model_validate(org),
                role=existing.role,
            )

        if not await self._ensure_pending(invitation):
            raise DomainError("La invitación no es válida o caducó.")

        org = await self._org(invitation.organization_id)
        if existing is None:
            await self._require_available_seat(org, invitation.email)
            await self.memberships.add(
                Membership(
                    user_id=user.id,
                    organization_id=invitation.organization_id,
                    role=invitation.role,
                )
            )
        invitation.status = InvitationStatus.ACCEPTED
        invitation.accepted_at = utcnow()
        await self._record(
            invitation.organization_id,
            AuditAction.MEMBER_JOINED,
            actor_user_id=user.id,
            actor_role=invitation.role,
            target_type="member",
            target_id=user.id,
            summary=f"{user.email} se unió al equipo",
            payload={"email": user.email, "role": invitation.role.value if hasattr(invitation.role, "value") else str(invitation.role)},
        )
        await self.session.commit()
        org = await self._org(invitation.organization_id)
        return InvitationAcceptRead(
            organization=OrganizationRead.model_validate(org),
            role=existing.role if existing else invitation.role,
        )

    async def claim_pending(self, user: User, token: str | None = None) -> UUID | None:
        joined_id: UUID | None = None
        if token:
            try:
                result = await self.accept(token, user)
                joined_id = result.organization.id
            except (ForbiddenError, NotFoundError, DomainError):
                pass
        for item in await self.invitations.list_pending_for_email(user.email):
            try:
                result = await self.accept(item.token, user)
                joined_id = result.organization.id
            except DomainError:
                continue
        return joined_id

    async def create_group(
        self, organization_id: UUID, actor_id: UUID, actor_role: MembershipRole, name: str
    ) -> GroupRead:
        org = await self._org(organization_id)
        self._require_team_features(org, actor_role)
        cleaned = name.strip()
        if await self.groups.get_by_name(organization_id, cleaned):
            raise ConflictError("Ya existe un grupo con ese nombre.")
        group = Group(
            organization_id=organization_id,
            name=cleaned,
            created_by_user_id=actor_id,
        )
        await self.groups.add(group)
        await self._record(
            organization_id,
            AuditAction.GROUP_CREATED,
            actor_user_id=actor_id,
            actor_role=actor_role,
            target_type="group",
            target_id=group.id,
            summary=f"Creó el grupo «{cleaned}»",
            payload={"name": cleaned},
        )
        await self.session.commit()
        created = await self.groups.get(group.id, organization_id)
        assert created is not None
        return await self._group_read_fresh(created, organization_id)

    async def rename_group(
        self,
        organization_id: UUID,
        actor_role: MembershipRole,
        group_id: UUID,
        name: str,
        actor_id: UUID | None = None,
    ) -> GroupRead:
        org = await self._org(organization_id)
        self._require_team_features(org, actor_role)
        group = await self.groups.get(group_id, organization_id)
        if group is None:
            raise NotFoundError("Grupo no encontrado")
        cleaned = name.strip()
        existing = await self.groups.get_by_name(organization_id, cleaned)
        if existing is not None and existing.id != group.id:
            raise ConflictError("Ya existe un grupo con ese nombre.")
        group.name = cleaned
        await self._record(
            organization_id,
            AuditAction.GROUP_RENAMED,
            actor_user_id=actor_id,
            actor_role=actor_role,
            target_type="group",
            target_id=group.id,
            summary=f"Renombró el grupo a «{cleaned}»",
            payload={"name": cleaned},
        )
        await self.session.commit()
        refreshed = await self.groups.get(group.id, organization_id)
        assert refreshed is not None
        return await self._group_read_fresh(refreshed, organization_id)

    async def delete_group(
        self, organization_id: UUID, actor_role: MembershipRole, group_id: UUID, actor_id: UUID | None = None
    ) -> None:
        org = await self._org(organization_id)
        self._require_team_features(org, actor_role)
        group = await self.groups.get(group_id, organization_id)
        if group is None:
            raise NotFoundError("Grupo no encontrado")
        name = group.name
        await self.groups.delete(group)
        await self._record(
            organization_id,
            AuditAction.GROUP_DELETED,
            actor_user_id=actor_id,
            actor_role=actor_role,
            target_type="group",
            target_id=group_id,
            summary=f"Eliminó el grupo «{name}»",
            payload={"name": name},
        )
        await self.session.commit()

    async def set_group_members(
        self,
        organization_id: UUID,
        actor_role: MembershipRole,
        group_id: UUID,
        user_ids: list[UUID],
        actor_id: UUID | None = None,
    ) -> GroupRead:
        org = await self._org(organization_id)
        self._require_team_features(org, actor_role)
        group = await self.groups.get(group_id, organization_id)
        if group is None:
            raise NotFoundError("Grupo no encontrado")
        members = await self.memberships.list_with_users(organization_id)
        member_ids = {item.user_id for item in members}
        unique = set(user_ids)
        unknown = unique - member_ids
        if unknown:
            raise DomainError("Hay usuarios que no pertenecen a este workspace.")
        await self.groups.replace_members(group, organization_id, unique)
        await self._record(
            organization_id,
            AuditAction.GROUP_MEMBERS_UPDATED,
            actor_user_id=actor_id,
            actor_role=actor_role,
            target_type="group",
            target_id=group.id,
            summary=f"Actualizó integrantes de «{group.name}»",
            payload={"name": group.name, "member_count": len(unique)},
        )
        await self.session.commit()
        refreshed = await self.groups.get(group.id, organization_id)
        assert refreshed is not None
        return await self._group_read_fresh(refreshed, organization_id)

    async def add_group_members(
        self,
        organization_id: UUID,
        actor_role: MembershipRole,
        group_id: UUID,
        user_ids: list[UUID],
        actor_id: UUID | None = None,
    ) -> GroupRead:
        org = await self._org(organization_id)
        self._require_team_features(org, actor_role)
        group = await self.groups.get(group_id, organization_id)
        if group is None:
            raise NotFoundError("Grupo no encontrado")
        members = await self.memberships.list_with_users(organization_id)
        member_ids = {item.user_id for item in members}
        unique = set(user_ids)
        if not unique:
            raise DomainError("Selecciona al menos un miembro.")
        unknown = unique - member_ids
        if unknown:
            raise DomainError("Hay usuarios que no pertenecen a este workspace.")
        current = {item.user_id for item in group.members}
        for user_id in unique - current:
            await self.groups.add_member(
                GroupMember(organization_id=organization_id, group_id=group.id, user_id=user_id)
            )
        await self._record(
            organization_id,
            AuditAction.GROUP_MEMBERS_UPDATED,
            actor_user_id=actor_id,
            actor_role=actor_role,
            target_type="group",
            target_id=group.id,
            summary=f"Añadió integrantes a «{group.name}»",
            payload={"name": group.name, "added": len(unique - current)},
        )
        await self.session.commit()
        refreshed = await self.groups.get(group.id, organization_id)
        assert refreshed is not None
        return await self._group_read_fresh(refreshed, organization_id)

    async def remove_group_member(
        self,
        organization_id: UUID,
        actor_role: MembershipRole,
        group_id: UUID,
        user_id: UUID,
        actor_id: UUID | None = None,
    ) -> None:
        org = await self._org(organization_id)
        self._require_team_features(org, actor_role)
        member = await self.groups.get_member(group_id, user_id, organization_id)
        if member is None:
            raise NotFoundError("Ese integrante no está en el grupo.")
        group = await self.groups.get(group_id, organization_id)
        await self.groups.delete_member(member)
        await self._record(
            organization_id,
            AuditAction.GROUP_MEMBERS_UPDATED,
            actor_user_id=actor_id,
            actor_role=actor_role,
            target_type="group",
            target_id=group_id,
            summary=f"Quitó un integrante de «{group.name if group else group_id}»",
            payload={"name": group.name if group else None, "removed_user_id": str(user_id)},
        )
        await self.session.commit()

    def invitation_read(
        self,
        invitation: Invitation,
        include_token: bool = False,
        email_sent: bool | None = None,
    ) -> InvitationRead:
        return self._invitation_read(invitation, include_token=include_token, email_sent=email_sent)

    def _member_read(self, item: Membership) -> MemberRead:
        return MemberRead(
            id=item.id,
            user_id=item.user_id,
            email=item.user.email,
            full_name=item.user.full_name,
            role=item.role,
            last_seen_at=item.last_seen_at,
        )

    async def _org(self, organization_id: UUID) -> Organization:
        org = await self.orgs.get(organization_id)
        if org is None:
            raise NotFoundError("Organization not found")
        return org

    def _require_manage(self, org: Organization, role: MembershipRole) -> None:
        if org.is_personal:
            raise DomainError("El workspace personal no admite invitaciones ni grupos. Crea un equipo.")
        if role not in MANAGE_ROLES:
            raise ForbiddenError("Solo el propietario o un admin puede gestionar el equipo.")

    def _require_team_features(self, org: Organization, role: MembershipRole) -> None:
        self._require_manage(org, role)
        if not limits_for(org).can_invite:
            raise DomainError(
                "El plan gratuito no incluye invitaciones ni grupos. Suscríbete al plan Equipo."
            )

    async def _occupied_seats(self, organization_id: UUID, extra_email: str | None = None) -> int:
        members = await self.memberships.list_with_users(organization_id)
        invites = await self.invitations.list_for_org(organization_id)
        skip = extra_email.lower() if extra_email else None
        pending = {
            item.email.lower()
            for item in invites
            if item.status == InvitationStatus.PENDING and item.email.lower() != skip
        }
        return len(members) + len(pending)

    async def _require_available_seat(self, org: Organization, email: str | None = None) -> None:
        limits = limits_for(org)
        if limits.seats is None:
            return
        used = await self._occupied_seats(org.id, extra_email=email)
        if used >= limits.seats:
            raise DomainError(
                f"Este plan admite hasta {limits.seats} miembros. Amplía el plan para invitar a más personas."
            )

    async def _usable_or_public(self, token: str) -> Invitation:
        invitation = await self.invitations.get_by_token(token)
        if invitation is None:
            raise NotFoundError("Invitación no encontrada")
        return invitation

    async def _ensure_pending(self, invitation: Invitation) -> bool:
        if invitation.status != InvitationStatus.PENDING:
            return False
        expires = invitation.expires_at
        if expires.tzinfo is None:
            expires = expires.replace(tzinfo=timezone.utc)
        if expires <= datetime.now(timezone.utc):
            invitation.status = InvitationStatus.EXPIRED
            await self.session.commit()
            return False
        return True

    def _deliver_invite(self, org: Organization, actor: User, invitation: Invitation) -> bool:
        url = invite_accept_url(invitation.token)
        message = build_invite_email(
            to=invitation.email,
            organization_name=org.name,
            inviter_name=actor.full_name,
            role=invitation.role,
            accept_url=url,
            expires_at=invitation.expires_at,
            locale=actor.locale,
        )
        if not self.mailer.configured:
            logger.info("Invite for %s (SMTP not configured): %s", invitation.email, url)
            return False
        try:
            self.mailer.send(message)
            return True
        except MailError:
            logger.exception("Failed to send invite email to %s", invitation.email)
            return False

    def _invitation_read(
        self,
        invitation: Invitation,
        include_token: bool,
        email_sent: bool | None = None,
    ) -> InvitationRead:
        return InvitationRead(
            id=invitation.id,
            organization_id=invitation.organization_id,
            email=invitation.email,
            role=invitation.role,
            status=invitation.status,
            token=invitation.token if include_token else None,
            expires_at=invitation.expires_at,
            created_at=invitation.created_at,
            email_sent=email_sent,
        )

    def _group_read(self, group: Group, members_by_user: dict[UUID, MemberRead]) -> GroupRead:
        members = [
            members_by_user[item.user_id] for item in group.members if item.user_id in members_by_user
        ]
        return GroupRead(
            id=group.id,
            organization_id=group.organization_id,
            name=group.name,
            member_count=len(members),
            members=members,
        )

    async def _group_read_fresh(self, group: Group, organization_id: UUID) -> GroupRead:
        members = await self.memberships.list_with_users(organization_id)
        by_user = {item.user_id: self._member_read(item) for item in members}
        return self._group_read(group, by_user)

    async def _unique_slug(self, base: str) -> str:
        candidate = base
        suffix = 2
        while await self.orgs.slug_exists(candidate):
            candidate = f"{base}-{suffix}"
            suffix += 1
        return candidate

    async def _record(
        self,
        organization_id: UUID,
        action: AuditAction,
        *,
        actor_user_id: UUID | None,
        actor_role: MembershipRole | None,
        target_type: str,
        target_id: UUID | None,
        summary: str,
        payload: dict | None = None,
    ) -> None:
        await self.audit.record(
            organization_id,
            action,
            actor_user_id=actor_user_id,
            actor_role=actor_role,
            target_type=target_type,
            target_id=target_id,
            summary=summary,
            payload=payload,
        )
