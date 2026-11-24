from uuid import uuid4

from app.services.citations import CitationEngine


def test_citation_prefers_anchor_inside_chunk():
    engine = CitationEngine()
    chunk = (
        "La capa de transporte garantiza la entrega confiable mediante TCP. "
        "UDP no garantiza el orden de los paquetes."
    )
    result = engine.cite(
        chunk_content=chunk,
        chunk_id=uuid4(),
        chunk_position=2,
        page_start=12,
        page_end=12,
        chapter="Capítulo 4",
        anchor="entrega confiable mediante TCP",
        explanation="TCP ofrece entrega confiable.",
    )
    assert result is not None
    assert result.verified is True
    assert "TCP" in result.quote
    assert result.page_start == 12
    assert result.chapter == "Capítulo 4"
    assert result.confidence >= 0.9


def test_citation_falls_back_to_chunk_excerpt():
    engine = CitationEngine()
    chunk = "Las direcciones IPv4 tienen 32 bits y se representan en notación decimal puntuada."
    result = engine.cite(
        chunk_content=chunk,
        explanation="algo no relacionado con el texto fuente",
        max_chars=120,
    )
    assert result is not None
    assert result.verified is True
    assert result.quote
    assert result.confidence >= 0.4


def test_citation_rejects_empty_chunk():
    engine = CitationEngine()
    assert engine.cite(chunk_content="   ") is None
