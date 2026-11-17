from __future__ import annotations

import asyncio
import json
import re
from collections.abc import Awaitable, Callable
from typing import Protocol, TypeVar

import httpx
from pydantic import AliasChoices, BaseModel, Field, field_validator, model_validator

from app.core.config import get_settings
from app.core.llm_provider import GEMINI_API_ROOT, gemini_headers, gemini_model, is_gemini
from app.models.exam import QuestionKind
from app.services.exam_blueprint import ExamSlot, build_exam_blueprint, select_diverse_questions
from app.services.exam_quality import (
    grounded_question,
    is_exam_worthy,
    polish_exam_text,
    unnatural_question,
    usable_concept,
)
from app.services.rag import RetrievedContext

settings = get_settings()

T = TypeVar("T")

_FENCE = re.compile(r"^```(?:json)?\s*|\s*```$", re.IGNORECASE | re.MULTILINE)
_ATTRIBUTION = re.compile(
    r"^\s*¿?\s*(?:según|segun|de acuerdo con|a partir de|con base en|based on|according to)\s+"
    r"(?:el |la |este |esta |the )?"
    r"(?:fragmento|documento|texto|extracto|pasaje|excerpt|passage|context|provided text)"
    r"(?:\s+proporcionad[oa])?\s*[,:]?\s*",
    re.IGNORECASE,
)


class GeneratedQuestion(BaseModel):
    prompt: str
    kind: QuestionKind = QuestionKind.SINGLE_CHOICE
    options: list[str] = Field(min_length=2, max_length=6)
    correct_index: int | None = None
    correct_indices: list[int] = Field(
        default_factory=list,
        validation_alias=AliasChoices("correct_indices", "correct_indexes"),
    )
    explanation: str = ""
    difficulty: str = "medium"
    source_chunk_position: int | None = None
    claim: str = ""
    anchor: str = ""

    @field_validator("kind", mode="before")
    @classmethod
    def _parse_kind(cls, value: object) -> QuestionKind:
        if isinstance(value, QuestionKind):
            return value
        raw = str(value or "").strip().lower().replace("-", "_").replace(" ", "_")
        aliases = {
            "true_false": QuestionKind.TRUE_FALSE,
            "truefalse": QuestionKind.TRUE_FALSE,
            "boolean": QuestionKind.TRUE_FALSE,
            "tf": QuestionKind.TRUE_FALSE,
            "multiple_choice": QuestionKind.MULTIPLE_CHOICE,
            "multiple": QuestionKind.MULTIPLE_CHOICE,
            "multi": QuestionKind.MULTIPLE_CHOICE,
            "multi_select": QuestionKind.MULTIPLE_CHOICE,
        }
        return aliases.get(raw, QuestionKind.SINGLE_CHOICE)

    @model_validator(mode="after")
    def _index_in_range(self) -> GeneratedQuestion:
        indices = list(dict.fromkeys(self.correct_indices))
        if not indices and self.correct_index is not None:
            indices = [self.correct_index]
        if not indices:
            raise ValueError("missing correct answer")
        if any(index < 0 or index >= len(self.options) for index in indices):
            raise ValueError("correct_index out of range")
        self.correct_indices = sorted(indices)
        self.correct_index = self.correct_indices[0]
        return self


class GeneratedExam(BaseModel):
    title: str
    questions: list[GeneratedQuestion] = Field(min_length=1)


class GeneratedCard(BaseModel):
    front: str
    back: str


class GeneratedDeck(BaseModel):
    cards: list[GeneratedCard] = Field(min_length=1)


class LLMClient(Protocol):
    async def complete_json(self, system: str, user: str, temperature: float = 0.3) -> dict: ...


class OpenAICompatibleClient:
    async def complete_json(self, system: str, user: str, temperature: float = 0.3) -> dict:
        headers = {"Content-Type": "application/json"}
        if settings.llm_api_key:
            headers["Authorization"] = f"Bearer {settings.llm_api_key}"
        payload = {
            "model": settings.llm_model,
            "temperature": temperature,
            "response_format": {"type": "json_object"},
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
        }
        url = settings.llm_base_url.rstrip("/") + "/chat/completions"
        async with httpx.AsyncClient(timeout=settings.llm_timeout_seconds) as client:
            response = await client.post(url, headers=headers, json=payload)
            if response.status_code >= 400 and "response_format" in payload:
                payload.pop("response_format", None)
                response = await client.post(url, headers=headers, json=payload)
            response.raise_for_status()
            content = response.json()["choices"][0]["message"]["content"]
        return _parse_json(content)


