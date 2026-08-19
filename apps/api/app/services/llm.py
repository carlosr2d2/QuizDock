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


def _sentences(text: str) -> list[str]:
    parts = re.split(r"(?<=[\.\!\?])\s+", text)
    return [part.strip() for part in parts if 40 <= len(part.strip()) <= 280]


def _clip(text: str) -> str:
    return text[: settings.generation_max_chars]


class HeuristicClient:
    """Deterministic fallback so the pipeline works without an API key."""

    async def complete_json(self, system: str, user: str, temperature: float = 0.3) -> dict:
        if "Fragmento:\n" in user:
            body = user.split("Fragmento:\n", 1)[-1]
        else:
            body = user.split("Documento:\n", 1)[-1]
        source = _clip(body)
        sentences = _sentences(source) or [source[-220:] or "El documento no contiene texto suficiente."]
        count_match = re.search(r"exactamente (\d+)", user)
        count = int(count_match.group(1)) if count_match else 8
        if "flashcards" in system.lower() or "tarjetas" in system.lower():
            cards = []
            for index in range(count):
                sentence = sentences[index % len(sentences)]
                cards.append({"front": _prompt_from(sentence), "back": sentence})
            return {"cards": cards}

        kind_match = re.search(r"Tipo:\s*(true_false|single_choice|multiple_choice)", user)
        kind = kind_match.group(1) if kind_match else QuestionKind.SINGLE_CHOICE
        language_match = re.search(r"Idioma:\s*(\S+)", user)
        language = language_match.group(1) if language_match else "es"
        questions = []
        for index in range(count):
            questions.append(_heuristic_question(sentences, index, kind, language))
        return {"title": "Cuestionario generado", "questions": questions}


def _prompt_from(sentence: str) -> str:
    snippet = sentence[:90].rstrip(" .")
    return f"¿Cuál afirmación es correcta en relación con {snippet}?"


def boolean_options(language: str) -> list[str]:
    code = (language or "es").lower()[:2]
    if code == "en":
        return ["True", "False"]
    return ["Verdadero", "Falso"]


