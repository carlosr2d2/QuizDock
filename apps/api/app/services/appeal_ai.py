from __future__ import annotations

import hashlib
import logging
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.jobs import enqueue
from app.models.ai_audit import AiDecisionEvent, AiFeature
from app.models.appeal import (
    AppealActionLog,
    AppealAiRecommendation,
    AppealAiStatus,
    AppealCase,
    AppealDecision,
    AppealStatus,
)
from app.models.identity import MembershipRole
from app.repositories.appeals import AppealRepository
from app.repositories.content import ExamRepository
from app.schemas.appeals import AppealAiRecommendationRead
from app.services.billing import BillingService
from app.services.errors import ConflictError, DomainError, ForbiddenError, NotFoundError
from app.services.llm import get_llm_client

logger = logging.getLogger(__name__)
settings = get_settings()

REVIEWER_ROLES = {MembershipRole.OWNER, MembershipRole.ADMIN}

SYSTEM_PROMPT = """You are an academic appeals assistant for QuizDock.
You compare system evidence (why the key says an answer is correct) with the student's
challenging evidence and argument.

Return ONLY a JSON object with:
- recommendation: one of "accepted", "rejected", "needs_info"
- confidence: number from 0 to 1
- rationale: short justification in the same language as the student argument
- ambiguity: true if the document supports more than one valid reading of the disputed point
- alt_chunk_ids: optional list of chunk id strings that support an alternative reading

Rules:
- Never invent page numbers or quotes that are not in the provided evidence.
- If evidence is thin or contradictory without a clear winner, prefer "needs_info" and set ambiguity true.
- If student evidence clearly supports their answer and system evidence is weak/ambiguous, recommend "accepted".
- If system evidence clearly supports the key and student evidence does not, recommend "rejected".
- This is advisory only; a human will decide.
"""


