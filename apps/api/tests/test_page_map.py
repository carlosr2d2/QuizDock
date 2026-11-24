from app.services.page_map import (
    build_page_spans,
    content_hash,
    infer_chapter,
    infer_section,
    meta_for_chunk,
    pages_for_range,
)


def test_build_page_spans_tracks_offsets():
    text, spans = build_page_spans(["Alpha page", "", "Beta page"])
    assert text == "Alpha page\n\nBeta page"
    assert len(spans) == 2
    assert spans[0].page == 1
    assert spans[0].char_start == 0
    assert spans[0].char_end == len("Alpha page")
    assert spans[1].page == 3
    assert spans[1].char_start == len("Alpha page") + 2


def test_pages_for_range_across_pages():
    _, spans = build_page_spans(["one two", "three four"])
    start, end = pages_for_range(spans, 0, len(spans[0].text) + 5)
    assert start == 1
    assert end == 2


def test_infer_chapter_and_section():
    assert infer_chapter("Capítulo 2: Redes\nContenido") == "Capítulo 2: Redes"
    assert infer_section("Sección 4.1 Introducción\nMás texto") == "Sección 4.1 Introducción"
    assert infer_chapter("sin encabezado útil") is None


def test_meta_for_chunk_assigns_page_and_hash():
    text, spans = build_page_spans(
        [
            "Capítulo 1 Fundamentos\nLa capa de red define el enrutamiento.",
            "Sección 2.1 Direcciones\nLas direcciones IP identifican hosts.",
        ]
    )
    chunk = "Capítulo 1 Fundamentos\nLa capa de red define el enrutamiento."
    meta = meta_for_chunk(chunk, full_text=text, spans=spans)
    assert meta.page_start == 1
    assert meta.page_end == 1
    assert meta.chapter == "Capítulo 1 Fundamentos"
    assert meta.content_hash == content_hash(chunk)
    assert meta.char_start == 0
