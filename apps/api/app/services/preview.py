from __future__ import annotations

import logging
import re
from pathlib import Path

import httpx

from app.core.config import get_settings
from app.core.files import humanize_filename
from app.core.llm_provider import GEMINI_API_ROOT, gemini_headers, gemini_model, is_gemini

logger = logging.getLogger(__name__)
settings = get_settings()

_NOISE = re.compile(
    r"(?i)^(tabla de contenido|table of contents|índice|indice|contenido|"
    r"isbn|www\.|http|página|pagina|page\s+\d+|copyright|©|"
    r"universidad|university|facultad|departamento)$"
)
_QUOTES = re.compile(r'^[\s"“”\'«»]+|[\s"“”\'«»]+$')


def infer_title_heuristic(text: str, filename: str, metadata_title: str | None) -> str:
    if _usable_title(metadata_title, filename):
        return _clean_title(metadata_title or "")
    from_text = _title_from_text(text)
    if from_text:
        return from_text
    return humanize_filename(filename)


async def infer_display_title(filename: str, text: str, metadata_title: str | None) -> str:
    heuristic = infer_title_heuristic(text, filename, metadata_title)
    polished = await _llm_title(text, heuristic)
    return _prefer_title(polished, heuristic, filename)


def looks_truncated(title: str | None) -> bool:
    cleaned = (title or "").strip()
    if len(cleaned) < 8:
        return True
    return len(cleaned) < 16 and " " not in cleaned


def render_pdf_cover(source: Path, dest: Path) -> bool:
    try:
        import pypdfium2 as pdfium
    except ImportError:
        logger.warning("pypdfium2 is not installed; skipping cover render")
        return False

    try:
        pdf = pdfium.PdfDocument(str(source))
    except Exception:
        logger.exception("Could not open PDF for cover render")
        return False

    try:
        if len(pdf) < 1:
            return False
        bitmap = pdf[0].render(scale=1.8)
        image = bitmap.to_pil().convert("RGB")
        if _is_blank(image):
            return False
        image.thumbnail((480, 640))
        dest.parent.mkdir(parents=True, exist_ok=True)
        image.save(dest, "JPEG", quality=84, optimize=True)
        return dest.is_file()
    except Exception:
        logger.exception("PDF cover render failed")
        return False
    finally:
        pdf.close()


def _prefer_title(llm: str | None, heuristic: str, filename: str) -> str:
    if not llm or not _usable_title(llm, filename):
        return heuristic
    lowered = llm.casefold()
    heuristic_l = heuristic.casefold()
    if looks_truncated(llm):
        return heuristic
    if heuristic_l.startswith(lowered) and len(llm) < max(16, int(len(heuristic) * 0.6)):
        return heuristic
    return llm


def _usable_title(title: str | None, filename: str) -> bool:
    cleaned = _clean_title(title or "")
    if len(cleaned) < 6:
        return False
    lowered = cleaned.casefold()
    if lowered in {"untitled", "document", "documento", "sin título", "sin titulo"}:
        return False
    stem = Path(filename).stem.casefold()
    if cleaned.casefold() == stem:
        return False
    return True


def _clean_title(value: str) -> str:
    text = _QUOTES.sub("", " ".join(value.split()))
    return text[:240].strip()


def _title_from_text(text: str) -> str | None:
    picked: list[str] = []
    for raw in text.splitlines()[:40]:
        line = " ".join(raw.split()).strip(" .-•")
        if not line or len(line) < 8 or len(line) > 90:
            continue
        if _NOISE.match(line) or line.isdigit():
            continue
        if re.fullmatch(r"[\d./-]+", line):
            continue
        picked.append(line)
        if len(picked) >= 2 or len(" ".join(picked)) >= 24:
            break
    title = _clean_title(" ".join(picked[:2]))
    return title if len(title) >= 8 else None


def _is_blank(image: object) -> bool:
    from statistics import mean, pstdev

    sample = image.convert("L").resize((32, 32))
    pixels = list(sample.getdata())
    if not pixels:
        return True
    return mean(pixels) > 245 and pstdev(pixels) < 8


async def _llm_title(text: str, heuristic: str) -> str | None:
    if not settings.llm_api_key.strip() or not text.strip():
        return None
    prompt = (
        "Devuelve únicamente el título del libro o documento, en una línea. "
        "Sin comillas, sin autor, sin año, sin editorial y sin explicación. "
        "Si el título candidato ya es correcto, cópialo fielmente.\n\n"
        f"Título candidato: {heuristic}\n\n"
        f"Inicio del documento:\n{text[:2500]}"
    )
    try:
        if is_gemini():
            raw = await _gemini_text(prompt)
        else:
            raw = await _openai_text(prompt)
    except Exception:
        logger.exception("LLM title inference failed")
        return None
    return _clean_title(raw.splitlines()[0]) if raw else None


async def _gemini_text(prompt: str) -> str:
    url = f"{GEMINI_API_ROOT}/models/{gemini_model(settings.llm_model)}:generateContent"
    payload = {
        "contents": [{"role": "user", "parts": [{"text": prompt}]}],
        "generationConfig": {
            "temperature": 0.1,
            "maxOutputTokens": 256,
            "thinkingConfig": {"thinkingBudget": 0},
        },
    }
    async with httpx.AsyncClient(timeout=20.0) as client:
        response = await client.post(url, headers=gemini_headers(), json=payload)
        response.raise_for_status()
        data = response.json()
    parts = data.get("candidates", [{}])[0].get("content", {}).get("parts", [])
    return "".join(part.get("text", "") for part in parts if isinstance(part, dict))


async def _openai_text(prompt: str) -> str:
    headers = {"Content-Type": "application/json"}
    if settings.llm_api_key:
        headers["Authorization"] = f"Bearer {settings.llm_api_key}"
    payload = {
        "model": settings.llm_model,
        "temperature": 0.1,
        "max_tokens": 256,
        "messages": [
            {"role": "system", "content": "Responde solo con el título del documento."},
            {"role": "user", "content": prompt},
        ],
    }
    url = settings.llm_base_url.rstrip("/") + "/chat/completions"
    async with httpx.AsyncClient(timeout=20.0) as client:
        response = await client.post(url, headers=headers, json=payload)
        response.raise_for_status()
        data = response.json()
    return data.get("choices", [{}])[0].get("message", {}).get("content") or ""
