from app.services.chunking import chunk_text
from app.services.exam_quality import normalize_extracted_text


def test_normalize_extracted_joins_hyphen_line_breaks_and_paragraphs():
    raw = "las bases técni-\ncas estaban maduras.\n\nOtra idea completa."
    cleaned = normalize_extracted_text(raw)
    assert "técnicas" in cleaned
    assert "\n\n" in cleaned
    assert "maduras. Otra" not in cleaned


def test_chunk_text_packs_by_sentences_without_mid_sentence_cuts():
    sentences = [
        f"Esta es la oración número {index} con suficiente texto para empaquetar."
        for index in range(1, 40)
    ]
    text = " ".join(sentences)
    chunks = chunk_text(text, size=220, overlap=60, min_chars=40)
    assert len(chunks) >= 2
    for chunk in chunks:
        assert "oración número" in chunk
        # Prefer complete sentences: chunks should end on sentence punctuation.
        assert chunk.rstrip().endswith(".")


def test_chunk_text_keeps_short_paragraphs_together():
    text = "Párrafo uno con idea completa.\n\nPárrafo dos también completo."
    chunks = chunk_text(text, size=1200, overlap=200, min_chars=10)
    assert len(chunks) == 1
    assert "Párrafo uno" in chunks[0]
    assert "Párrafo dos" in chunks[0]