def _parse_json(raw: str) -> dict:
    cleaned = _FENCE.sub("", raw.strip()).strip()
    data = json.loads(cleaned)
    if not isinstance(data, dict):
        raise ValueError("LLM response is not a JSON object")
    return data


_HEADING_PREFIX = re.compile(r"^[\d.]+\s+")
_TOPIC_SKIP = re.compile(
    r"^(?:el|la|los|las|un|una|unos|unas|the|a|an|este|esta|estos|estas|this|that|"
    r"de|del|al|en|con|por|para|sobre|como|que|y|o|su|sus|se|es|son|"
    r"prefacio|introducción|introduccion|capítulo|capitulo|sección|seccion|"
    r"opciones|opción|opcion)$",
    re.IGNORECASE,
)
_GENERIC_PROMPT = re.compile(
    r"^(?:según el documento,\s*)?¿?\s*cuál de las siguientes afirmaciones es correcta\s*\??$"
    r"|^(?:according to the document,\s*)?which of the following statements is correct\??$",
    re.IGNORECASE,
)
_CLIPPED_STEM = re.compile(
    r"^¿?\s*Cuál afirmación es correcta en relación con\s+(.+?)\s*\??\s*$",
    re.IGNORECASE | re.DOTALL,
)
_QUOTED_TERM = re.compile(r"«([^»]{3,80})»|\"([^\"]{3,80})\"")
_ALIASED_PROPER = re.compile(
    r"\b((?:[A-ZÁÉÍÓÚÑ][\w.+-]{2,})\s+o\s+(?:[A-ZÁÉÍÓÚÑ][\w.+-]{2,}))\b"
)
_CLOZE_WRAP = re.compile(
    r"(?is)^¿?\s*(?:qué término completa esta idea del material|"
    r"which term completes this idea from the material)\s*\??\s*[«“\"](.+)[»”\"]\s*$"
)
_VERB_PHRASE = re.compile(
    r"(?i)(?:(?:también|además)\s+)?(?:nos\s+|se\s+|le\s+|les\s+|lo\s+)?"
    r"(?:es|son|está|están|era|fue|permite|permiten|genera|generan|"
    r"evita|evitan|ofrece|ofrecen|ejecuta|ejecutan|gestiona|gestionan|"
    r"agrupa|agrupan|procesa|procesan|consiste|sirve|utiliza|utilizan|"
    r"define|definen|describe|describen|representa|representan|"
    r"facilita|facilitan|reduce|reducen|incrementa|incrementan|"
    r"distingue|distinguen|descuenta|descuentan|crea|crean|usa|usan|"
    r"hace|hacen|incluye|incluyen|deriva|derivan|basa|basan|"
    r"encuentra|encuentran|cubre|cubren|tiene|tienen)\b"
)
_PROPER_TERM = re.compile(
    r"\b((?:[A-ZÁÉÍÓÚÑ][\w.+-]{1,})(?:\s+[A-ZÁÉÍÓÚÑ0-9][\w.+-]{0,}){0,3})\b"
)
_ARTICLE_NOUN = re.compile(
    r"\b((?:el|la|los|las|un|una|the|a|an)\s+[A-Za-zÁÉÍÓÚÜÑáéíóúüñ]{4,}"
    r"(?:\s+[A-Za-zÁÉÍÓÚÜÑáéíóúüñ]{4,})?)",
    re.IGNORECASE,
)


def _sentences(text: str) -> list[str]:
    normalized = polish_exam_text(text)
    parts = [
        part.strip()
        for part in re.split(r"(?<=[\.\!\?])\s+|\n+", normalized)
        if part.strip()
    ]
    return [part for part in parts if is_exam_worthy(part)]


def _clip(text: str) -> str:
    return polish_exam_text(text)[: settings.generation_max_chars]


class HeuristicClient:
    """Deterministic fallback so the pipeline works without an API key."""

    async def complete_json(self, system: str, user: str, temperature: float = 0.3) -> dict:
        if "Material de estudio:\n" in user:
            body = user.split("Material de estudio:\n", 1)[-1]
        elif "Fragmento:\n" in user:
            body = user.split("Fragmento:\n", 1)[-1]
        else:
            body = user.split("Documento:\n", 1)[-1]
        source = _clip(body)
        sentences = _sentences(source)
        count_match = re.search(r"exactamente (\d+)", user)
        count = int(count_match.group(1)) if count_match else 8
        language_match = re.search(r"Idioma:\s*(\S+)", user)
        language = language_match.group(1) if language_match else "es"
        if "flashcards" in system.lower() or "tarjetas" in system.lower():
            cards = []
            pool = sentences or [source[-220:] or "El documento no contiene texto suficiente."]
            for index in range(count):
                sentence = pool[index % len(pool)]
                concept = _concept_from(sentence)
                front = concept if usable_concept(concept) else _prompt_from(sentence, language, index)
                cards.append({"front": front or _option_text(sentence, 80), "back": _option_text(sentence, 240)})
            return {"cards": cards}

        kind_match = re.search(r"Tipo:\s*(true_false|single_choice|multiple_choice)", user)
        kind = kind_match.group(1) if kind_match else QuestionKind.SINGLE_CHOICE
        questions = []
        for index in range(count):
            item = _heuristic_question(sentences, index, kind, language)
            if item is not None:
                questions.append(item)
        if not questions:
            raise ValueError("No exam-worthy sentences in this fragment")
        return {"title": "Cuestionario generado", "questions": questions}