class AppealAiService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.repo = AppealRepository(session)
        self.exams = ExamRepository(session)
        self.billing = BillingService(session)
        self.llm = get_llm_client()

    async def request_review(
        self,
        organization_id: UUID,
        user_id: UUID,
        role: MembershipRole,
        appeal_id: UUID,
    ) -> AppealAiRecommendationRead:
        if role not in REVIEWER_ROLES:
            raise ForbiddenError("Solo un administrador puede pedir revisión IA.")
        case = await self.repo.get(appeal_id, organization_id)
        if case is None:
            raise NotFoundError("Appeal not found")
        if case.status == AppealStatus.CLOSED:
            raise ConflictError("La apelación está cerrada.")

        latest = await self.repo.latest_ai_recommendation(case.id, organization_id)
        if latest is not None and latest.status in {AppealAiStatus.QUEUED, AppealAiStatus.RUNNING}:
            return _ai_read(latest)

        cost = max(0, int(settings.credit_cost_per_appeal_review))
        if cost:
            await self.billing.debit(
                organization_id,
                user_id,
                cost,
                "appeal_ai_review",
            )

        system_quote = str((case.system_evidence_snapshot or {}).get("quote") or "") or None
        evidence = await self.repo.list_evidence(case.id, organization_id)
        student_quote = next(
            (item.quote for item in evidence if item.quote),
            None,
        )

        row = AppealAiRecommendation(
            organization_id=organization_id,
            appeal_id=case.id,
            requested_by_user_id=user_id,
            status=AppealAiStatus.QUEUED,
            system_quote=system_quote,
            student_quote=student_quote,
            model=settings.llm_model,
            credit_cost=cost,
        )
        await self.repo.add_ai_recommendation(row)
        await self.repo.add_action(
            AppealActionLog(
                organization_id=organization_id,
                appeal_id=case.id,
                actor_user_id=user_id,
                action="ai_review_requested",
                payload={"recommendation_id": str(row.id)},
            )
        )
        await self.session.commit()

        if not enqueue("appeals.ai_review", str(row.id)):
            await self.fulfill(row.id)
            refreshed = await self.repo.get_ai_recommendation(row.id, organization_id)
            if refreshed is None:
                raise NotFoundError("Recommendation not found")
            return _ai_read(refreshed)
        return _ai_read(row)

    async def fulfill(self, recommendation_id: UUID) -> AppealAiRecommendationRead:
        row = await self.repo.get_ai_recommendation(recommendation_id)
        if row is None:
            raise NotFoundError("Recommendation not found")
        if row.status == AppealAiStatus.READY:
            return _ai_read(row)

        case = await self.repo.get(row.appeal_id, row.organization_id)
        if case is None:
            row.status = AppealAiStatus.FAILED
            row.error_message = "Appeal not found"
            await self.session.commit()
            return _ai_read(row)

        row.status = AppealAiStatus.RUNNING
        await self.session.commit()

        try:
            payload = await self._analyze(case, row)
            recommendation = _parse_decision(payload.get("recommendation"))
            confidence = _clamp_confidence(payload.get("confidence"))
            rationale = str(payload.get("rationale") or "").strip()
            ambiguity = bool(payload.get("ambiguity"))
            if not rationale:
                raise DomainError("La IA no devolvió justificación.")
            alt_ids = payload.get("alt_chunk_ids") if isinstance(payload.get("alt_chunk_ids"), list) else []
            row.recommendation = recommendation
            row.confidence = confidence
            row.rationale = rationale
            row.ambiguity = ambiguity or recommendation == AppealDecision.NEEDS_INFO
            row.alt_chunk_ids = [str(item) for item in alt_ids if item]
            row.status = AppealAiStatus.READY
            row.error_message = None
            row.model = settings.llm_model
            await self.repo.add_decision(
                AiDecisionEvent(
                    organization_id=row.organization_id,
                    actor_user_id=row.requested_by_user_id,
                    feature=AiFeature.APPEAL_REVIEW,
                    document_id=None,
                    model=settings.llm_model,
                    prompt_hash=hashlib.sha256(
                        f"{case.id}:{case.student_argument}".encode("utf-8")
                    ).hexdigest(),
                    chunk_ids=row.alt_chunk_ids,
                    confidence=confidence,
                    relevance=confidence,
                    outcome=recommendation.value,
                    payload={
                        "appeal_id": str(case.id),
                        "recommendation_id": str(row.id),
                        "ambiguity": row.ambiguity,
                    },
                )
            )
            await self.repo.add_action(
                AppealActionLog(
                    organization_id=row.organization_id,
                    appeal_id=case.id,
                    actor_user_id=None,
                    action="ai_review_ready",
                    payload={
                        "recommendation_id": str(row.id),
                        "recommendation": recommendation.value,
                        "ambiguity": row.ambiguity,
                    },
                )
            )
        except Exception as exc:
            logger.exception("Appeal AI review failed for %s", recommendation_id)
            row.status = AppealAiStatus.FAILED
            row.error_message = str(exc)[:500]
            await self.repo.add_decision(
                AiDecisionEvent(
                    organization_id=row.organization_id,
                    actor_user_id=row.requested_by_user_id,
                    feature=AiFeature.APPEAL_REVIEW,
                    document_id=None,
                    model=settings.llm_model,
                    prompt_hash=None,
                    chunk_ids=[],
                    confidence=None,
                    relevance=None,
                    outcome="failed",
                    payload={"appeal_id": str(row.appeal_id), "error": row.error_message},
                )
            )
        await self.session.commit()
        return _ai_read(row)

    async def _analyze(self, case: AppealCase, row: AppealAiRecommendation) -> dict:
        evidence = await self.repo.list_evidence(case.id, case.organization_id)
        student_bits = []
        for item in evidence:
            student_bits.append(
                {
                    "quote": item.quote,
                    "page_start": item.page_start,
                    "page_end": item.page_end,
                    "chapter": item.chapter,
                    "section": item.section,
                    "argument": item.argument,
                    "chunk_id": str(item.chunk_id) if item.chunk_id else None,
                }
            )
        user_prompt = (
            f"Exam: {case.exam_title}\n"
            f"Question: {case.question_prompt}\n"
            f"Student selected indices: {case.selected_indices}\n"
            f"System correct indices: {case.correct_indices}\n"
            f"Student argument: {case.student_argument}\n"
            f"System evidence snapshot: {case.system_evidence_snapshot}\n"
            f"Student evidence items: {student_bits}\n"
            f"Stored system quote: {row.system_quote}\n"
            f"Stored student quote: {row.student_quote}\n"
        )
        return await self.llm.complete_json(SYSTEM_PROMPT, user_prompt, temperature=0.2)


def _ai_read(row: AppealAiRecommendation) -> AppealAiRecommendationRead:
    recommendation = None
    if row.recommendation is not None:
        recommendation = (
            row.recommendation.value if hasattr(row.recommendation, "value") else str(row.recommendation)
        )
    status = row.status.value if hasattr(row.status, "value") else str(row.status)
    return AppealAiRecommendationRead(
        id=row.id,
        appeal_id=row.appeal_id,
        requested_by_user_id=row.requested_by_user_id,
        status=status,
        recommendation=recommendation,
        confidence=row.confidence,
        rationale=row.rationale or "",
        ambiguity=bool(row.ambiguity),
        alt_chunk_ids=[str(item) for item in (row.alt_chunk_ids or [])],
        system_quote=row.system_quote,
        student_quote=row.student_quote,
        model=row.model or "",
        error_message=row.error_message,
        credit_cost=int(row.credit_cost or 0),
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


def _parse_decision(value: object) -> AppealDecision:
    raw = str(value or "").strip().lower()
    for item in AppealDecision:
        if item.value == raw:
            return item
    raise DomainError(f"Recomendación IA inválida: {value!r}")


def _clamp_confidence(value: object) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return 0.5
    return max(0.0, min(1.0, number))
