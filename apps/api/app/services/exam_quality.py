"""Quality gates so exam items stay grammatical and grounded in the source."""

from __future__ import annotations

import re
import unicodedata

from typing import Any

# PDF syllable breaks: "gene- rativas", soft hyphen U+00AD.
_HYPHEN_BREAK = re.compile(r"(?<=\w)-\s+(?=\w)")
_SOFT_HYPHEN = re.compile("\u00ad")
_HYPHEN_LINE_BREAK = re.compile(r"(?<=\w)\s*-\s*\n\s*(?=\w)")
# Spaced stump + short continuation: "técni - cas" (avoid "IA - definición").
_SPACED_SYLLABLE = re.compile(
    r"([A-Za-zÁÉÍÓÚÜÑáéíóúüñ]{4,})\s+-\s+([a-záéíóúüñ]{1,5})\b"
)
_DASH_KEEP = frozenset(
    {
        "de",
        "del",
        "la",
        "el",
        "en",
        "y",
        "o",
        "a",
        "al",
        "un",
        "una",
        "the",
        "or",
        "and",
        "to",
        "of",
        "for",
        "ser",
        "si",
        "no",
        "es",
        "se",
        "su",
        "ya",
        "muy",
        "con",
        "por",
        "que",
        "como",
    }
)
_JOIN_MORPHEME = re.compile(
    r"(?<=[A-Za-zÁÉÍÓÚáéíóúñ])\s+(?=ficar\b|ficial\b|ción\b|sión\b|mente\b)",
    re.IGNORECASE,
)
_TRAILING_PREP = re.compile(
    r"(?i)\b(?:a|al|de|del|en|con|por|para|como|cómo|que|cuál|quien|quién)\s*\??\s*$"
)
_GENERIC_PROMPT = re.compile(
    r"^(?:según el documento,\s*)?¿?\s*cuál de las siguientes afirmaciones es correcta\s*\??$"
    r"|^(?:according to the document,\s*)?which of the following statements is correct\??$",
    re.IGNORECASE,
)
_GENERIC_TOPIC_QUESTION = re.compile(
    r"(?i)^¿?(?:qué es|cuál es el propósito (?:de|del)|qué caracteriza a|"
    r"para qué se utiliza|qué papel tiene)\s+"
    r"(?:(?:el|la|los|las|un|una|de|del|al)\s+)*"
    r"(?:investigación(?: realizada)?|descripción|objetivo(?: principal)?|propósito|"
    r"resultado|análisis|estudio|contenido|tema|concepto|información|proceso|"
    r"sistema|ejemplo|parte|tipo)s?"
    r"(?:\s+\w+){0,3}\s*\??$"
)
_UNNATURAL_STEM = re.compile(
    r"(?i)según el (?:documento|fragmento|texto|material)|"
    r"cuál de las siguientes afirmaciones|"
    r"qué afirma el material|"
    r"qué indica el contenido|"
    r"qué término completa|"
    r"which term completes|"
    r"idea del material|"
    r"¿qué es a\b|"
    r"\bidenti\s|\b\w{3,6}\s+ficar\b"
)
_CLOZE_BLANK = re.compile(r"_{3,}")
_JUNK_SENTENCE = re.compile(
    r"(?i)(?:©|&copy;)|\beditorial\b|\bfuente:|\bfigura\s*\d|\bfigure\s*\d|"
    r"https?://|tabla de contenido|haga clic|click here|"
    r"\bentrypoint\b|\bdockerfile\b|\bdocker\s+build\b|#formato|\bparam\d|"
    r"\bcopy\s+\S+/|todos los derechos|"
    r"^(?:\[\d+\]|\d+\.\d{1,2}\.\d)|puzle|puzzle|arma la foto"
)
_HAS_VERB = re.compile(
    r"(?i)\b(?:es|son|está|están|era|fue|permite|permiten|genera|generan|"
    r"evita|evitan|ofrece|ofrecen|ejecuta|ejecutan|gestiona|gestionan|"
    r"agrupa|agrupan|procesa|procesan|consiste|sirve|utiliza|utilizan|"
    r"define|definen|describe|describen|representa|representan|"
    r"facilita|facilitan|reduce|reducen|incrementa|incrementan|"
    r"distingue|distinguen|descuenta|descuentan|crea|crean|usa|usan|"
    r"hace|hacen|incluye|incluyen|deriva|derivan|basa|basan|"
    r"encuentra|encuentran|cubre|cubren|tiene|tienen|se\s+\w+)\b"
)
_STOP = {
    "a",
    "al",
    "de",
    "del",
    "en",
    "con",
    "por",
    "para",
    "como",
    "cómo",
    "que",
    "cuál",
    "quien",
    "quién",
    "un",
    "una",
    "unos",
    "unas",
    "el",
    "la",
    "los",
    "las",
    "the",
    "an",
    "y",
    "o",
    "su",
    "sus",
    "se",
    "es",
    "son",
}
_GENERIC_HEADS = {
    "investigación",
    "descripción",
    "objetivo",
    "propósito",
    "resultado",
    "análisis",
    "estudio",
    "contenido",
    "tema",
    "concepto",
    "información",
    "proceso",
    "sistema",
    "ejemplo",
    "parte",
    "tipo",
    "uso",
    "manera",
    "forma",
}


