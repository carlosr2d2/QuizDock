from __future__ import annotations

from pathlib import Path
from uuid import UUID, uuid4

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.files import display_name, document_kind, humanize_filename, is_pdf
from app.core.jobs import enqueue
from app.models import Document, DocumentStatus, Flashcard, MembershipRole
from app.models.audit import AuditAction
from app.repositories.content import DocumentRepository, ExamRepository, FlashcardRepository
from app.schemas.content import (
    DocumentCreate,
    FlashcardCreate,
    FlashcardDeckRead,
    FlashcardProgress,
    FlashcardRead,
    flashcard_read,
)
from app.services.audit import AuditService
from app.services.progress import as_utc_date
from app.services.errors import ConflictError, NotFoundError
from app.services.ingestion import extract_document, pdf_metadata_title
from app.services.permissions import require_author
from app.services.preview import infer_display_title, infer_title_heuristic, looks_truncated, render_pdf_cover
from app.services.rag import RagService

settings = get_settings()


class DocumentService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.repo = DocumentRepository(session)
        self.audit = AuditService(session)

    async def list(self, organization_id: UUID) -> list[Document]:
        return await self.repo.list_for_org(organization_id)

    async def create(
        self,
        organization_id: UUID,
        owner_user_id: UUID,
        role: MembershipRole,
        payload: DocumentCreate,
        file_bytes: bytes | None = None,
    ) -> Document:
        require_author(role)
        filename = Path(payload.filename).name or "document.pdf"
        if await self.repo.exists_filename(organization_id, filename):
            raise ConflictError(
                f"Ya existe un documento con el archivo «{filename}» en este workspace."
            )
        storage_dir = Path(settings.storage_dir)
        storage_dir.mkdir(parents=True, exist_ok=True)
        storage_key = f"{organization_id}/{uuid4()}-{filename}"
        dest = storage_dir / storage_key
        dest.parent.mkdir(parents=True, exist_ok=True)
        if file_bytes is not None:
            dest.write_bytes(file_bytes)

        document = Document(
            organization_id=organization_id,
            owner_user_id=owner_user_id,
            filename=filename,
            content_type=payload.content_type,
            storage_key=storage_key,
            status=DocumentStatus.UPLOADED,
            language=payload.language,
            display_title=humanize_filename(filename),
        )
        await self.repo.add(document)
        await self.session.flush()
        self._attach_upload_preview(document, dest)
        title = display_name(document.display_title, document.filename)
        await self.audit.record(
            organization_id,
            AuditAction.DOCUMENT_UPLOADED,
            actor_user_id=owner_user_id,
            actor_role=role,
            target_type="document",
            target_id=document.id,
            summary=f"Subió «{title}»",
            payload={"filename": filename, "title": title},
        )
        await self.session.commit()
        await self.session.refresh(document)
        enqueue("documents.process", str(document.id))
        return document

    def _attach_upload_preview(self, document: Document, source: Path) -> None:
        """Cover + title from the file itself, before the worker runs."""
        if not source.is_file():
            return
        if is_pdf(document.content_type, document.filename):
            cover_key = f"{document.organization_id}/{document.id}-cover.jpg"
            dest = Path(settings.storage_dir) / cover_key
            try:
                if render_pdf_cover(source, dest):
                    document.cover_key = cover_key
            except Exception:
                pass
            document.display_title = infer_title_heuristic(
                "",
                document.filename,
                pdf_metadata_title(source),
            )
            return
        try:
            preview = source.read_text(encoding="utf-8", errors="ignore")[:4000]
        except Exception:
            preview = ""
        document.display_title = infer_title_heuristic(preview, document.filename, None)

    async def get(self, document_id: UUID, organization_id: UUID) -> Document:
        document = await self.repo.get(document_id, organization_id)
        if document is None:
            raise NotFoundError("Document not found")
        return document

    async def delete(
        self,
        document_id: UUID,
        organization_id: UUID,
        role: MembershipRole,
        actor_id: UUID | None = None,
    ) -> None:
        require_author(role)
        document = await self.get(document_id, organization_id)
        title = display_name(document.display_title, document.filename)
        self._unlink_stored(document.storage_key)
        self._unlink_stored(document.cover_key)
        await self.repo.delete(document)
        await self.audit.record(
            organization_id,
            AuditAction.DOCUMENT_DELETED,
            actor_user_id=actor_id,
            actor_role=role,
            target_type="document",
            target_id=document_id,
            summary=f"Eliminó «{title}»",
            payload={"filename": document.filename, "title": title},
        )
        await self.session.commit()

    def _unlink_stored(self, key: str | None) -> None:
        if not key:
            return
        root = Path(settings.storage_dir).resolve()
        path = (root / key).resolve()
        if not path.is_relative_to(root):
            return
        try:
            if path.is_file():
                path.unlink()
        except OSError:
            pass

    async def process(self, document_id: UUID) -> None:
        document = await self.repo.get_by_id(document_id)
        if document is None:
            return
        if document.status == DocumentStatus.READY and document.extracted_text:
            try:
                await self.ensure_preview(document)
            except Exception:
                pass
            await RagService(self.session).ensure_indexed(document)
            return

        document.status = DocumentStatus.PROCESSING
        document.error_message = None
        await self.session.commit()
        try:
            path = Path(settings.storage_dir) / document.storage_key
            extracted = extract_document(path, document.content_type)
            if not extracted.text:
                raise ValueError("No se pudo extraer texto del documento")
            document.extracted_text = extracted.text
            document.page_count = extracted.page_count
            try:
                await self.ensure_preview(document, metadata_title=extracted.metadata_title)
            except Exception:
                if not document.display_title:
                    document.display_title = humanize_filename(document.filename)
            await self.session.commit()
            await RagService(self.session).index_document(document, pages=extracted.pages)
            document.status = DocumentStatus.READY
            document.error_message = None
        except Exception as exc:
            document.status = DocumentStatus.FAILED
            document.error_message = str(exc)
        await self.session.commit()

    async def ensure_preview(
        self,
        document: Document,
        metadata_title: str | None = None,
    ) -> Document:
        changed = False
        source = Path(settings.storage_dir) / document.storage_key
        if not document.display_title or looks_truncated(document.display_title):
            previous_title = document.display_title
            meta = metadata_title
            if meta is None and source.is_file() and is_pdf(document.content_type, document.filename):
                meta = pdf_metadata_title(source)
            document.display_title = await infer_display_title(
                filename=document.filename,
                text=document.extracted_text or "",
                metadata_title=meta,
            )
            await ExamRepository(self.session).retitle_from_filename(
                document.id,
                document.filename,
                document.display_title,
                previous_title=previous_title,
            )
            changed = True
        if not document.cover_key and source.is_file() and is_pdf(document.content_type, document.filename):
            cover_key = f"{document.organization_id}/{document.id}-cover.jpg"
            dest = Path(settings.storage_dir) / cover_key
            try:
                if render_pdf_cover(source, dest):
                    document.cover_key = cover_key
                    changed = True
            except Exception:
                pass
        if changed:
            await self.session.commit()
            await self.session.refresh(document)
        return document

    def cover_path(self, document: Document) -> Path | None:
        if not document.cover_key:
            return None
        root = Path(settings.storage_dir).resolve()
        path = (root / document.cover_key).resolve()
        if not path.is_relative_to(root) or not path.is_file():
            return None
        return path