def _heuristic_question(sentences: list[str], index: int, kind: str, language: str) -> dict:
    sentence = sentences[index % len(sentences)]
    distractors = [sentences[(index + offset) % len(sentences)] for offset in (1, 2, 3)]
    if kind == QuestionKind.TRUE_FALSE:
        is_true = index % 2 == 0
        prompt = sentence if is_true else f"No es cierto que {sentence[0].lower() + sentence[1:]}"
        return {
            "prompt": prompt,
            "kind": QuestionKind.TRUE_FALSE,
            "options": boolean_options(language),
            "correct_index": 0 if is_true else 1,
            "correct_indices": [0 if is_true else 1],
            "explanation": sentence,
            "difficulty": "medium",
        }
    if kind == QuestionKind.MULTIPLE_CHOICE:
        return {
            "prompt": _prompt_from(sentence),
            "kind": QuestionKind.MULTIPLE_CHOICE,
            "options": [sentence, distractors[0], distractors[1], distractors[2]],
            "correct_index": 0,
            "correct_indices": [0, 1],
            "explanation": sentence,
            "difficulty": "medium",
        }
    return {
        "prompt": _prompt_from(sentence),
        "kind": QuestionKind.SINGLE_CHOICE,
        "options": [sentence, *distractors],
        "correct_index": 0,
        "correct_indices": [0],
        "explanation": sentence,
        "difficulty": "medium",
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
            text = data["candidates"][0]["content"]["parts"][0]["text"]
        except (KeyError, IndexError) as exc:
            raise RuntimeError(f"Gemini response missing text: {data}") from exc
        return _parse_json(text)


def get_llm_client() -> LLMClient:
    current = get_settings()
    if not current.llm_api_key.strip():
        return HeuristicClient()
    if is_gemini(current):
        return GeminiClient()
    return OpenAICompatibleClient()


_QUESTION_STYLES = (
    "definición de un concepto clave",
    "aplicación o uso práctico",
    "causa, consecuencia o procedimiento",
    "comparación o contraste entre ideas",
    "identificar el concepto a partir de una descripción",
)

_QUESTION_KINDS = (
    QuestionKind.SINGLE_CHOICE,
    QuestionKind.TRUE_FALSE,
    QuestionKind.MULTIPLE_CHOICE,
)

_EXAM_SYSTEM_BASE = (
    "Eres un evaluador técnico. Generas UNA pregunta fiel al contenido. "
    "Redáctala como ítem de examen autónomo: nunca menciones fragmento, documento, texto, "
    "extracto ni frases como 'según el fragmento'. Varía el enfoque según el estilo pedido. "
    "No uses tablas de contenido ni números de página. No inventes datos. "
    "Responde solo JSON válido con title y questions (array de 1 elemento). "
)

EXAM_SYSTEM_BY_KIND = {
    QuestionKind.TRUE_FALSE: (
        _EXAM_SYSTEM_BASE
        + "Tipo true_false: el prompt es una afirmación (no una pregunta). "
        "options exactamente 2: Verdadero y Falso (o True/False si el idioma es inglés). "
        "correct_index 0 si la afirmación es verdadera, 1 si es falsa. "
        "Campos: prompt, kind, options, correct_index, explanation, difficulty."
    ),
    QuestionKind.SINGLE_CHOICE: (
        _EXAM_SYSTEM_BASE
        + "Tipo single_choice: opción múltiple con UNA sola respuesta correcta. "
        "options exactamente 4. correct_index es el índice de la única opción correcta. "
        "Campos: prompt, kind, options, correct_index, explanation, difficulty."
    ),
    QuestionKind.MULTIPLE_CHOICE: (
        _EXAM_SYSTEM_BASE
        + "Tipo multiple_choice: opción múltiple con VARIAS respuestas correctas (2 o 3). "
        "options exactamente 4. correct_indices es un array con los índices correctos. "
        "Campos: prompt, kind, options, correct_indices, explanation, difficulty."
    ),
}

EXAM_SYSTEM = EXAM_SYSTEM_BY_KIND[QuestionKind.SINGLE_CHOICE]

FLASHCARD_SYSTEM = (
    "Eres un tutor. Generas UNA flashcard fiel al contenido. "
    "El anverso debe ser un término o pregunta autónoma: nunca menciones fragmento, documento "
    "ni 'según el texto'. No uses índices ni tablas de contenido. No inventes datos. "
    "Responde solo JSON válido con cards (array de 1 elemento). "
    "Cada card tiene front (término o pregunta) y back (respuesta breve)."
)


async def generate_exam_from_contexts(
    contexts: list[RetrievedContext] | list[str],
    question_count: int,
    language: str,
    title_hint: str,
    *,
    on_question: Callable[[GeneratedQuestion], Awaitable[None]] | None = None,
) -> GeneratedExam:
    if not contexts:
        raise ValueError("No hay fragmentos indexados para este documento")
    selected = _cycle(contexts, question_count)
    semaphore = asyncio.Semaphore(4)

    async def one(
        item: RetrievedContext | str,
        style: str,
        kind: QuestionKind,
    ) -> GeneratedQuestion | None:
        content = item.content if isinstance(item, RetrievedContext) else item
        async with semaphore:
            try:
                payload = await generate_exam_payload(content, 1, language, style=style, kind=kind)
                question = payload.questions[0] if payload.questions else None
                if question is not None and isinstance(item, RetrievedContext):
                    question.source_chunk_position = item.position
                if question is not None and on_question is not None:
                    await on_question(question)
                return question
            except Exception:
                return None

    results = await asyncio.gather(
        *[
            one(
                item,
                _QUESTION_STYLES[index % len(_QUESTION_STYLES)],
                _QUESTION_KINDS[index % len(_QUESTION_KINDS)],
            )
            for index, item in enumerate(selected)
        ]
    )
    questions = [item for item in results if item is not None]
    if not questions:
        raise ValueError("No se pudieron generar preguntas a partir de los fragmentos")
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
            except Exception:
                return None

    results = await asyncio.gather(*[one(item) for item in selected])
    cards = [item for item in results if item is not None]
    if not cards:
        raise ValueError("No se pudieron generar flashcards a partir de los fragmentos")
    return GeneratedDeck(cards=cards[:card_count])


def _cycle(items: list[T], count: int) -> list[T]:
    return [items[index % len(items)] for index in range(count)]


async def generate_exam_payload(
    text: str,
    question_count: int,
    language: str,
    *,
    style: str = "definición de un concepto clave",
    kind: QuestionKind = QuestionKind.SINGLE_CHOICE,
) -> GeneratedExam:
    client = get_llm_client()
    user = (
        f"Idioma: {language}. Tipo: {kind}. Genera exactamente {question_count} preguntas. "
        f"Estilo: {style}. No repitas redacciones genéricas.\n\n"
        f"Fragmento:\n{_clip(text)}"
    )
    data = await client.complete_json(EXAM_SYSTEM_BY_KIND[kind], user, temperature=0.7)
    exam = GeneratedExam.model_validate(data)
    exam.questions = exam.questions[:question_count]
    for question in exam.questions:
        question.prompt = standalone_prompt(question.prompt)
        coerce_question_kind(question, kind, language)
    return exam


async def generate_flashcard_payload(text: str, card_count: int, language: str) -> GeneratedDeck:
    client = get_llm_client()
    user = (
        f"Idioma: {language}. Genera exactamente {card_count} tarjetas (flashcards).\n\n"
        f"Fragmento:\n{_clip(text)}"
    )
    data = await client.complete_json(FLASHCARD_SYSTEM, user)
    deck = GeneratedDeck.model_validate(data)
    deck.cards = deck.cards[:card_count]
    for card in deck.cards:
        card.front = standalone_prompt(card.front)
    return deck