def polish_exam_text(text: str) -> str:
    """Join PDF syllable breaks, unfold ligatures, and collapse leftover whitespace."""
    if not text:
        return text
    normalized = unicodedata.normalize("NFKC", text)
    normalized = _SOFT_HYPHEN.sub("", normalized)
    normalized = _HYPHEN_LINE_BREAK.sub("", normalized)
    normalized = _HYPHEN_BREAK.sub("", normalized)
    normalized = _join_spaced_syllables(normalized)
    normalized = _JOIN_MORPHEME.sub("", normalized)
    return re.sub(r"[ \t]+", " ", normalized).strip()


def normalize_extracted_text(text: str) -> str:
    """Clean PDF/plain extraction while preserving paragraph breaks for chunking."""
    if not text:
        return text
    normalized = unicodedata.normalize("NFKC", text).replace("\r\n", "\n").replace("\r", "\n")
    normalized = _SOFT_HYPHEN.sub("", normalized)
    normalized = _HYPHEN_LINE_BREAK.sub("", normalized)
    normalized = _HYPHEN_BREAK.sub("", normalized)
    normalized = _join_spaced_syllables(normalized)
    normalized = _JOIN_MORPHEME.sub("", normalized)
    paragraphs = []
    for block in re.split(r"\n\s*\n+", normalized):
        line = re.sub(r"[ \t]*\n[ \t]*", " ", block)
        line = re.sub(r"[ \t]+", " ", line).strip()
        if line:
            paragraphs.append(line)
    return "\n\n".join(paragraphs)


def _join_spaced_syllables(text: str) -> str:
    def replacer(match: re.Match[str]) -> str:
        left, right = match.group(1), match.group(2)
        if right.lower() in _DASH_KEEP:
            return match.group(0)
        return f"{left}{right}"

    return _SPACED_SYLLABLE.sub(replacer, text)


def usable_concept(concept: str) -> bool:
    """True when the phrase can stand as the object of a teacher question."""
    text = polish_exam_text(concept or "")
    tokens = re.findall(r"[A-Za-zÁÉÍÓÚÜÑáéíóúüñ0-9]+", text)
    articles = {"el", "la", "los", "las", "un", "una", "the", "a", "an"}
    while tokens and tokens[0].lower() in articles:
        tokens = tokens[1:]
    if not tokens:
        return False
    if tokens[-1].lower() in _STOP:
        return False
    content = [token for token in tokens if token.lower() not in _STOP]
    if not content:
        return False
    if len(" ".join(content)) < 4:
        return False
    has_proper = any(token[:1].isupper() and token[1:].islower() for token in content)
    has_acronym = any(token.isupper() and len(token) >= 2 for token in content)
    if any(token.lower() in _GENERIC_HEADS for token in content) and not (has_proper or has_acronym):
        return False
    return True


