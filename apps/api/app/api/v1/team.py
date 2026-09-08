from uuid import UUID

from fastapi import APIRouter, Depends, Query, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import RequestContext, get_context, get_current_user, get_db, require_roles
from app.models import MembershipRole, User
from app.schemas.audit import AuditEventList
from app.schemas.auth import OrganizationRead
from app.schemas.content import MemberProgressRead, TeamAnalyticsRead
from app.schemas.team import (
    GroupCreate,
    GroupMembersUpdate,
    GroupRead,
    InvitationAcceptRead,
    InvitationCreate,
    InvitationPublic,
    InvitationRead,
    MyInvitationRead,
    OrganizationCreate,
    TeamSnapshot,
)
from app.services.audit import AuditService
from app.services.generation import ExamService
from app.services.team import TeamService

MANAGE_ROLES = (MembershipRole.OWNER, MembershipRole.ADMIN)

router = APIRouter(tags=["team"])


@router.post("/organizations", response_model=OrganizationRead, status_code=201)
async def create_organization(
    payload: OrganizationCreate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> OrganizationRead:
    org = await TeamService(db).create_organization(user, payload.name)
    return OrganizationRead.model_validate(org)


@router.get("/organizations/current/team", response_model=TeamSnapshot)
async def current_team(
    ctx: RequestContext = Depends(get_context),
    db: AsyncSession = Depends(get_db),
) -> TeamSnapshot:
    return await TeamService(db).snapshot(ctx.organization_id, ctx.role)


@router.post(
    "/organizations/current/invitations",
    response_model=InvitationRead,
    status_code=201,
)
async def invite_member(
    payload: InvitationCreate,
    ctx: RequestContext = Depends(require_roles(*MANAGE_ROLES)),
    db: AsyncSession = Depends(get_db),
) -> InvitationRead:
    service = TeamService(db)
    outcome = await service.invite(
        ctx.organization_id,
        ctx.user,
        ctx.role,
        payload.email,
        payload.role,
    )
    return service.invitation_read(outcome.invitation, include_token=True, email_sent=outcome.email_sent)


@router.post(
    "/organizations/current/invitations/{invitation_id}/resend",
    response_model=InvitationRead,
)
async def resend_invitation(
    invitation_id: UUID,
    ctx: RequestContext = Depends(require_roles(*MANAGE_ROLES)),
    db: AsyncSession = Depends(get_db),
) -> InvitationRead:
    service = TeamService(db)
    outcome = await service.resend(
        ctx.organization_id, ctx.user, ctx.role, invitation_id
    )
    return service.invitation_read(outcome.invitation, include_token=True, email_sent=outcome.email_sent)


@router.delete(
    "/organizations/current/invitations/{invitation_id}",
    status_code=204,
    response_class=Response,
)
async def revoke_invitation(
    invitation_id: UUID,
    ctx: RequestContext = Depends(require_roles(*MANAGE_ROLES)),
    db: AsyncSession = Depends(get_db),
) -> Response:
    await TeamService(db).revoke(ctx.organization_id, ctx.role, invitation_id, actor_id=ctx.user.id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.delete(
    "/organizations/current/members/{user_id}",
    status_code=204,
    response_class=Response,
)
async def remove_member(
    user_id: UUID,
    ctx: RequestContext = Depends(require_roles(*MANAGE_ROLES)),
    db: AsyncSession = Depends(get_db),
) -> Response:
    await TeamService(db).remove_member(ctx.organization_id, ctx.user.id, ctx.role, user_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get(
    "/organizations/current/members/{user_id}/progress",
    response_model=MemberProgressRead,
)
async def member_progress(
    user_id: UUID,
    ctx: RequestContext = Depends(get_context),
    db: AsyncSession = Depends(get_db),
) -> MemberProgressRead:
    return await ExamService(db).member_progress(
        ctx.organization_id, ctx.user.id, ctx.role, user_id
    )


@router.get("/organizations/current/analytics", response_model=TeamAnalyticsRead)
async def team_analytics(
    ctx: RequestContext = Depends(get_context),
    db: AsyncSession = Depends(get_db),
) -> TeamAnalyticsRead:
    return await ExamService(db).team_analytics(ctx.organization_id, ctx.role)


@router.get("/organizations/current/audit", response_model=AuditEventList)
async def team_audit(
    ctx: RequestContext = Depends(get_context),
    db: AsyncSession = Depends(get_db),
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
) -> AuditEventList:
    return await AuditService(db).list_events(
        ctx.organization_id, ctx.role, limit=limit, offset=offset
    )


@router.post("/organizations/current/groups", response_model=GroupRead, status_code=201)
async def create_group(
    payload: GroupCreate,
    ctx: RequestContext = Depends(require_roles(*MANAGE_ROLES)),
    db: AsyncSession = Depends(get_db),
) -> GroupRead:
    return await TeamService(db).create_group(
        ctx.organization_id, ctx.user.id, ctx.role, payload.name
    )


@router.patch("/organizations/current/groups/{group_id}", response_model=GroupRead)
async def rename_group(
    group_id: UUID,
    payload: GroupCreate,
    ctx: RequestContext = Depends(require_roles(*MANAGE_ROLES)),
    db: AsyncSession = Depends(get_db),
) -> GroupRead:
    return await TeamService(db).rename_group(
        ctx.organization_id, ctx.role, group_id, payload.name, actor_id=ctx.user.id
    )


@router.delete(
    "/organizations/current/groups/{group_id}",
    status_code=204,
    response_class=Response,
)
async def delete_group(
    group_id: UUID,
    ctx: RequestContext = Depends(require_roles(*MANAGE_ROLES)),
    db: AsyncSession = Depends(get_db),
) -> Response:
    await TeamService(db).delete_group(ctx.organization_id, ctx.role, group_id, actor_id=ctx.user.id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.put("/organizations/current/groups/{group_id}/members", response_model=GroupRead)
async def set_group_members(
    group_id: UUID,
    payload: GroupMembersUpdate,
    ctx: RequestContext = Depends(require_roles(*MANAGE_ROLES)),
    db: AsyncSession = Depends(get_db),
) -> GroupRead:
    return await TeamService(db).set_group_members(
        ctx.organization_id, ctx.role, group_id, payload.user_ids, actor_id=ctx.user.id
    )


@router.post("/organizations/current/groups/{group_id}/members", response_model=GroupRead)
async def add_group_members(
    group_id: UUID,
    payload: GroupMembersUpdate,
    ctx: RequestContext = Depends(require_roles(*MANAGE_ROLES)),
    db: AsyncSession = Depends(get_db),
) -> GroupRead:
    return await TeamService(db).add_group_members(
        ctx.organization_id, ctx.role, group_id, payload.user_ids, actor_id=ctx.user.id
    )


@router.delete(
    "/organizations/current/groups/{group_id}/members/{user_id}",
    status_code=204,
    response_class=Response,
)
async def remove_group_member(
    group_id: UUID,
    user_id: UUID,
    ctx: RequestContext = Depends(require_roles(*MANAGE_ROLES)),
    db: AsyncSession = Depends(get_db),
) -> Response:
    await TeamService(db).remove_group_member(
        ctx.organization_id, ctx.role, group_id, user_id, actor_id=ctx.user.id
    )
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/invitations", response_model=list[MyInvitationRead])
async def my_invitations(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[MyInvitationRead]:
    return await TeamService(db).list_for_email(user.email)


@router.get("/invitations/{token}", response_model=InvitationPublic)
async def invitation_preview(
    token: str,
    db: AsyncSession = Depends(get_db),
) -> InvitationPublic:
    return await TeamService(db).preview(token)


@router.post("/invitations/{token}/accept", response_model=InvitationAcceptRead)
async def accept_invitation(
    token: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> InvitationAcceptRead:
    return await TeamService(db).accept(token, user)
