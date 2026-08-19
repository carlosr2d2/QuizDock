from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import RequestContext, get_context, get_db
from app.schemas.support import ErrorReportAck, ErrorReportCreate
from app.services.support import SupportService

router = APIRouter(prefix="/support", tags=["support"])


@router.post("/error-reports", response_model=ErrorReportAck, status_code=201)
async def create_error_report(
    payload: ErrorReportCreate,
    ctx: RequestContext = Depends(get_context),
    db: AsyncSession = Depends(get_db),
) -> ErrorReportAck:
    await SupportService(db).report_error(ctx, payload)
    return ErrorReportAck()
