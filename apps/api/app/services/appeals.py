from __future__ import annotations

import logging
import re
from pathlib import Path
from uuid import UUID, uuid4

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.models.appeal import (
    AppealActionLog,
    AppealCase,
    AppealComment,
    AppealDecision,
    AppealEvidence,
    AppealEvidenceSource,
    AppealResolution,
    AppealStatus,
)
from app.models.exam import parse_str_enum
from app.models.identity import MembershipRole
from app.repositories.appeals import AppealRepository
from app.repositories.chunks import ChunkRepository
from app.repositories.content import DocumentRepository, ExamRepository
from app.repositories.evidence import EvidenceRepository
from app.repositories.identity import MembershipRepository, OrganizationRepository, UserRepository
from app.schemas.appeals import (
    AppealActionRead,
    AppealAttachmentRead,
    AppealCommentCreate,
    AppealCommentRead,
    AppealCreate,
    AppealDetail,
    AppealEvidenceCreate,
    AppealEvidenceRead,
    AppealRead,
    AppealResolutionRead,
    AppealResolveRequest,
    AppealStatusUpdate,
    DocumentChunkRead,
)
from app.services.appeal_state import assert_transition, is_open
from app.services.errors import ConflictError, DomainError, ForbiddenError, NotFoundError
from app.services.generation import answer_indices, question_correct_indices
from app.services.mail import OutboundEmail, get_mailer

logger = logging.getLogger(__name__)
settings = get_settings()

REVIEWER_ROLES = {MembershipRole.OWNER, MembershipRole.ADMIN}
ALLOWED_ATTACHMENT_TYPES = {
    "application/pdf",
    "image/png",
    "image/jpeg",
    "text/plain",
}
MAX_ATTACHMENT_BYTES = 5 * 1024 * 1024
SAFE_FILENAME = re.compile(r"[^A-Za-z0-9._-]+")


