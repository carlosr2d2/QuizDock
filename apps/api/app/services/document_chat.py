from __future__ import annotations

import hashlib
import logging
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.files import display_name
from app.models.ai_audit import AiDecisionEvent, AiFeature
from app.models.chat import ChatRole, DocumentChatMessage, DocumentConversation
from app.models.document import DocumentStatus
from app.repositories.chat import ChatRepository
from app.repositories.content import DocumentRepository
from app.schemas.chat import (
    ChatCitationRead,
    ChatMessageCreate,
    ChatMessageRead,
    ChatSessionCreate,
    ChatSessionDetail,
    ChatSessionRead,
)
from app.services.billing import BillingService
from app.services.citations import CitationEngine
from app.services.errors import ConflictError, DomainError, ForbiddenError, NotFoundError
from app.services.llm import OpenAICompatibleClient
from app.services.rag import RagService, RetrievedContext

logger = logging.getLogger(__name__)
settings = get_settings()

_REFUSAL_ES = (
    "No encontré evidencia suficiente en el documento para responder con certeza. "
    "Prueba reformular la pregunta o pedir un tema que aparezca en el texto."
)
_REFUSAL_EN = (
    "I could not find enough evidence in the document to answer confidently. "
    "Try rephrasing or ask about a topic that appears in the text."
)