def _topic_from(sentence: str, max_words: int = 4) -> str:
    text = _HEADING_PREFIX.sub("", polish_exam_text(sentence or ""))
    words = re.findall(r"[A-Za-zÁÉÍÓÚÜÑáéíóúüñ0-9]+", text)
    content = [word for word in words if not _TOPIC_SKIP.match(word) and len(word) > 2]
    if not content:
        content = words or re.findall(r"\S+", text)
    topic = " ".join(content[:max_words]).strip(" .,;:«»\"'")
    return topic or text[:48].rstrip(" .,;:")


def _normalize_topic(topic: str) -> str:
    parts = topic.split()
    if parts and _TOPIC_SKIP.match(parts[0]):
        parts[0] = parts[0].lower()
        return " ".join(parts)
    return topic


def _concept_from(sentence: str) -> str:
    """Pick a short concept a teacher would name in a question."""
    text = _HEADING_PREFIX.sub("", polish_exam_text(sentence or ""))
    quoted = _QUOTED_TERM.search(text)
    if quoted:
        return _normalize_topic((quoted.group(1) or quoted.group(2)).strip())
    aliased = _ALIASED_PROPER.search(text)
    if aliased:
        return aliased.group(1).strip()
    multi_proper: list[str] = []
    short_proper: list[str] = []
    for match in _PROPER_TERM.finditer(text):
        name = match.group(1).strip()
        words = name.split()
        if not words or (_TOPIC_SKIP.match(words[0]) and len(words) == 1):
            continue
        if len(words) >= 2:
            multi_proper.append(name)
        elif len(name) >= 3:
            short_proper.append(name)
    if multi_proper:
        return _normalize_topic(multi_proper[0])
    if short_proper:
        candidate = _normalize_topic(max(short_proper, key=len))
        if usable_concept(candidate):
            return candidate
    article = _ARTICLE_NOUN.search(text)
    if article:
        candidate = _normalize_topic(article.group(1).strip())
        if usable_concept(candidate):
            return candidate
    fallback = _topic_from(text, max_words=3)
    return fallback if usable_concept(fallback) else ""


def _with_preposition(preposition: str, topic: str) -> str:
    lower = topic.lower()
    article = next((word for word in ("el", "la", "los", "las") if lower.startswith(word + " ")), "")
    rest = topic[len(article) + 1 :] if article else topic
    if preposition == "de" and article == "el":
        return "del " + rest
    if preposition == "a" and article == "el":
        return "al " + rest
    if article:
        return f"{preposition} {article} {rest}"
    return f"{preposition} {topic}"


def _with_de(topic: str) -> str:
    return _with_preposition("de", topic)


def _predicate_after_concept(sentence: str, concept: str) -> str:
    text = polish_exam_text(sentence or "")
    if concept:
        text = re.sub(re.escape(concept), " ", text, count=1, flags=re.I)
    text = re.sub(r"[«»\"“”]", " ", text)
    text = re.sub(
        r"^(?:o|u|or|and|y|e)\s+[A-Za-zÁÉÍÓÚÑ][\w.+-]{1,}(?:\s+[A-ZÁÉÍÓÚÑ][\w.+-]{1,})?\s+",
        "",
        text.strip(),
        flags=re.I,
    )
    text = polish_exam_text(text).strip(" ,;:.-")
    match = _VERB_PHRASE.search(text)
    if match:
        text = text[match.start() :]
    return _option_text(text, 140)


def _usable_predicate(predicate: str) -> bool:
    text = polish_exam_text(predicate or "")
    return len(text) >= 20 and bool(_VERB_PHRASE.search(text))


def _question_from_predicate(predicate: str, language: str) -> str:
    body = predicate[0].lower() + predicate[1:] if predicate else predicate
    body = body.rstrip(".!?")
    if (language or "es").lower()[:2] == "en":
        return f"What {body}?"
    return f"¿Qué {body}?"