def is_exam_worthy(text: str) -> bool:
    """True when a sentence can support a teacher-written item (not a PDF dump)."""
    cleaned = polish_exam_text(text or "")
    if len(cleaned) < 40 or len(cleaned) > 260:
        return False
    if _JUNK_SENTENCE.search(cleaned):
        return False
    letters = sum(character.isalpha() for character in cleaned)
    digits = sum(character.isdigit() for character in cleaned)
    if letters / max(len(cleaned), 1) < 0.58:
        return False
    if digits / max(len(cleaned), 1) > 0.18:
        return False
    if cleaned.count("=") >= 2 or "/usr/" in cleaned.lower():
        return False
    return bool(_HAS_VERB.search(cleaned))


def cloze(sentence: str, concept: str) -> str:
    text = polish_exam_text(sentence)
    if not concept or not text:
        return text
    pattern = re.compile(re.escape(concept), re.IGNORECASE)
    if not pattern.search(text):
        return text
    return pattern.sub("________", text, count=1)


def _is_true_false(kind: Any) -> bool:
    value = getattr(kind, "value", kind)
    return str(value).lower() in {"true_false", "truefalse"}


def unnatural_question(question: Any, source: str = "") -> bool:
    """True when the item is generic, broken, or copied from the source dump."""
    prompt = polish_exam_text(getattr(question, "prompt", "") or "")
    if not prompt:
        return True
    if _GENERIC_PROMPT.match(prompt) or _GENERIC_TOPIC_QUESTION.match(prompt):
        return True
    if _UNNATURAL_STEM.search(prompt) or _TRAILING_PREP.search(prompt):
        return True
    without_blank = _CLOZE_BLANK.sub("", prompt)
    if len(re.sub(r"\W+", "", without_blank)) < 12:
        return True
    kind = getattr(question, "kind", None)
    if not _is_true_false(kind) and "?" not in prompt:
        return True
    if _is_true_false(kind) and (len(prompt) > 220 or prompt.count(".") > 2 or _CLOZE_BLANK.search(prompt)):
        return True
    if source and not _is_true_false(kind) and _copied_from_source(prompt, source):
        return True
    options = getattr(question, "options", []) or []
    if sum(1 for option in options if len(option or "") > 180) >= 2:
        return True
    compact = [re.sub(r"\W+", "", (option or "").lower()) for option in options]
    compact = [item for item in compact if item]
    if compact and len(set(compact)) < len(compact):
        return True
    return any(_JUNK_SENTENCE.search(option or "") for option in options)


def grounded_question(question: Any, source: str, anchor: str = "") -> bool:
    """The stem must be natural and, when an anchor exists, tied to the source."""
    if unnatural_question(question, source):
        return False
    if not anchor.strip():
        return True
    haystack = polish_exam_text(source).lower()
    needle = polish_exam_text(anchor).lower()
    if len(needle) >= 4 and needle not in haystack:
        tokens = [token for token in re.findall(r"[a-záéíóúüñ0-9]{4,}", needle, re.I) if token.lower() not in _STOP]
        if tokens and not any(token.lower() in haystack for token in tokens):
            return False
    options = getattr(question, "options", []) or []
    indices = getattr(question, "correct_indices", None) or []
    if not indices and getattr(question, "correct_index", None) is not None:
        indices = [question.correct_index]
    correct = " ".join(
        options[index] for index in indices if isinstance(index, int) and 0 <= index < len(options)
    )
    surface = f"{question.prompt} {correct}".lower()
    tokens = [token for token in re.findall(r"[a-záéíóúüñ0-9]{4,}", needle, re.I) if token.lower() not in _STOP]
    if tokens and not any(token.lower() in surface for token in tokens):
        return False
    return True


def _copied_from_source(prompt: str, source: str) -> bool:
    compact_prompt = re.sub(r"\W+", "", prompt.lower())
    compact_source = re.sub(r"\W+", "", source.lower())
    if len(compact_prompt) < 40:
        return False
    return compact_prompt in compact_source or compact_source[:90] in compact_prompt
