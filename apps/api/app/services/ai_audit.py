from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.models import MembershipRole, Organization
from app.models.ai_audit import AiDecisionEvent, AiFeature
from app.models.exam import parse_str_enum
from app.models.mixins import utcnow
from app.repositories.ai_audit import AiAuditRepository
from app.repositories.appeals import AppealRepository
from app.repositories.content import DocumentRepository, ExamRepository
from app.repositories.evidence import EvidenceRepository
from app.repositories.identity import OrganizationRepository
from app.schemas.ai_audit import AiAuditPurgeResult, AiDecisionEventList, AiDecisionEventRead
from app.services.appeal_ai import _ai_read
from app.services.errors import DomainError, ForbiddenError, NotFoundError

settings = get_settings()
READ_ROLES = {MembershipRole.OWNER, MembershipRole.ADMIN, MembershipRole.AUDITOR}


class AiAuditService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.repo = AiAuditRepository(session)
        self.orgs = OrganizationRepository(session)
        self.appeals = AppealRepository(session)
        self.exams = ExamRepository(session)
        self.documents = DocumentRepository(session)
        self.evidence = EvidenceRepository(session)

    async def record(
        self,
        *,
        organization_id: UUID,
        feature: AiFeature | str,
        outcome: str,
        actor_user_id: UUID | None = None,
        document_id: UUID | None = None,
        conversation_id: UUID | None = None,
        model: str | None = None,
        prompt_hash: str | None = None,
        chunk_ids: list | None = None,
        confidence: float | None = None,
        relevance: float | None = None,
        payload: dict | None = None,
    ) -> AiDecisionEvent:
        feature_enum = feature if isinstance(feature, AiFeature) else parse_str_enum(AiFeature, feature)
        safe_payload = _trim_payload(payload or {})
        row = AiDecisionEvent(
            organization_id=organization_id,
            actor_user_id=actor_user_id,
            feature=feature_enum,
            document_id=document_id,
            conversation_id=conversation_id,
            model=(model or settings.llm_model)[:120],
            prompt_hash=prompt_hash,
            chunk_ids=[str(item) for item in (chunk_ids or [])],
            confidence=confidence,
            relevance=relevance,
            outcome=(outcome or "")[:64],
            payload=safe_payload,
            created_at=utcnow(),
        )
        return await self.repo.add(row)

    async def list_events(
        self,
        organization_id: UUID,
        role: MembershipRole,
        *,
        feature: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> AiDecisionEventList:
        await self._assert_can_read(organization_id, role)
        feature_enum = AiAuditRepository.parse_feature(feature)
        rows, total = await self.repo.list_for_org(
            organization_id,
            feature=feature_enum,
            limit=limit,
            offset=offset,
        )
        return AiDecisionEventList(
            items=[
                AiDecisionEventRead(
                    id=event.id,
                    organization_id=event.organization_id,
                    actor_user_id=event.actor_user_id,
                    actor_email=email,
                    actor_full_name=full_name,
                    feature=event.feature.value if hasattr(event.feature, "value") else str(event.feature),
                    document_id=event.document_id,
                    conversation_id=event.conversation_id,
                    model=event.model or "",
                    prompt_hash=event.prompt_hash,
                    chunk_ids=list(event.chunk_ids or []),
                    confidence=event.confidence,
                    relevance=event.relevance,
                    outcome=event.outcome or "",
                    payload=event.payload or {},
                    created_at=event.created_at,
                )
                for event, email, full_name in rows
            ],
            total=total,
            limit=limit,
            offset=offset,
        )

    async def purge(
        self,
        organization_id: UUID,
        role: MembershipRole,
        *,
        retention_days: int | None = None,
    ) -> AiAuditPurgeResult:
        if role not in {MembershipRole.OWNER, MembershipRole.ADMIN}:
            raise ForbiddenError("Solo un administrador puede purgar la auditoría IA.")
        await self._assert_can_read(organization_id, role)
        days = retention_days if retention_days is not None else settings.ai_audit_retention_days
        days = max(1, min(int(days), 3650))
        cutoff = datetime.now(timezone.utc) - timedelta(days=days)
        deleted = await self.repo.purge_before(cutoff, organization_id=organization_id)
        await self.session.commit()
        return AiAuditPurgeResult(deleted=deleted, retention_days=days)

    async def export_appeal(
        self,
        organization_id: UUID,
        user_id: UUID,
        role: MembershipRole,
        appeal_id: UUID,
    ) -> dict:
        case = await self.appeals.get(appeal_id, organization_id)
        if case is None:
            raise NotFoundError("Appeal not found")
        if case.student_user_id == user_id:
            pass
        elif role in READ_ROLES:
            await self._assert_can_read(organization_id, role)
        else:
            raise ForbiddenError("No puedes exportar esta apelación.")

        evidence = await self.appeals.list_evidence(case.id, organization_id)
        comments = await self.appeals.list_comments(case.id, organization_id)
        actions = await self.appeals.list_actions(case.id, organization_id)
        resolution = await self.appeals.get_resolution(case.id, organization_id)
        ai_rec = await self.appeals.latest_ai_recommendation(case.id, organization_id)
        ai_events = await self.repo.list_for_appeal(organization_id, case.id)
        return {
            "exported_at": datetime.now(timezone.utc).isoformat(),
            "type": "appeal",
            "appeal": {
                "id": str(case.id),
                "organization_id": str(case.organization_id),
                "exam_id": str(case.exam_id),
                "attempt_id": str(case.attempt_id),
                "question_id": str(case.question_id),
                "student_user_id": str(case.student_user_id),
                "status": case.status.value if hasattr(case.status, "value") else str(case.status),
                "student_argument": case.student_argument,
                "selected_indices": list(case.selected_indices or []),
                "correct_indices": list(case.correct_indices or []),
                "system_evidence_snapshot": dict(case.system_evidence_snapshot or {}),
                "question_prompt": case.question_prompt,
                "exam_title": case.exam_title,
                "created_at": case.created_at.isoformat() if case.created_at else None,
                "updated_at": case.updated_at.isoformat() if case.updated_at else None,
            },
            "evidence": [
                {
                    "id": str(item.id),
                    "source": item.source.value if hasattr(item.source, "value") else str(item.source),
                    "quote": item.quote,
                    "page_start": item.page_start,
                    "page_end": item.page_end,
                    "chapter": item.chapter,
                    "section": item.section,
                    "argument": item.argument,
                    "chunk_id": str(item.chunk_id) if item.chunk_id else None,
                    "created_at": item.created_at.isoformat() if item.created_at else None,
                }
                for item in evidence
            ],
            "comments": [
                {
                    "id": str(item.id),
                    "author_user_id": str(item.author_user_id),
                    "body": item.body,
                    "attachment_keys": list(item.attachment_keys or []),
                    "created_at": item.created_at.isoformat() if item.created_at else None,
                }
                for item in comments
            ],
            "actions": [
                {
                    "id": str(item.id),
                    "actor_user_id": str(item.actor_user_id) if item.actor_user_id else None,
                    "action": item.action,
                    "payload": item.payload or {},
                    "created_at": item.created_at.isoformat() if item.created_at else None,
                }
                for item in actions
            ],
            "resolution": (
                {
                    "id": str(resolution.id),
                    "decision": (
                        resolution.decision.value
                        if hasattr(resolution.decision, "value")
                        else str(resolution.decision)
                    ),
                    "rationale": resolution.rationale,
                    "score_adjustment": resolution.score_adjustment,
                    "ai_recommendation_id": (
                        str(resolution.ai_recommendation_id) if resolution.ai_recommendation_id else None
                    ),
                    "resolved_at": resolution.resolved_at.isoformat() if resolution.resolved_at else None,
                }
                if resolution
                else None
            ),
            "ai_recommendation": _ai_read(ai_rec).model_dump(mode="json") if ai_rec else None,
            "ai_decision_events": [_event_dict(item) for item in ai_events],
        }

    async def export_attempt(
        self,
        organization_id: UUID,
        user_id: UUID,
        role: MembershipRole,
        exam_id: UUID,
        attempt_id: UUID,
    ) -> dict:
        exam = await self.exams.get(exam_id, organization_id)
        if exam is None:
            raise NotFoundError("Exam not found")
        attempt = await self.exams.get_attempt_in_org(attempt_id, organization_id)
        if attempt is None or attempt.exam_id != exam_id:
            raise NotFoundError("Attempt not found")
        if attempt.user_id == user_id:
            pass
        elif role in READ_ROLES:
            await self._assert_can_read(organization_id, role)
        else:
            raise ForbiddenError("No puedes exportar este intento.")

        refs = await self.evidence.list_for_attempt(organization_id, attempt_id)
        document = await self.documents.get_by_id(exam.document_id) if exam.document_id else None
        return {
            "exported_at": datetime.now(timezone.utc).isoformat(),
            "type": "attempt",
            "exam": {
                "id": str(exam.id),
                "title": exam.title,
                "document_id": str(exam.document_id) if exam.document_id else None,
                "document_title": getattr(document, "display_title", None) or getattr(document, "filename", None),
            },
            "attempt": {
                "id": str(attempt.id),
                "user_id": str(attempt.user_id),
                "score": attempt.score,
                "started_at": attempt.started_at.isoformat() if attempt.started_at else None,
                "completed_at": attempt.completed_at.isoformat() if attempt.completed_at else None,
                "answers": attempt.answers or {},
            },
            "questions": [
                {
                    "id": str(question.id),
                    "prompt": question.prompt,
                    "kind": question.kind.value if hasattr(question.kind, "value") else str(question.kind),
                    "options": list(question.options or []),
                    "correct_indices": list(question.correct_indices or [question.correct_index]),
                    "explanation": question.explanation,
                }
                for question in exam.questions
            ],
            "answer_references": [
                {
                    "question_id": str(item.question_id),
                    "quote": item.quote,
                    "page_start": item.page_start,
                    "page_end": item.page_end,
                    "chapter": item.chapter,
                    "section": item.section,
                    "confidence": item.confidence,
                    "document_title": item.document_title,
                }
                for item in refs.values()
            ],
        }

    async def _assert_can_read(self, organization_id: UUID, role: MembershipRole) -> Organization:
        org = await self.orgs.get(organization_id)
        if org is None:
            raise DomainError("Organization not found", status_code=404)
        if org.is_personal:
            raise DomainError("La auditoría IA está en un workspace de empresa.")
        if role not in READ_ROLES:
            raise ForbiddenError("Solo el propietario, un administrador o un auditor puede ver la auditoría IA.")
        return org


def _trim_payload(payload: dict) -> dict:
    raw = json.dumps(payload, default=str)
    max_bytes = max(500, int(settings.ai_decision_payload_max_bytes))
    if len(raw.encode("utf-8")) <= max_bytes:
        return payload
    return {"truncated": True, "preview": raw[: max_bytes // 2]}


def _event_dict(event: AiDecisionEvent) -> dict:
    return {
        "id": str(event.id),
        "feature": event.feature.value if hasattr(event.feature, "value") else str(event.feature),
        "model": event.model,
        "prompt_hash": event.prompt_hash,
        "chunk_ids": list(event.chunk_ids or []),
        "confidence": event.confidence,
        "relevance": event.relevance,
        "outcome": event.outcome,
        "payload": event.payload or {},
        "created_at": event.created_at.isoformat() if event.created_at else None,
    }