def _prompt_from(sentence: str, language: str = "es", index: int = 0) -> str:
    """Ask about the fact in the sentence; the answer is the named concept."""
    del index
    english = (language or "es").lower()[:2] == "en"
    concept = _concept_from(sentence)
    predicate = _predicate_after_concept(sentence, concept) if concept else ""
    if usable_concept(concept) and _usable_predicate(predicate):
        return _question_from_predicate(predicate, language)
    if usable_concept(concept):
        if english:
            return f"What role does {concept} play?"
        return f"¿Qué función tiene {concept}?"
    return ""


def _option_text(sentence: str, limit: int = 180) -> str:
    text = polish_exam_text(sentence)
    text = re.split(r"(?<=[\.\!\?])\s+", text, maxsplit=1)[0].strip()
    if len(text) > limit:
        text = text[:limit].rsplit(" ", 1)[0].rstrip(".,;:") + "…"
    if text and text[0].islower():
        text = text[0].upper() + text[1:]
    return text


def _is_boolean_options(options: list[str] | None) -> bool:
    labels = {polish_exam_text(option).lower() for option in options or [] if option}
    return len(labels) == 2 and labels <= {"verdadero", "falso", "true", "false", "v", "f"}


def _source_option(prompt: str, options: list[str] | None) -> str | None:
    text = (prompt or "").strip()
    match = _CLIPPED_STEM.match(text)
    snippet = match.group(1).strip(" .") if match else ""
    cleaned = [(option or "").strip() for option in options or [] if (option or "").strip()]
    if snippet:
        for option in cleaned:
            if option.startswith(snippet) and len(option) > len(snippet):
                return option
        return None
    cloze_match = _CLOZE_WRAP.match(text)
    if cloze_match:
        quoted = cloze_match.group(1).strip()
        concept = cleaned[0] if cleaned and not _is_boolean_options(cleaned) and len(cleaned[0]) <= 60 else ""
        restored = re.sub(r"_{3,}", concept or " ", quoted)
        return polish_exam_text(restored)
    if _GENERIC_PROMPT.match(text):
        return max(cleaned, key=len) if cleaned else None
    return None


def repair_clipped_prompt(prompt: str, options: list[str] | None = None) -> str:
    """Replace truncated or dumped stems with a teacher-style question."""
    if _is_boolean_options(options):
        return prompt
    source = _source_option(prompt, options)
    if not source:
        return prompt
    repaired = _prompt_from(source, "es")
    if not repaired:
        return prompt
    probe_options = list(options or [])
    if len(probe_options) < 2:
        probe_options = (probe_options + ["A", "B"])[:2]
    probe = GeneratedQuestion.model_validate(
        {"prompt": repaired, "options": probe_options, "correct_index": 0}
    )
    if unnatural_question(probe):
        return prompt
    return repaired


def present_exam_item(prompt: str, options: list[str] | None) -> tuple[str, list[str]]:
    raw_options = [polish_exam_text(item) for item in options or []]
    cleaned = polish_exam_text(prompt)
    if _is_boolean_options(raw_options):
        match = _CLOZE_WRAP.match(cleaned)
        if match:
            restored = polish_exam_text(re.sub(r"_{3,}", " ", match.group(1)))
            if len(re.sub(r"\W+", "", restored)) >= 20:
                return _option_text(restored, 180), raw_options
        return cleaned, raw_options
    repaired = repair_clipped_prompt(cleaned, raw_options)
    if repaired != cleaned:
        return repaired, raw_options
    probe_options = (raw_options + ["A", "B"])[:2]
    probe = GeneratedQuestion.model_validate(
        {"prompt": repaired, "options": probe_options, "correct_index": 0}
    )
    if unnatural_question(probe) and raw_options and not _is_boolean_options(raw_options):
        source = max(raw_options, key=len)
        rebuilt = _prompt_from(source, "es")
        if not rebuilt:
            return repaired, raw_options
        rebuilt_probe = GeneratedQuestion.model_validate(
            {"prompt": rebuilt, "options": probe_options, "correct_index": 0}
        )
        if not unnatural_question(rebuilt_probe):
            return rebuilt, raw_options
    return repaired, raw_options


def boolean_options(language: str) -> list[str]:
    code = (language or "es").lower()[:2]
    if code == "en":
        return ["True", "False"]
    return ["Verdadero", "Falso"]


