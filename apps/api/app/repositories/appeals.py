from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.appeal import (
    AppealActionLog,
    AppealCase,
    AppealEvidence,
    AppealResolution,
    AppealStatus,
)


class AppealRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def add(self, row: AppealCase) -> AppealCase:
        self.session.add(row)
        await self.session.flush()
        return row

    async def get(self, appeal_id: UUID, organization_id: UUID) -> AppealCase | None:
        result = await self.session.execute(
            select(AppealCase).where(
                AppealCase.id == appeal_id,
                AppealCase.organization_id == organization_id,
            )
        )
        return result.scalar_one_or_none()

    async def get_by_attempt_question(
        self,
        organization_id: UUID,
        attempt_id: UUID,
        question_id: UUID,
    ) -> AppealCase | None:
        result = await self.session.execute(
            select(AppealCase).where(
                AppealCase.organization_id == organization_id,
                AppealCase.attempt_id == attempt_id,
                AppealCase.question_id == question_id,
            )
        )
        return result.scalar_one_or_none()

    async def list_for_student(
        self,
        organization_id: UUID,
        student_user_id: UUID,
        *,
        status: AppealStatus | None = None,
    ) -> list[AppealCase]:
        conditions = [
            AppealCase.organization_id == organization_id,
            AppealCase.student_user_id == student_user_id,
        ]
        if status is not None:
            conditions.append(AppealCase.status == status)
        result = await self.session.execute(
            select(AppealCase).where(*conditions).order_by(AppealCase.created_at.desc())
        )
        return list(result.scalars().all())

    async def list_for_org(
        self,
        organization_id: UUID,
        *,
        status: AppealStatus | None = None,
    ) -> list[AppealCase]:
        conditions = [AppealCase.organization_id == organization_id]
        if status is not None:
            conditions.append(AppealCase.status == status)
        result = await self.session.execute(
            select(AppealCase).where(*conditions).order_by(AppealCase.created_at.desc())
        )
        return list(result.scalars().all())

    async def add_evidence(self, row: AppealEvidence) -> AppealEvidence:
        self.session.add(row)
        await self.session.flush()
        return row

    async def list_evidence(self, appeal_id: UUID, organization_id: UUID) -> list[AppealEvidence]:
        result = await self.session.execute(
            select(AppealEvidence)
            .where(
                AppealEvidence.appeal_id == appeal_id,
                AppealEvidence.organization_id == organization_id,
            )
            .order_by(AppealEvidence.created_at.asc())
        )
        return list(result.scalars().all())

    async def add_resolution(self, row: AppealResolution) -> AppealResolution:
        self.session.add(row)
        await self.session.flush()
        return row

    async def get_resolution(self, appeal_id: UUID, organization_id: UUID) -> AppealResolution | None:
        result = await self.session.execute(
            select(AppealResolution).where(
                AppealResolution.appeal_id == appeal_id,
                AppealResolution.organization_id == organization_id,
            )
        )
        return result.scalar_one_or_none()

    async def add_action(self, row: AppealActionLog) -> AppealActionLog:
        self.session.add(row)
        await self.session.flush()
        return row

    async def list_actions(self, appeal_id: UUID, organization_id: UUID) -> list[AppealActionLog]:
        result = await self.session.execute(
            select(AppealActionLog)
            .where(
                AppealActionLog.appeal_id == appeal_id,
                AppealActionLog.organization_id == organization_id,
            )
            .order_by(AppealActionLog.created_at.asc())
        )
        return list(result.scalars().all())
