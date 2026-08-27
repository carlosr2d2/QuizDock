from fastapi import APIRouter, Depends, HTTPException, status

from app.api.deps import RequestContext, get_context
from app.schemas.auth import OrganizationRead

router = APIRouter(tags=["organizations"])


@router.get("/organizations/current", response_model=OrganizationRead)
async def current_organization(ctx: RequestContext = Depends(get_context)) -> OrganizationRead:
    membership = next(
        (m for m in ctx.user.memberships if m.organization_id == ctx.organization_id),
        None,
    )
    if membership is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Organization not found")
    return OrganizationRead.model_validate(membership.organization)