def _concept_choices(sentences: list[str], concept: str, index: int) -> list[str]:
    others: list[str] = []
    for offset, sentence in enumerate(sentences):
        if offset == index % max(len(sentences), 1):
            continue
        candidate = _concept_from(sentence)
        if not usable_concept(candidate):
            continue
        if candidate.lower() == concept.lower() or candidate in others:
            continue
        others.append(candidate)
        if len(others) == 3:
            break
    filler_at = index
    while len(others) < 3 and sentences:
        filler_at += 1
        filler = _option_text(sentences[filler_at % len(sentences)], 48)
        if filler and filler not in others and filler.lower() != concept.lower():
            others.append(filler)
        if filler_at > index + len(sentences) + 3:
            others.append(f"Opción {len(others) + 1}")
    return others[:3]


def _heuristic_question(
    sentences: list[str],
    index: int,
    kind: str,
    language: str,
    *,
    force: bool = False,
) -> dict | None:
    if not sentences:
        return None
    wanted = QuestionKind.parse(kind)
    english = (language or "es").lower()[:2] == "en"
    last: dict | None = None
    for offset in range(len(sentences)):
        position = (index + offset) % len(sentences)
        sentence = sentences[position]
        if not is_exam_worthy(sentence) and not force:
            continue
        concept = _concept_from(sentence)
        predicate = _predicate_after_concept(sentence, concept) if concept else ""
        claim = _option_text(sentence, 160)
        payload: dict | None = None
        if wanted is QuestionKind.TRUE_FALSE:
            payload = _heuristic_true_false(
                sentences, position, sentence, concept, claim, language, index
            )
        elif wanted is QuestionKind.MULTIPLE_CHOICE:
            payload = _heuristic_multi(
                sentences, position, sentence, concept, predicate, language, english
            )
        else:
            payload = _heuristic_single(
                sentences, position, sentence, concept, predicate, language
            )
        if payload is None:
            continue
        question = GeneratedQuestion.model_validate(payload)
        last = payload
        if not unnatural_question(question, sentence):
            return payload
        if force:
            return payload
    return last if force else None


def _heuristic_true_false(
    sentences: list[str],
    position: int,
    sentence: str,
    concept: str,
    claim: str,
    language: str,
    index: int,
) -> dict | None:
    if len(claim) < 24:
        return None
    is_true = index % 2 == 0
    prompt = claim if claim.endswith(".") else f"{claim}."
    if not is_true:
        other = _concept_from(sentences[(position + 1) % len(sentences)])
        swapped = ""
        if usable_concept(concept) and usable_concept(other) and other.lower() != concept.lower():
            swapped = re.sub(re.escape(concept), other, sentence, count=1, flags=re.I)
            swapped = _option_text(swapped, 160)
        if swapped and swapped.lower() != claim.lower():
            prompt = swapped if swapped.endswith(".") else f"{swapped}."
        else:
            body = claim[0].lower() + claim[1:]
            prompt = f"No es cierto que {body}"
            if not prompt.endswith("."):
                prompt += "."
    return {
        "prompt": prompt,
        "kind": QuestionKind.TRUE_FALSE,
        "options": boolean_options(language),
        "correct_index": 0 if is_true else 1,
        "correct_indices": [0 if is_true else 1],
        "explanation": sentence,
        "difficulty": "medium",
        "claim": claim,
        "anchor": concept,
    }


def _heuristic_single(
    sentences: list[str],
    position: int,
    sentence: str,
    concept: str,
    predicate: str,
    language: str,
) -> dict | None:
    prompt = _prompt_from(sentence, language, position)
    if not prompt or not usable_concept(concept):
        return None
    options = [concept, *_concept_choices(sentences, concept, position)]
    if len(options) < 4:
        return None
    return {
        "prompt": prompt,
        "kind": QuestionKind.SINGLE_CHOICE,
        "options": options[:4],
        "correct_index": 0,
        "correct_indices": [0],
        "explanation": sentence,
        "difficulty": "medium",
        "claim": predicate or sentence,
        "anchor": concept,
    }