class FlashcardService:
    def __init__(self, session: AsyncSession) -> None:
        self.repo = FlashcardRepository(session)
        self.documents = DocumentRepository(session)
        self.session = session

    async def list(
        self,
        organization_id: UUID,
        owner_user_id: UUID,
        due_only: bool = False,
        document_id: UUID | None = None,
    ) -> list[FlashcardRead]:
        cards = await self.repo.list_for_org(
            organization_id,
            owner_user_id,
            due_only=due_only,
            document_id=document_id,
        )
        documents = await self.documents.get_many(
            {card.document_id for card in cards if card.document_id},
            organization_id,
        )
        return [
            flashcard_read(card, documents.get(card.document_id) if card.document_id else None)
            for card in cards
        ]

    async def list_decks(self, organization_id: UUID, owner_user_id: UUID) -> list[FlashcardDeckRead]:
        rows = await self.repo.deck_stats(organization_id, owner_user_id)
        documents = await self.documents.get_many(
            {document_id for document_id, *_ in rows if document_id},
            organization_id,
        )
        decks: list[FlashcardDeckRead] = []
        for document_id, card_count, due_count, last_reviewed_at in rows:
            document = documents.get(document_id) if document_id else None
            decks.append(
                FlashcardDeckRead(
                    document_id=document_id,
                    document_title=(
                        display_name(document.display_title, document.filename)
                        if document
                        else "Sin documento"
                    ),
                    document_kind=(
                        document_kind(document.content_type, document.filename) if document else None
                    ),
                    has_cover=bool(document.cover_key) if document else False,
                    card_count=card_count,
                    due_count=due_count,
                    last_reviewed_at=last_reviewed_at,
                )
            )
        return decks

    async def progress(self, organization_id: UUID, owner_user_id: UUID) -> FlashcardProgress:
        total, due, reviewed, last_at, mastered = await self.repo.progress_aggregates(
            organization_id, owner_user_id
        )
        review_times = await self.repo.review_times(organization_id, owner_user_id)
        return FlashcardProgress(
            flashcard_count=total,
            flashcard_due=due,
            flashcard_reviewed=reviewed,
            flashcard_mastered=mastered,
            flashcard_last_reviewed_at=last_at,
            study_dates=[as_utc_date(value) for value in review_times],
        )

    async def create(
        self,
        organization_id: UUID,
        owner_user_id: UUID,
        role: MembershipRole,
        payload: FlashcardCreate,
    ) -> Flashcard:
        require_author(role)
        card = Flashcard(
            organization_id=organization_id,
            owner_user_id=owner_user_id,
            document_id=payload.document_id,
            front=payload.front,
            back=payload.back,
        )
        await self.repo.add(card)
        await self.session.commit()
        await self.session.refresh(card)
        return card

    async def review(
        self,
        card_id: UUID,
        organization_id: UUID,
        owner_user_id: UUID,
        quality: int,
    ) -> Flashcard:
        from datetime import datetime, timedelta, timezone

        card = await self.repo.get(card_id, organization_id, owner_user_id)
        if card is None:
            raise NotFoundError("Flashcard not found")

        now = datetime.now(timezone.utc)
        card.last_reviewed_at = now
        if quality < 3:
            card.repetitions = 0
            card.interval_days = 1
            card.next_review_at = now
        else:
            if card.repetitions == 0:
                card.interval_days = 1
            elif card.repetitions == 1:
                card.interval_days = 6
            else:
                card.interval_days = max(1, round(card.interval_days * card.ease_factor))
            card.repetitions += 1
            card.next_review_at = now + timedelta(days=card.interval_days)

        card.ease_factor = max(1.3, card.ease_factor + (0.1 - (5 - quality) * (0.08 + (5 - quality) * 0.02)))
        await self.session.commit()
        await self.session.refresh(card)
        return card
