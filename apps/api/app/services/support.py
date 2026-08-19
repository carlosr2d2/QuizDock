import logging

from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import RequestContext
from app.models.support import ErrorReport
from app.schemas.support import ErrorReportCreate

logger = logging.getLogger("quizdock.support")


class SupportService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def report_error(self, ctx: RequestContext, payload: ErrorReportCreate) -> ErrorReport:
        report = ErrorReport(
            user_id=ctx.user.id,
            organization_id=ctx.organization_id,
            path=payload.path,
            message=payload.message,
            detail=payload.detail,
            user_agent=payload.user_agent,
            status="open",
        )
        self.session.add(report)
        await self.session.commit()
        await self.session.refresh(report)
        logger.error(
            "Client error report %s path=%s user=%s org=%s message=%s",
            report.id,
            payload.path,
            ctx.user.email,
            ctx.organization_id,
            payload.message,
        )
        return report