def _heuristic_multi(
    sentences: list[str],
    position: int,
    sentence: str,
    concept: str,
    predicate: str,
    language: str,
    english: bool,
) -> dict | None:
    if not usable_concept(concept) or not _usable_predicate(predicate):
        return None
    true_a = _option_text(predicate, 110)
    true_b = _option_text(sentence, 110)
    if not true_a or not true_b or true_a.lower() == true_b.lower():
        return None
    false_options: list[str] = []
    for offset in range(2, 2 + max(len(sentences), 3)):
        other = sentences[(position + offset) % len(sentences)]
        other_concept = _concept_from(other)
        other_pred = _predicate_after_concept(other, other_concept) if other_concept else ""
        candidate = _option_text(other_pred or other, 110)
        if not candidate:
            continue
        labels = {true_a.lower(), true_b.lower(), *[item.lower() for item in false_options]}
        if candidate.lower() in labels:
            continue
        false_options.append(candidate)
        if len(false_options) == 2:
            break
    if len(false_options) < 2:
        negation = true_a[0].lower() + true_a[1:] if true_a else "esto ocurre"
        false_options.append(f"No {negation}")
    if len(false_options) < 2:
        false_options.append(f"{concept} no interviene en este caso.")
    prompt = f"What is true about {concept}?" if english else f"¿Qué es cierto sobre {concept}?"
    return {
        "prompt": prompt,
        "kind": QuestionKind.MULTIPLE_CHOICE,
        "options": [true_a, true_b, false_options[0], false_options[1]],
        "correct_index": 0,
        "correct_indices": [0, 1],
        "explanation": sentence,
        "difficulty": "medium",
        "claim": predicate,
        "anchor": concept,
    }


def coerce_question_kind(question: GeneratedQuestion, kind: QuestionKind, language: str) -> GeneratedQuestion:
    question.kind = kind
    if kind == QuestionKind.TRUE_FALSE:
        labels = boolean_options(language)
        truthy = {"verdadero", "true", "v", "cierto", "sí", "si"}
        selected_text = ""
        index = (question.correct_indices or [0])[0]
        if question.options and 0 <= index < len(question.options):
            selected_text = question.options[index].strip().lower()
        is_true = selected_text in truthy or (not selected_text and index == 0)
        question.options = labels
        question.correct_indices = [0 if is_true else 1]
        question.correct_index = question.correct_indices[0]
        return question
    if kind == QuestionKind.MULTIPLE_CHOICE:
        if len(question.correct_indices) < 2:
            question.kind = QuestionKind.SINGLE_CHOICE
            question.correct_indices = question.correct_indices[:1] or [0]
            question.correct_index = question.correct_indices[0]
        return question
    question.correct_indices = [question.correct_indices[0]]
    question.correct_index = question.correct_indices[0]
    return question


def standalone_prompt(text: str) -> str:
    cleaned = _ATTRIBUTION.sub("", text.strip()).strip(" ,;:-")
    if not cleaned:
        return text.strip()
    if cleaned.endswith("?") and not cleaned.startswith("¿"):
        return f"¿{cleaned}"
    return cleaned[:1].upper() + cleaned[1:]


class GeminiClient:
    """Native Gemini generateContent. Required for AQ. Auth keys from AI Studio."""

    async def complete_json(self, system: str, user: str, temperature: float = 0.3) -> dict:
        current = get_settings()
        model = gemini_model(current.llm_model)
        url = f"{GEMINI_API_ROOT}/models/{model}:generateContent"
        payload: dict = {
            "system_instruction": {"parts": [{"text": system}]},
            "contents": [{"role": "user", "parts": [{"text": user}]}],
            "generationConfig": {
                "temperature": temperature,
                "responseMimeType": "application/json",
                "thinkingConfig": {"thinkingBudget": 0},
            },
        }
        async with httpx.AsyncClient(timeout=current.llm_timeout_seconds) as client:
            response = await client.post(url, headers=gemini_headers(current), json=payload)
            if response.status_code >= 400 and "responseMimeType" in payload["generationConfig"]:
                payload["generationConfig"].pop("responseMimeType", None)
                response = await client.post(url, headers=gemini_headers(current), json=payload)
            if response.status_code >= 400:
                raise RuntimeError(f"Gemini generateContent {response.status_code}: {response.text[:400]}")
            data = response.json()
        try:
            parts = data["candidates"][0]["content"]["parts"]
            text = "".join(part.get("text", "") for part in parts if isinstance(part, dict))
            if not text.strip():
                raise KeyError("empty text")
        except (KeyError, IndexError, TypeError) as exc:
            raise RuntimeError(f"Gemini response missing text: {data}") from exc
        return _parse_json(text)


def get_llm_client() -> LLMClient:
    current = get_settings()
    if not current.llm_api_key.strip():
        raise RuntimeError(
            "LLM_API_KEY is required. Exam and flashcard generation must use an LLM."
        )
    if is_gemini(current):
        return GeminiClient()
    return OpenAICompatibleClient()


