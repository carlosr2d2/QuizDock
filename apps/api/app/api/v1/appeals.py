from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import RequestContext, get_context, get_db, require_roles
from app.models import MembershipRole
from app.schemas.appeals import (
    AppealCreate,
    AppealDetail,
    AppealEvidenceCreate,
    AppealRead,
    AppealResolveRequest,
    AppealStatusUpdate,
)
from app.services.appeals import AppealService

router = APIRouter(prefix="/appeals", tags=["appeals"])
WRITE_ROLES = (MembershipRole.OWNER, MembershipRole.ADMIN, MembershipRole.MEMBER)
REVIEW_ROLES = (MembershipRole.OWNER, MembershipRole.ADMIN)


@router.get("", response_model=list[AppealRead])
async def list_appeals(
    status: str | None = Query(default=None),
    inbox: bool = Query(default=False),
    ctx: RequestContext = Depends(get_context),
    db: AsyncSession = Depends(get_db),
) -> list[AppealRead]:
    return await AppealService(db).list(
        ctx.organization_id,
        ctx.user.id,
        ctx.role,
        status=status,
        inbox=inbox,
    )


@router.post("", response_model=AppealDetail, status_code=201)
async def create_appeal(
    payload: AppealCreate,
    ctx: RequestContext = Depends(require_roles(*WRITE_ROLES)),
    db: AsyncSession = Depends(get_db),
) -> AppealDetail:
    return await AppealService(db).create(ctx.organization_id, ctx.user.id, ctx.role, payload)


@router.get("/{appeal_id}", response_model=AppealDetail)
async def get_appeal(
    appeal_id: UUID,
    ctx: RequestContext = Depends(get_context),
    db: AsyncSession = Depends(get_db),
) -> AppealDetail:
    return await AppealService(db).get_detail(ctx.organization_id, ctx.user.id, ctx.role, appeal_id)


@router.post("/{appeal_id}/evidence", response_model=AppealDetail)
async def add_appeal_evidence(
    appeal_id: UUID,
    payload: AppealEvidenceCreate,
    ctx: RequestContext = Depends(require_roles(*WRITE_ROLES)),
    db: AsyncSession = Depends(get_db),
) -> AppealDetail:
    return await AppealService(db).add_evidence(
        ctx.organization_id, ctx.user.id, ctx.role, appeal_id, payload
    )


@router.patch("/{appeal_id}/status", response_model=AppealDetail)
async def update_appeal_status(
    appeal_id: UUID,
    payload: AppealStatusUpdate,
    ctx: RequestContext = Depends(require_roles(*REVIEW_ROLES)),
    db: AsyncSession = Depends(get_db),
) -> AppealDetail:
    return await AppealService(db).update_status(
        ctx.organization_id, ctx.user.id, ctx.role, appeal_id, payload
    )


@router.post("/{appeal_id}/resolve", response_model=AppealDetail)
async def resolve_appeal(
    appeal_id: UUID,
    payload: AppealResolveRequest,
    ctx: RequestContext = Depends(require_roles(*REVIEW_ROLES)),
    db: AsyncSession = Depends(get_db),
) -> AppealDetail:
    return await AppealService(db).resolve(
        ctx.organization_id, ctx.user.id, ctx.role, appeal_id, payload
    )