class DocumentChatService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.documents = DocumentRepository(session)
        self.repo = ChatRepository(session)
        self.rag = RagService(session)
        self.billing = BillingService(session)
        self.citations = CitationEngine()
        self.llm = OpenAICompatibleClient()

    async def create_session(
        self,
        organization_id: UUID,
        user_id: UUID,
        document_id: UUID,
        payload: ChatSessionCreate,
    ) -> ChatSessionRead:
        document = await self._ready_document(document_id, organization_id)
        title = (payload.title or "").strip() or display_name(document.display_title, document.filename)
        row = DocumentConversation(
            organization_id=organization_id,
            document_id=document.id,
            user_id=user_id,
            exam_id=payload.exam_id,
            title=title[:240],
        )
        await self.repo.add_conversation(row)
        await self.session.commit()
        await self.session.refresh(row)
        return ChatSessionRead.model_validate(row)

    async def list_sessions(
        self,
        organization_id: UUID,
        user_id: UUID,
        document_id: UUID,
    ) -> list[ChatSessionRead]:
        await self._ready_document(document_id, organization_id)
        rows = await self.repo.list_conversations(organization_id, document_id, user_id)
        return [ChatSessionRead.model_validate(row) for row in rows]

    async def get_session(
        self,
        organization_id: UUID,
        user_id: UUID,
        document_id: UUID,
        conversation_id: UUID,
        *,
        allow_org_read: bool = False,
    ) -> ChatSessionDetail:
        await self._ready_document(document_id, organization_id)
        conversation = await self.repo.get_conversation(
            conversation_id,
            organization_id,
            user_id=None if allow_org_read else user_id,
        )
        if conversation is None or conversation.document_id != document_id:
            raise NotFoundError("Conversation not found")
        if not allow_org_read and conversation.user_id != user_id:
            raise ForbiddenError("No puedes ver esta conversación.")
        messages = await self.repo.list_messages(conversation.id, organization_id)
        return ChatSessionDetail(
            **ChatSessionRead.model_validate(conversation).model_dump(),
            messages=[_message_read(item) for item in messages],
        )

    async def send_message(
        self,
        organization_id: UUID,
        user_id: UUID,
        document_id: UUID,
        conversation_id: UUID,
        payload: ChatMessageCreate,
    ) -> ChatMessageRead:
        document = await self._ready_document(document_id, organization_id)
        conversation = await self.repo.get_conversation(
            conversation_id,
            organization_id,
            user_id=user_id,
        )
        if conversation is None or conversation.document_id != document_id:
            raise NotFoundError("Conversation not found")

        content = payload.content.strip()
        if not content:
            raise DomainError("El mensaje no puede estar vacío.", 400)

        await self.billing.debit(
            organization_id,
            user_id,
            settings.credit_cost_per_chat_message,
            "document_chat",
        )

        user_message = DocumentChatMessage(
            organization_id=organization_id,
            conversation_id=conversation.id,
            role=ChatRole.USER,
            content=content,
            citations=[],
            refusal=False,
        )
        await self.repo.add_message(user_message)

        contexts = await self.rag.semantic_retrieve(
            document.id,
            organization_id,
            content,
            limit=max(4, min(settings.rag_candidate_k, 8)),
        )
        language = (document.language or "es").lower()
        if language.startswith("en"):
            refusal_text = _REFUSAL_EN
        else:
            refusal_text = _REFUSAL_ES

        assistant = await self._grounded_reply(
            organization_id=organization_id,
            user_id=user_id,
            document_id=document.id,
            conversation_id=conversation.id,
            question=content,
            contexts=contexts,
            refusal_text=refusal_text,
            language=language,
        )
        conversation.title = conversation.title or content[:80]
        await self.session.commit()
        await self.session.refresh(assistant)
        return _message_read(assistant)

    async def _grounded_reply(
        self,
        *,
        organization_id: UUID,
        user_id: UUID,
        document_id: UUID,
        conversation_id: UUID,
        question: str,
        contexts: list[RetrievedContext],
        refusal_text: str,
        language: str,
    ) -> DocumentChatMessage:
        if not contexts:
            return await self._store_refusal(
                organization_id,
                conversation_id,
                refusal_text,
                user_id=user_id,
                document_id=document_id,
                outcome="no_context",
            )

        try:
            raw = await self.llm.complete_json(
                _system_prompt(language),
                _user_prompt(question, contexts, language),
                temperature=0.2,
            )
        except Exception:
            logger.exception("document chat LLM failed")
            return await self._store_refusal(
                organization_id,
                conversation_id,
                refusal_text,
                user_id=user_id,
                document_id=document_id,
                outcome="llm_error",
            )

        answer = str(raw.get("answer") or "").strip()
        refuse = bool(raw.get("refuse"))
        raw_citations = raw.get("citations") if isinstance(raw.get("citations"), list) else []

        verified = self._verify_citations(raw_citations, contexts)
        if refuse or not answer or not verified:
            return await self._store_refusal(
                organization_id,
                conversation_id,
                refusal_text,
                user_id=user_id,
                document_id=document_id,
                outcome="refused" if refuse or not verified else "empty_answer",
                contexts=contexts,
            )

        confidence = sum(item.confidence or 0.0 for item in verified) / len(verified)
        relevance = sum(item.confidence or 0.0 for item in verified) / len(verified)
        message = DocumentChatMessage(
            organization_id=organization_id,
            conversation_id=conversation_id,
            role=ChatRole.ASSISTANT,
            content=answer,
            citations=[item.model_dump(mode="json") for item in verified],
            refusal=False,
            model=settings.llm_model,
        )
        await self.repo.add_message(message)
        await self.repo.add_decision(
            AiDecisionEvent(
                organization_id=organization_id,
                actor_user_id=user_id,
                feature=AiFeature.CHAT,
                document_id=document_id,
                conversation_id=conversation_id,
                model=settings.llm_model,
                prompt_hash=hashlib.sha256(question.encode("utf-8")).hexdigest(),
                chunk_ids=[str(item.chunk_id) for item in verified if item.chunk_id],
                confidence=confidence,
                relevance=relevance,
                outcome="answered",
                payload={"citation_count": len(verified)},
            )
        )
        return message

    def _verify_citations(
        self,
        raw_citations: list,
        contexts: list[RetrievedContext],
    ) -> list[ChatCitationRead]:
        by_position = {item.position: item for item in contexts}
        verified: list[ChatCitationRead] = []
        for item in raw_citations:
            if not isinstance(item, dict):
                continue
            position = item.get("chunk_position")
            quote = str(item.get("quote") or "").strip()
            if not isinstance(position, int) or position not in by_position or len(quote) < 12:
                continue
            context = by_position[position]
            # Strict: the model quote must appear in the chunk (no excerpt fallback).
            citation = self.citations.cite(
                chunk_content=context.content,
                chunk_id=context.chunk_id,
                chunk_position=context.position,
                page_start=context.page_start,
                page_end=context.page_end,
                chapter=context.chapter,
                section=context.section,
                anchor=quote,
            )
            # Anchor hits score >= 0.9; excerpt fallback is 0.4 and must not count as a citation.
            if citation is None or not citation.verified or citation.confidence < 0.9:
                continue
            verified.append(
                ChatCitationRead(
                    chunk_id=citation.chunk_id,
                    quote=citation.quote,
                    page_start=citation.page_start,
                    page_end=citation.page_end,
                    chapter=citation.chapter,
                    section=citation.section,
                    confidence=citation.confidence,
                )
            )
        return verified

    async def _store_refusal(
        self,
        organization_id: UUID,
        conversation_id: UUID,
        text: str,
        *,
        user_id: UUID,
        document_id: UUID,
        outcome: str,
        contexts: list[RetrievedContext] | None = None,
    ) -> DocumentChatMessage:
        message = DocumentChatMessage(
            organization_id=organization_id,
            conversation_id=conversation_id,
            role=ChatRole.ASSISTANT,
            content=text,
            citations=[],
            refusal=True,
            model=settings.llm_model if settings.llm_api_key.strip() else None,
        )
        await self.repo.add_message(message)
        await self.repo.add_decision(
            AiDecisionEvent(
                organization_id=organization_id,
                actor_user_id=user_id,
                feature=AiFeature.CHAT,
                document_id=document_id,
                conversation_id=conversation_id,
                model=settings.llm_model if settings.llm_api_key.strip() else "none",
                prompt_hash=None,
                chunk_ids=[str(item.chunk_id) for item in (contexts or []) if item.chunk_id],
                confidence=None,
                relevance=None,
                outcome=outcome,
                payload={},
            )
        )
        return message

    async def _ready_document(self, document_id: UUID, organization_id: UUID):
        document = await self.documents.get(document_id, organization_id)
        if document is None:
            raise NotFoundError("Document not found")
        if document.status != DocumentStatus.READY or not document.extracted_text:
            raise ConflictError("El documento aún no está listo para chatear.")
        return document