_EXAM_SYSTEM_BASE = (
    "Eres un profesor universitario que diseña un examen a partir de UN material concreto. "
    "Primero extraes UN hecho enseñable (claim) y un ancla (anchor: nombre, término, cifra o procedimiento "
    "que aparece literalmente en el material). Luego redactas UNA pregunta que solo se puede responder "
    "con ese hecho: si quitas el material, la pregunta deja de tener respuesta única. "
    "El enunciado debe mencionar el ancla. Prohibido: preguntas genéricas "
    "('cuál es el propósito de la investigación', 'qué es una descripción', 'qué es a cómo'), "
    "cortar palabras, terminar en preposición, mencionar fragmento/documento/extracto, "
    "copiar el párrafo como enunciado u opción, "
    "huecos ('¿Qué término completa esta idea del material?'), cabeceras, © o código. "
    "Opciones: una idea cada una, máximo ~25 palabras, paralelas y plausibles. "
    "JSON válido con title, claim, anchor y questions (array de 1 elemento). "
)

EXAM_SYSTEM_BY_KIND = {
    QuestionKind.TRUE_FALSE: (
        _EXAM_SYSTEM_BASE
        + "Tipo true_false: el prompt es UNA afirmación breve y precisa, no una pregunta y no un párrafo. "
        "Ejemplo bueno: 'El discriminador de una GAN distingue muestras reales de generadas.' "
        "options exactamente 2: Verdadero y Falso (o True/False si el idioma es inglés). "
        "correct_index 0 si la afirmación es verdadera, 1 si es falsa. "
        "Campos: prompt, kind, options, correct_index, explanation, difficulty."
    ),
    QuestionKind.SINGLE_CHOICE: (
        _EXAM_SYSTEM_BASE
        + "Tipo single_choice: opción múltiple con UNA sola respuesta correcta. "
        "Ejemplo bueno: prompt '¿Qué papel cumple el discriminador en una GAN?' "
        "y cuatro opciones cortas, una correcta. "
        "options exactamente 4. correct_index es el índice de la única opción correcta. "
        "Campos: prompt, kind, options, correct_index, explanation, difficulty."
    ),
    QuestionKind.MULTIPLE_CHOICE: (
        _EXAM_SYSTEM_BASE
        + "Tipo multiple_choice: opción múltiple con VARIAS respuestas correctas (2 o 3). "
        "El enunciado pide seleccionar todas las que apliquen sobre un concepto concreto. "
        "options exactamente 4. correct_indices es un array con los índices correctos. "
        "Campos: prompt, kind, options, correct_indices, explanation, difficulty."
    ),
}

EXAM_SYSTEM = EXAM_SYSTEM_BY_KIND[QuestionKind.SINGLE_CHOICE]

FLASHCARD_SYSTEM = (
    "Eres un profesor que prepara tarjetas de estudio. Generas UNA flashcard fiel al contenido. "
    "El anverso es un término o una pregunta breve como la escribiría un estudiante "
    "('¿Qué es el espacio latente?', 'GAN'). "
    "El reverso es una definición de una o dos frases, no un párrafo copiado. "
    "Nunca menciones fragmento, documento ni 'según el texto'. No uses índices ni páginas. "
    "No inventes datos. Responde solo JSON válido con cards (array de 1 elemento). "
    "Cada card tiene front y back."
)


async def generate_exam_from_contexts(
    contexts: list[RetrievedContext] | list[str],
    question_count: int,
    language: str,
    title_hint: str,
    *,
    on_question: Callable[[GeneratedQuestion], Awaitable[None]] | None = None,
    on_progress: Callable[[int, int], Awaitable[None]] | None = None,
) -> GeneratedExam:
    if not contexts:
        raise ValueError("No hay fragmentos indexados para este documento")
    semaphore = asyncio.Semaphore(4)
    produced = 0
    progress_lock = asyncio.Lock()

    async def one(slot: ExamSlot) -> GeneratedQuestion | None:
        nonlocal produced
        item = slot.context
        content = item.content if isinstance(item, RetrievedContext) else item
        question: GeneratedQuestion | None = None
        async with semaphore:
            try:
                payload = await generate_exam_payload(
                    content,
                    1,
                    language,
                    style=slot.style,
                    kind=slot.kind,
                    subject=title_hint,
                    focus=slot.focus,
                )
                question = payload.questions[0] if payload.questions else None
                if question is None:
                    return None
                if unnatural_question(question, content) or not grounded_question(
                    question, content, question.anchor
                ):
                    return None
                if isinstance(item, RetrievedContext):
                    question.source_chunk_position = item.position
            except RuntimeError:
                raise
            except Exception:
                return None
        if question is not None and on_progress is not None:
            async with progress_lock:
                produced += 1
                await on_progress(min(produced, question_count), question_count)
        return question

    blueprint = build_exam_blueprint(contexts, max(question_count * 2, question_count))
    results = await asyncio.gather(*[one(slot) for slot in blueprint])
    questions = select_diverse_questions(
        [item for item in results if item is not None],
        question_count,
    )
    if not questions:
        raise ValueError("No se pudieron generar preguntas a partir de los fragmentos")
    if on_question is not None:
        for question in questions:
            await on_question(question)
    return GeneratedExam(title=title_hint, questions=questions[:question_count])