class AppealService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.repo = AppealRepository(session)
        self.exams = ExamRepository(session)
        self.documents = DocumentRepository(session)
        self.evidence_repo = EvidenceRepository(session)
        self.chunks = ChunkRepository(session)
        self.memberships = MembershipRepository(session)
        self.users = UserRepository(session)
        self.orgs = OrganizationRepository(session)
        self.mailer = get_mailer(settings)

    async def create(
        self,
        organization_id: UUID,
        user_id: UUID,
        role: MembershipRole,
        payload: AppealCreate,
    ) -> AppealDetail:
        if role == MembershipRole.AUDITOR:
            raise ForbiddenError("Los auditores no pueden crear apelaciones.")

        attempt = await self.exams.get_attempt_in_org(
            payload.attempt_id,
            organization_id,
            user_id=user_id,
        )
        if attempt is None or attempt.completed_at is None:
            raise NotFoundError("Attempt not found")

        exam = await self.exams.get(attempt.exam_id, organization_id)
        if exam is None:
            raise NotFoundError("Exam not found")
        question = next((item for item in exam.questions if item.id == payload.question_id), None)
        if question is None:
            raise NotFoundError("Question not found")

        selected = answer_indices((attempt.answers or {}).get(str(question.id)))
        expected = question_correct_indices(question)
        if selected == expected:
            raise DomainError("Solo puedes apelar una respuesta marcada como incorrecta.", 400)

        existing = await self.repo.get_by_attempt_question(
            organization_id, attempt.id, question.id
        )
        if existing is not None:
            raise ConflictError("Ya existe una apelación para esta pregunta.")

        evidence_map = await self.evidence_repo.list_for_questions(organization_id, [question.id])
        system_evidence = evidence_map.get(question.id)
        snapshot: dict = {}
        if system_evidence is not None:
            snapshot = {
                "quote": system_evidence.quote,
                "page_start": system_evidence.page_start,
                "page_end": system_evidence.page_end,
                "chapter": system_evidence.chapter,
                "section": system_evidence.section,
                "confidence": system_evidence.confidence,
                "document_id": str(system_evidence.document_id),
            }

        case = AppealCase(
            organization_id=organization_id,
            attempt_id=attempt.id,
            question_id=question.id,
            exam_id=exam.id,
            student_user_id=user_id,
            status=AppealStatus.PENDING,
            student_argument=payload.argument.strip(),
            selected_indices=selected,
            correct_indices=expected,
            system_evidence_snapshot=snapshot,
            question_prompt=question.prompt,
            exam_title=exam.title,
        )
        await self.repo.add(case)
        await self._log(case, user_id, "created", {"argument": case.student_argument[:240]})

        if payload.evidence_quote or payload.evidence_chunk_id:
            await self._attach_evidence(
                case,
                user_id,
                AppealEvidenceCreate(
                    quote=payload.evidence_quote or "",
                    chunk_id=payload.evidence_chunk_id,
                    argument=payload.evidence_argument,
                ),
                source=AppealEvidenceSource.STUDENT,
            )

        await self.session.commit()
        await self._notify_reviewers(case, organization_id)
        return await self.get_detail(organization_id, user_id, role, case.id)

    async def list(
        self,
        organization_id: UUID,
        user_id: UUID,
        role: MembershipRole,
        *,
        status: str | None = None,
        inbox: bool = False,
    ) -> list[AppealRead]:
        status_enum = parse_str_enum(AppealStatus, status) if status else None
        if inbox:
            if role not in REVIEWER_ROLES and role != MembershipRole.AUDITOR:
                raise ForbiddenError("No puedes ver la bandeja de apelaciones.")
            rows = await self.repo.list_for_org(organization_id, status=status_enum)
        else:
            rows = await self.repo.list_for_student(organization_id, user_id, status=status_enum)
        people = await self.exams.users_by_ids({row.student_user_id for row in rows})
        return [_read(row, people.get(row.student_user_id)) for row in rows]

    async def get_detail(
        self,
        organization_id: UUID,
        user_id: UUID,
        role: MembershipRole,
        appeal_id: UUID,
    ) -> AppealDetail:
        case = await self.repo.get(appeal_id, organization_id)
        if case is None:
            raise NotFoundError("Appeal not found")
        self._assert_can_view(case, user_id, role)
        evidence = await self.repo.list_evidence(case.id, organization_id)
        comments = await self.repo.list_comments(case.id, organization_id)
        resolution = await self.repo.get_resolution(case.id, organization_id)
        actions = await self.repo.list_actions(case.id, organization_id)
        student = await self.users.get_by_id(case.student_user_id)
        authors = await self.exams.users_by_ids({row.author_user_id for row in comments})
        return AppealDetail(
            **_read(case, student).model_dump(),
            evidence=[AppealEvidenceRead.model_validate(item) for item in evidence],
            comments=[_comment_read(item, authors.get(item.author_user_id)) for item in comments],
            resolution=AppealResolutionRead.model_validate(resolution) if resolution else None,
            actions=[AppealActionRead.model_validate(item) for item in actions],
        )

    async def add_comment(
        self,
        organization_id: UUID,
        user_id: UUID,
        role: MembershipRole,
        appeal_id: UUID,
        payload: AppealCommentCreate,
    ) -> AppealDetail:
        if role == MembershipRole.AUDITOR:
            raise ForbiddenError("Los auditores no pueden comentar.")
        case = await self.repo.get(appeal_id, organization_id)
        if case is None:
            raise NotFoundError("Appeal not found")
        self._assert_can_view(case, user_id, role)
        if case.student_user_id != user_id and role not in REVIEWER_ROLES:
            raise ForbiddenError("No puedes comentar en esta apelación.")
        if case.status == AppealStatus.CLOSED:
            raise ConflictError("La apelación está cerrada.")

        body = payload.body.strip()
        if len(body) < 1:
            raise DomainError("El comentario no puede estar vacío.", 400)

        keys = list(payload.attachment_keys or [])
        if len(keys) > 3:
            raise DomainError("Máximo 3 adjuntos por comentario.", 400)
        for key in keys:
            self._assert_owned_attachment(organization_id, appeal_id, key)

        row = AppealComment(
            organization_id=organization_id,
            appeal_id=case.id,
            author_user_id=user_id,
            body=body,
            attachment_keys=keys,
        )
        await self.repo.add_comment(row)
        await self._log(
            case,
            user_id,
            "commented",
            {"preview": body[:240], "attachments": len(keys)},
        )
        if case.status == AppealStatus.PENDING and role in REVIEWER_ROLES:
            assert_transition(case.status, AppealStatus.IN_REVIEW)
            case.status = AppealStatus.IN_REVIEW
            await self._log(case, user_id, "status_changed", {"status": case.status.value})
        if case.status == AppealStatus.NEEDS_INFO and case.student_user_id == user_id:
            assert_transition(case.status, AppealStatus.IN_REVIEW)
            case.status = AppealStatus.IN_REVIEW
            await self._log(case, user_id, "status_changed", {"status": case.status.value})

        await self.session.commit()
        await self._notify_comment(case, organization_id, user_id, body)
        return await self.get_detail(organization_id, user_id, role, case.id)

    async def store_attachment(
        self,
        organization_id: UUID,
        user_id: UUID,
        role: MembershipRole,
        appeal_id: UUID,
        *,
        filename: str,
        content_type: str,
        data: bytes,
    ) -> AppealAttachmentRead:
        if role == MembershipRole.AUDITOR:
            raise ForbiddenError("Los auditores no pueden adjuntar archivos.")
        case = await self.repo.get(appeal_id, organization_id)
        if case is None:
            raise NotFoundError("Appeal not found")
        self._assert_can_view(case, user_id, role)
        if case.student_user_id != user_id and role not in REVIEWER_ROLES:
            raise ForbiddenError("No puedes adjuntar archivos a esta apelación.")
        if case.status == AppealStatus.CLOSED:
            raise ConflictError("La apelación está cerrada.")
        if content_type not in ALLOWED_ATTACHMENT_TYPES:
            raise DomainError("Tipo de archivo no permitido. Usa PDF, PNG, JPG o TXT.", 400)
        if len(data) == 0:
            raise DomainError("El archivo está vacío.", 400)
        if len(data) > MAX_ATTACHMENT_BYTES:
            raise DomainError("El archivo supera el máximo de 5 MB.", 400)

        safe_name = SAFE_FILENAME.sub("_", Path(filename).name)[:120] or "attachment"
        storage_key = f"{organization_id}/appeals/{appeal_id}/{uuid4()}-{safe_name}"
        dest = Path(settings.storage_dir) / storage_key
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(data)
        return AppealAttachmentRead(
            storage_key=storage_key,
            filename=safe_name,
            content_type=content_type,
            size=len(data),
        )

    async def add_evidence(
        self,
        organization_id: UUID,
        user_id: UUID,
        role: MembershipRole,
        appeal_id: UUID,
        payload: AppealEvidenceCreate,
    ) -> AppealDetail:
        case = await self.repo.get(appeal_id, organization_id)
        if case is None:
            raise NotFoundError("Appeal not found")
        if case.student_user_id != user_id and role not in REVIEWER_ROLES:
            raise ForbiddenError("No puedes aportar evidencia a esta apelación.")
        if not is_open(case.status):
            raise ConflictError("La apelación ya está cerrada.")
        source = (
            AppealEvidenceSource.TEACHER
            if role in REVIEWER_ROLES and case.student_user_id != user_id
            else AppealEvidenceSource.STUDENT
        )
        await self._attach_evidence(case, user_id, payload, source=source)
        if case.status == AppealStatus.NEEDS_INFO and case.student_user_id == user_id:
            assert_transition(case.status, AppealStatus.IN_REVIEW)
            case.status = AppealStatus.IN_REVIEW
            await self._log(case, user_id, "status_changed", {"status": case.status.value})
        await self.session.commit()
        return await self.get_detail(organization_id, user_id, role, case.id)

    async def update_status(
        self,
        organization_id: UUID,
        user_id: UUID,
        role: MembershipRole,
        appeal_id: UUID,
        payload: AppealStatusUpdate,
    ) -> AppealDetail:
        if role not in REVIEWER_ROLES:
            raise ForbiddenError("Solo un administrador puede cambiar el estado.")
        case = await self.repo.get(appeal_id, organization_id)
        if case is None:
            raise NotFoundError("Appeal not found")
        target = parse_str_enum(AppealStatus, payload.status)
        if target in {AppealStatus.ACCEPTED, AppealStatus.REJECTED, AppealStatus.NEEDS_INFO}:
            raise DomainError("Usa el endpoint de resolución para aceptar, rechazar o pedir información.", 400)
        assert_transition(case.status, target)
        case.status = target
        await self._log(case, user_id, "status_changed", {"status": target.value})
        await self.session.commit()
        return await self.get_detail(organization_id, user_id, role, case.id)

    async def resolve(
        self,
        organization_id: UUID,
        user_id: UUID,
        role: MembershipRole,
        appeal_id: UUID,
        payload: AppealResolveRequest,
    ) -> AppealDetail:
        if role not in REVIEWER_ROLES:
            raise ForbiddenError("Solo un administrador puede resolver apelaciones.")
        case = await self.repo.get(appeal_id, organization_id)
        if case is None:
            raise NotFoundError("Appeal not found")
        decision = parse_str_enum(AppealDecision, payload.decision)
        status_map = {
            AppealDecision.ACCEPTED: AppealStatus.ACCEPTED,
            AppealDecision.REJECTED: AppealStatus.REJECTED,
            AppealDecision.NEEDS_INFO: AppealStatus.NEEDS_INFO,
        }
        target = status_map[decision]
        assert_transition(case.status, target)
        existing = await self.repo.get_resolution(case.id, organization_id)
        if existing is not None and decision != AppealDecision.NEEDS_INFO:
            raise ConflictError("La apelación ya tiene una resolución.")
        case.status = target
        if decision != AppealDecision.NEEDS_INFO:
            await self.repo.add_resolution(
                AppealResolution(
                    organization_id=organization_id,
                    appeal_id=case.id,
                    resolver_user_id=user_id,
                    decision=decision,
                    rationale=payload.rationale.strip(),
                )
            )
        await self._log(
            case,
            user_id,
            "resolved",
            {"decision": decision.value, "rationale": payload.rationale.strip()[:240]},
        )
        await self.session.commit()
        return await self.get_detail(organization_id, user_id, role, case.id)

    async def list_document_chunks(
        self,
        organization_id: UUID,
        document_id: UUID,
        *,
        limit: int = 40,
    ) -> list[DocumentChunkRead]:
        document = await self.documents.get(document_id, organization_id)
        if document is None:
            raise NotFoundError("Document not found")
        rows = await self.chunks.list_for_document(document_id, organization_id)
        return [
            DocumentChunkRead(
                id=row.id,
                position=row.position,
                content=row.content[:500],
                page_start=row.page_start,
                page_end=row.page_end,
                chapter=row.chapter,
                section=row.section,
            )
            for row in rows[: max(1, min(limit, 100))]
        ]

    async def _attach_evidence(
        self,
        case: AppealCase,
        user_id: UUID,
        payload: AppealEvidenceCreate,
        *,
        source: AppealEvidenceSource,
    ) -> AppealEvidence:
        quote = (payload.quote or "").strip()
        chunk = None
        if payload.chunk_id is not None:
            exam = await self.exams.get(case.exam_id, case.organization_id)
            document_id = exam.document_id if exam else None
            if document_id is None:
                raise DomainError("El examen no tiene documento asociado.", 400)
            rows = await self.chunks.list_for_document(document_id, case.organization_id)
            chunk = next((item for item in rows if item.id == payload.chunk_id), None)
            if chunk is None:
                raise NotFoundError("Chunk not found")
            if not quote:
                quote = chunk.content[:500]
        if len(quote) < 8:
            raise DomainError("La evidencia debe incluir un fragmento de al menos 8 caracteres.", 400)

        row = AppealEvidence(
            organization_id=case.organization_id,
            appeal_id=case.id,
            submitted_by_user_id=user_id,
            chunk_id=chunk.id if chunk else payload.chunk_id,
            quote=quote,
            page_start=payload.page_start if payload.page_start is not None else (chunk.page_start if chunk else None),
            page_end=payload.page_end if payload.page_end is not None else (chunk.page_end if chunk else None),
            chapter=payload.chapter or (chunk.chapter if chunk else None),
            section=payload.section or (chunk.section if chunk else None),
            argument=(payload.argument or "").strip() or None,
            source=source,
        )
        await self.repo.add_evidence(row)
        await self._log(case, user_id, "evidence_added", {"source": source.value})
        return row

    def _assert_can_view(self, case: AppealCase, user_id: UUID, role: MembershipRole) -> None:
        if case.student_user_id == user_id:
            return
        if role in REVIEWER_ROLES or role == MembershipRole.AUDITOR:
            return
        raise ForbiddenError("No puedes ver esta apelación.")

    async def _log(
        self,
        case: AppealCase,
        actor_user_id: UUID | None,
        action: str,
        payload: dict | None = None,
    ) -> None:
        await self.repo.add_action(
            AppealActionLog(
                organization_id=case.organization_id,
                appeal_id=case.id,
                actor_user_id=actor_user_id,
                action=action,
                payload=payload or {},
            )
        )

    def _assert_owned_attachment(self, organization_id: UUID, appeal_id: UUID, storage_key: str) -> None:
        prefix = f"{organization_id}/appeals/{appeal_id}/"
        if not storage_key.startswith(prefix) or ".." in storage_key:
            raise DomainError("Adjunto inválido para esta apelación.", 400)
        path = Path(settings.storage_dir) / storage_key
        if not path.is_file():
            raise NotFoundError("Adjunto no encontrado")

    async def _notify_reviewers(self, case: AppealCase, organization_id: UUID) -> None:
        try:
            org = await self.orgs.get(organization_id)
            org_name = org.name if org else "QuizDock"
            url = f"{settings.app_public_url.rstrip('/')}/team/appeals/{case.id}"
            await self._send_to_reviewers(
                organization_id,
                exclude_user_id=case.student_user_id,
                subject=f"Nueva apelación en {org_name}",
                text=(
                    f"Hay una nueva apelación sobre «{case.exam_title}».\n\n"
                    f"Pregunta: {case.question_prompt[:200]}\n"
                    f"Argumento: {case.student_argument[:300]}\n\n"
                    f"Revisar: {url}\n"
                ),
                html=(
                    f"<p>Hay una nueva apelación sobre <strong>{_escape(case.exam_title)}</strong>.</p>"
                    f"<p>{_escape(case.question_prompt[:200])}</p>"
                    f"<p><a href=\"{url}\">Revisar apelación</a></p>"
                ),
            )
        except Exception:
            logger.exception("Failed to notify appeal reviewers")

    async def _notify_comment(
        self,
        case: AppealCase,
        organization_id: UUID,
        author_user_id: UUID,
        body: str,
    ) -> None:
        try:
            org = await self.orgs.get(organization_id)
            org_name = org.name if org else "QuizDock"
            preview = body[:300]
            if author_user_id == case.student_user_id:
                url = f"{settings.app_public_url.rstrip('/')}/team/appeals/{case.id}"
                await self._send_to_reviewers(
                    organization_id,
                    exclude_user_id=author_user_id,
                    subject=f"Nuevo comentario en apelación · {org_name}",
                    text=(
                        f"Hay un nuevo comentario sobre «{case.exam_title}».\n\n"
                        f"{preview}\n\n"
                        f"Abrir: {url}\n"
                    ),
                    html=(
                        f"<p>Nuevo comentario en <strong>{_escape(case.exam_title)}</strong>.</p>"
                        f"<p>{_escape(preview)}</p>"
                        f"<p><a href=\"{url}\">Abrir hilo</a></p>"
                    ),
                )
            else:
                student = await self.users.get_by_id(case.student_user_id)
                if student is None:
                    return
                url = f"{settings.app_public_url.rstrip('/')}/appeals/{case.id}"
                message = OutboundEmail(
                    to=student.email,
                    subject=f"Respuesta en tu apelación · {org_name}",
                    text=(
                        f"Hay un nuevo comentario sobre «{case.exam_title}».\n\n"
                        f"{preview}\n\n"
                        f"Abrir: {url}\n"
                    ),
                    html=(
                        f"<p>Nuevo comentario en tu apelación "
                        f"<strong>{_escape(case.exam_title)}</strong>.</p>"
                        f"<p>{_escape(preview)}</p>"
                        f"<p><a href=\"{url}\">Abrir hilo</a></p>"
                    ),
                )
                try:
                    self.mailer.send(message)
                except Exception:
                    logger.exception("Failed to notify student %s", student.email)
        except Exception:
            logger.exception("Failed to notify appeal comment recipients")

    async def _send_to_reviewers(
        self,
        organization_id: UUID,
        *,
        exclude_user_id: UUID | None,
        subject: str,
        text: str,
        html: str,
    ) -> None:
        memberships = await self.memberships.list_with_users(organization_id)
        for membership in memberships:
            if membership.role not in REVIEWER_ROLES:
                continue
            user = membership.user
            if user is None or (exclude_user_id is not None and user.id == exclude_user_id):
                continue
            message = OutboundEmail(to=user.email, subject=subject, text=text, html=html)
            try:
                self.mailer.send(message)
            except Exception:
                logger.exception("Failed to notify reviewer %s", user.email)


def _comment_read(row: AppealComment, author) -> AppealCommentRead:
    return AppealCommentRead(
        id=row.id,
        appeal_id=row.appeal_id,
        author_user_id=row.author_user_id,
        body=row.body,
        attachment_keys=list(row.attachment_keys or []),
        created_at=row.created_at,
        author_name=author.full_name if author else "",
        author_email=author.email if author else "",
    )


def _read(case: AppealCase, student) -> AppealRead:
    return AppealRead(
        id=case.id,
        organization_id=case.organization_id,
        attempt_id=case.attempt_id,
        question_id=case.question_id,
        exam_id=case.exam_id,
        student_user_id=case.student_user_id,
        status=case.status.value if hasattr(case.status, "value") else str(case.status),
        student_argument=case.student_argument,
        selected_indices=list(case.selected_indices or []),
        correct_indices=list(case.correct_indices or []),
        system_evidence_snapshot=dict(case.system_evidence_snapshot or {}),
        question_prompt=case.question_prompt,
        exam_title=case.exam_title,
        created_at=case.created_at,
        updated_at=case.updated_at,
        student_name=student.full_name if student else "",
        student_email=student.email if student else "",
    )


def _escape(value: str) -> str:
    return (
        value.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )
