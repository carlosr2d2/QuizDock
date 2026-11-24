from datetime import datetime, timezone
from uuid import uuid4

import pytest

from app.models.chat import ChatRole, DocumentChatMessage, DocumentConversation
from app.models.document import DocumentStatus
from app.schemas.chat import ChatMessageCreate, ChatSessionCreate
from app.services.document_chat import DocumentChatService
from app.services.errors import ConflictError, NotFoundError
from app.services.rag import RetrievedContext
from tests.fakes import FakeDocumentRepo, FakeSession, FakeTxRepo, ensure_id, make_document, make_org


class FakeChatRepo:
    def __init__(self) -> None:
        self.conversations: list[DocumentConversation] = []
        self.messages: list[DocumentChatMessage] = []
        self.decisions: list[object] = []

    async def add_conversation(self, row: DocumentConversation) -> DocumentConversation:
        ensure_id(row)
        self.conversations.append(row)
        return row

    async def get_conversation(self, conversation_id, organization_id, *, user_id=None):
        for row in self.conversations:
            if row.id != conversation_id or row.organization_id != organization_id:
                continue
            if user_id is not None and row.user_id != user_id:
                continue
            return row
        return None

    async def list_conversations(self, organization_id, document_id, user_id):
        return [
            row
            for row in self.conversations
            if row.organization_id == organization_id
            and row.document_id == document_id
            and row.user_id == user_id
        ]

    async def add_message(self, row: DocumentChatMessage) -> DocumentChatMessage:
        ensure_id(row)
        if getattr(row, "created_at", None) is None:
            row.created_at = datetime.now(timezone.utc)
        self.messages.append(row)
        return row

    async def list_messages(self, conversation_id, organization_id):
        return [
            row
            for row in self.messages
            if row.conversation_id == conversation_id and row.organization_id == organization_id
        ]

    async def add_decision(self, row):
        ensure_id(row)
        self.decisions.append(row)
        return row


class FakeBilling:
    def __init__(self) -> None:
        self.debited: list[tuple] = []

    async def debit(self, organization_id, user_id, amount, reason):
        self.debited.append((organization_id, user_id, amount, reason))
        return 999


class FakeRag:
    def __init__(self, contexts: list[RetrievedContext] | None = None) -> None:
        self.contexts = contexts or []

    async def semantic_retrieve(self, *_args, **_kwargs):
        return list(self.contexts)


class FakeLLM:
    def __init__(self, payload: dict | None = None, *, fail: bool = False) -> None:
        self.payload = payload
        self.fail = fail

    async def complete_json(self, system: str, user: str, temperature: float = 0.3) -> dict:
        if self.fail:
            raise RuntimeError("llm down")
        assert self.payload is not None
        return self.payload


def _service(org, document, *, contexts=None, llm_payload=None, llm_fail=False):
    service = DocumentChatService(FakeSession())
    service.documents = FakeDocumentRepo()
    service.documents.by_id[document.id] = document
    service.repo = FakeChatRepo()
    service.billing = FakeBilling()
    service.rag = FakeRag(contexts)
    service.llm = FakeLLM(llm_payload, fail=llm_fail)
    service.billing.txs = FakeTxRepo()
    return service


@pytest.mark.asyncio
async def test_create_session_requires_ready_document():
    org = make_org()
    document = make_document(org.id, uuid4(), status=DocumentStatus.PROCESSING)
    service = _service(org, document)
    with pytest.raises(ConflictError):
        await service.create_session(
            org.id,
            uuid4(),
            document.id,
            ChatSessionCreate(),
        )


@pytest.mark.asyncio
async def test_send_message_answers_with_verified_citation(monkeypatch):
    monkeypatch.setattr("app.services.document_chat.settings.credit_cost_per_chat_message", 1)
    monkeypatch.setattr("app.services.document_chat.settings.llm_model", "test-model")
    monkeypatch.setattr("app.services.document_chat.settings.llm_api_key", "x")
    org = make_org()
    user_id = uuid4()
    document = make_document(org.id, user_id)
    chunk_id = uuid4()
    quote = "TCP garantiza la entrega confiable de datos"
    contexts = [
        RetrievedContext(
            position=0,
            content=f"La capa de transporte usa {quote} entre hosts de la red.",
            chunk_id=chunk_id,
            page_start=11,
            chapter="Capítulo 4",
            relevance=0.9,
        )
    ]
    service = _service(
        org,
        document,
        contexts=contexts,
        llm_payload={
            "answer": "TCP ofrece entrega confiable.",
            "refuse": False,
            "citations": [{"chunk_position": 0, "quote": quote}],
        },
    )
    session = await service.create_session(org.id, user_id, document.id, ChatSessionCreate())
    reply = await service.send_message(
        org.id,
        user_id,
        document.id,
        session.id,
        ChatMessageCreate(content="¿Qué garantiza TCP?"),
    )
    assert reply.refusal is False
    assert reply.citations
    assert reply.citations[0].page_start == 11
    assert service.billing.debited
    assert any(item.role is ChatRole.USER for item in service.repo.messages)
    assert service.repo.decisions


@pytest.mark.asyncio
async def test_send_message_refuses_without_verified_citation(monkeypatch):
    monkeypatch.setattr("app.services.document_chat.settings.credit_cost_per_chat_message", 1)
    monkeypatch.setattr("app.services.document_chat.settings.llm_api_key", "x")
    org = make_org()
    user_id = uuid4()
    document = make_document(org.id, user_id)
    contexts = [
        RetrievedContext(
            position=0,
            content="Texto sobre fotosíntesis y clorofila en plantas verdes.",
            chunk_id=uuid4(),
            page_start=2,
        )
    ]
    service = _service(
        org,
        document,
        contexts=contexts,
        llm_payload={
            "answer": "Inventé una respuesta sin evidencia.",
            "refuse": False,
            "citations": [{"chunk_position": 0, "quote": "esto no está en el fragmento"}],
        },
    )
    session = await service.create_session(org.id, user_id, document.id, ChatSessionCreate())
    reply = await service.send_message(
        org.id,
        user_id,
        document.id,
        session.id,
        ChatMessageCreate(content="Explícame TCP"),
    )
    assert reply.refusal is True
    assert reply.citations == []


@pytest.mark.asyncio
async def test_get_session_not_found():
    org = make_org()
    document = make_document(org.id, uuid4())
    service = _service(org, document)
    with pytest.raises(NotFoundError):
        await service.get_session(org.id, uuid4(), document.id, uuid4())