async def generate_flashcards_from_contexts(
    contexts: list[RetrievedContext] | list[str],
    card_count: int,
    language: str,
) -> GeneratedDeck:
    if not contexts:
        raise ValueError("No hay fragmentos indexados para este documento")
    selected = _cycle(contexts, card_count)
    semaphore = asyncio.Semaphore(4)

    async def one(item: RetrievedContext | str) -> GeneratedCard | None:
        content = item.content if isinstance(item, RetrievedContext) else item
        async with semaphore:
            try:
                payload = await generate_flashcard_payload(content, 1, language)
                return payload.cards[0] if payload.cards else None
            except RuntimeError:
                raise
            except Exception:
                return None

    results = await asyncio.gather(*[one(item) for item in selected])
    cards = [item for item in results if item is not None]
    if not cards:
        raise ValueError("No se pudieron generar flashcards a partir de los fragmentos")
    return GeneratedDeck(cards=cards[:card_count])


def _cycle(items: list[T], count: int) -> list[T]:
    return [items[index % len(items)] for index in range(count)]


def _exam_user_prompt(
    text: str,
    language: str,
    kind: QuestionKind,
    style: str,
    question_count: int,
    subject: str = "",
    focus: str = "",
    *,
    rewrite: bool = False,
) -> str:
    rewrite_line = (
        "La versión anterior era genérica o no estaba anclada al material. "
        "Extrae un hecho concreto (claim) y un ancla literal, y redacta de nuevo.\n"
        if rewrite
        else ""
    )
    subject_line = f"Tema: {subject}. " if subject.strip() else ""
    focus_line = (
        f"Esta pregunta cubre este tramo del material: {focus}. No salgas de ese foco.\n"
        if focus.strip()
        else ""
    )
    return (
        f"{rewrite_line}{subject_line}{focus_line}"
        f"Idioma: {language}. Tipo: {kind}. Enfoque: {style}. "
        f"Genera exactamente {question_count} preguntas. "
        "El campo anchor debe aparecer en el material y en el enunciado.\n\n"
        f"Material de estudio:\n{_clip(text)}"
    )


async def generate_exam_payload(
    text: str,
    question_count: int,
    language: str,
    *,
    style: str = "definición de un concepto clave",
    kind: QuestionKind = QuestionKind.SINGLE_CHOICE,
    subject: str = "",
    focus: str = "",
    rewrite: bool = False,
) -> GeneratedExam:
    client = get_llm_client()
    user = _exam_user_prompt(
        text, language, kind, style, question_count, subject, focus, rewrite=rewrite
    )
    data = await client.complete_json(EXAM_SYSTEM_BY_KIND[kind], user, temperature=0.65)
    exam = GeneratedExam.model_validate(data)
    exam.questions = exam.questions[:question_count]
    anchor = polish_exam_text(str(data.get("anchor") or ""))
    claim = polish_exam_text(str(data.get("claim") or ""))
    for question in exam.questions:
        question.prompt = repair_clipped_prompt(standalone_prompt(question.prompt), question.options)
        question.options = [_option_text(option, 220) for option in question.options]
        question.anchor = question.anchor or anchor
        question.claim = question.claim or claim
        coerce_question_kind(question, kind, language)
    needs_rewrite = not rewrite and any(
        unnatural_question(question, text) or not grounded_question(question, text, question.anchor)
        for question in exam.questions
    )
    if needs_rewrite:
        return await generate_exam_payload(
            text,
            question_count,
            language,
            style=style,
            kind=kind,
            subject=subject,
            focus=focus,
            rewrite=True,
        )
    return exam


async def generate_flashcard_payload(text: str, card_count: int, language: str) -> GeneratedDeck:
    client = get_llm_client()
    user = (
        f"Idioma: {language}. Genera exactamente {card_count} tarjetas de estudio "
        f"con pregunta o término en el anverso y una definición breve al dorso.\n\n"
        f"Material de estudio:\n{_clip(text)}"
    )
    data = await client.complete_json(FLASHCARD_SYSTEM, user, temperature=0.65)
    deck = GeneratedDeck.model_validate(data)
    deck.cards = deck.cards[:card_count]
    for card in deck.cards:
        card.front = standalone_prompt(card.front)
        card.back = _option_text(card.back, 280)
    return deck