def _message_read(row: DocumentChatMessage) -> ChatMessageRead:
    citations: list[ChatCitationRead] = []
    for item in row.citations or []:
        if isinstance(item, dict):
            citations.append(ChatCitationRead.model_validate(item))
    return ChatMessageRead(
        id=row.id,
        conversation_id=row.conversation_id,
        role=row.role.value if hasattr(row.role, "value") else str(row.role),
        content=row.content,
        citations=citations,
        refusal=bool(row.refusal),
        model=row.model,
        created_at=row.created_at,
    )


def _system_prompt(language: str) -> str:
    if language.startswith("en"):
        return (
            "You answer ONLY using the provided document fragments. "
            "Return JSON with keys: answer (string), refuse (boolean), "
            "citations (array of {chunk_position:int, quote:string}). "
            "Every non-refusal answer MUST include at least one citation quote "
            "copied from a fragment. If evidence is insufficient, set refuse=true "
            "and answer to a short refusal. Never invent pages or facts."
        )
    return (
        "Respondes SOLO con los fragmentos del documento. "
        "Devuelve JSON con: answer (string), refuse (boolean), "
        "citations (array de {chunk_position:int, quote:string}). "
        "Toda respuesta no-rechazo DEBE incluir al menos una cita literal "
        "tomada de un fragmento. Si no hay evidencia, refuse=true y un rechazo breve. "
        "No inventes páginas ni hechos."
    )


def _user_prompt(question: str, contexts: list[RetrievedContext], language: str) -> str:
    blocks = []
    for item in contexts:
        meta = f"chunk_position={item.position}"
        if item.page_start is not None:
            meta += f" page={item.page_start}"
            if item.page_end and item.page_end != item.page_start:
                meta += f"-{item.page_end}"
        if item.chapter:
            meta += f" chapter={item.chapter}"
        blocks.append(f"[{meta}]\n{item.content}")
    header = "Question:" if language.startswith("en") else "Pregunta:"
    frags = "Fragments:" if language.startswith("en") else "Fragmentos:"
    return f"{header}\n{question}\n\n{frags}\n\n" + "\n\n".join(blocks)
