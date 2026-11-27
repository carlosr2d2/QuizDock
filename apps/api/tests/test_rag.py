from types import SimpleNamespace
from uuid import uuid4

import pytest

from app.models.chunk import DocumentChunk
from app.services.embeddings import hashed_embedding
from app.services.rag import RagService, RetrievedContext, _relevance, _stratified_sample


class FakeChunkRepo:
    def __init__(self, rows: list[DocumentChunk] | None = None) -> None:
        self.rows = list(rows or [])
        self.replaced: list[DocumentChunk] = []

    async def count_for_document(self, document_id, organization_id) -> int:
        return len(
            [
                row
                for row in self.rows
                if row.document_id == document_id and row.organization_id == organization_id
            ]
        )

    async def list_for_document(self, document_id, organization_id) -> list[DocumentChunk]:
        return sorted(
            [
                row
                for row in self.rows
                if row.document_id == document_id and row.organization_id == organization_id
            ],
            key=lambda row: row.position,
        )

    async def similar(self, document_id, organization_id, query, limit: int) -> list[DocumentChunk]:
        from app.services.embeddings import cosine

        scored = []
        for row in self.rows:
            if row.document_id != document_id or row.organization_id != organization_id:
                continue
            scored.append((cosine(query, row.embedding), row))
        scored.sort(key=lambda item: item[0], reverse=True)
        return [row for _, row in scored[:limit]]

    async def replace(self, document_id, organization_id, chunks: list[DocumentChunk]) -> None:
        self.rows = [
            row
            for row in self.rows
            if not (row.document_id == document_id and row.organization_id == organization_id)
        ]
        self.rows.extend(chunks)
        self.replaced = list(chunks)


def _chunk(
    document_id,
    organization_id,
    position: int,
    content: str,
    *,
    page_start: int | None = None,
) -> DocumentChunk:
    row = DocumentChunk(
        document_id=document_id,
        organization_id=organization_id,
        position=position,
        content=content,
        embedding=hashed_embedding(content),
        page_start=page_start,
        page_end=page_start,
        chapter=None,
        section=None,
        char_start=None,
        char_end=None,
        embedding_model="hashed-embedding",
        content_hash=None,
    )
    row.id = uuid4()
    return row


@pytest.mark.asyncio
async def test_semantic_retrieve_orders_by_similarity(monkeypatch):
    monkeypatch.setattr("app.services.rag.settings.rag_semantic_enabled", True)
    org_id = uuid4()
    doc_id = uuid4()
    rows = [
        _chunk(doc_id, org_id, 0, "Introducción a la fotosíntesis y clorofila", page_start=1),
        _chunk(doc_id, org_id, 1, "Historia de las matemáticas antiguas", page_start=2),
        _chunk(doc_id, org_id, 2, "Fotosíntesis: fase luminosa y oscura", page_start=3),
    ]
    service = RagService(SimpleNamespace())
    service.chunks = FakeChunkRepo(rows)

    results = await service.semantic_retrieve(doc_id, org_id, "fotosíntesis clorofila", limit=2)

    assert len(results) == 2
    assert all(isinstance(item, RetrievedContext) for item in results)
    assert results[0].position in {0, 2}
    assert results[0].page_start is not None
    assert results[0].relevance is not None


@pytest.mark.asyncio
async def test_hybrid_retrieve_mixes_semantic_and_stratified(monkeypatch):
    monkeypatch.setattr("app.services.rag.settings.rag_semantic_enabled", True)
    monkeypatch.setattr("app.services.rag.settings.rag_semantic_mix_ratio", 0.5)
    monkeypatch.setattr("app.services.rag.settings.rag_candidate_k", 8)
    org_id = uuid4()
    doc_id = uuid4()
    rows = [_chunk(doc_id, org_id, i, f"Tema {i} contenido base " + ("x" * 40)) for i in range(10)]
    service = RagService(SimpleNamespace())
    service.chunks = FakeChunkRepo(rows)

    async def fake_semantic(*_args, **_kwargs):
        return [
            RetrievedContext(position=7, content=rows[7].content, relevance=0.95),
            RetrievedContext(position=3, content=rows[3].content, relevance=0.8),
        ]

    service.semantic_retrieve = fake_semantic  # type: ignore[method-assign]

    results = await service.hybrid_retrieve(
        doc_id,
        org_id,
        4,
        query="TCP ventanas deslizantes",
        seed=42,
    )

    assert len(results) == 4
    positions = [item.position for item in results]
    assert len(set(positions)) == 4
    assert 7 in positions
    assert 3 in positions


@pytest.mark.asyncio
async def test_contexts_for_falls_back_when_semantic_disabled(monkeypatch):
    monkeypatch.setattr("app.services.rag.settings.rag_semantic_enabled", False)
    org_id = uuid4()
    doc_id = uuid4()
    rows = [_chunk(doc_id, org_id, i, f"chunk {i} " + ("x" * 40)) for i in range(6)]
    service = RagService(SimpleNamespace())
    service.chunks = FakeChunkRepo(rows)

    async def _ensure(document):
        return len(rows)

    service.ensure_indexed = _ensure  # type: ignore[method-assign]
    document = SimpleNamespace(
        id=doc_id,
        organization_id=org_id,
        display_title="Guía",
        filename="guia.pdf",
    )
    results = await service.contexts_for(document, 3, seed=7)
    assert len(results) == 3


def test_stratified_sample_respects_count():
    org_id = uuid4()
    doc_id = uuid4()
    rows = [_chunk(doc_id, org_id, i, f"c{i}") for i in range(20)]
    import random

    picked = _stratified_sample(rows, 5, random.Random(1))
    assert len(picked) == 5
    assert len({row.position for row in picked}) == 5


def test_relevance_accepts_numpy_like_embedding():
    class AmbiguousArray(list):
        def __bool__(self) -> bool:
            raise ValueError(
                "The truth value of an array with more than one element is ambiguous. Use a.any() or a.all()"
            )

    query = hashed_embedding("fotosíntesis")
    embedding = AmbiguousArray(hashed_embedding("fotosíntesis clorofila"))
    score = _relevance(query, embedding)
    assert score is not None
    assert 0.0 <= score <= 1.0
    assert _relevance(query, None) is None
    assert _relevance(query, AmbiguousArray()) is None
