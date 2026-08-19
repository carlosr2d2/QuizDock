from __future__ import annotations

import asyncio
import hashlib
import logging
import math
import random
import re

import httpx

from app.core.config import get_settings
from app.core.constants import EMBEDDING_DIM
from app.core.llm_provider import GEMINI_API_ROOT, gemini_headers, gemini_model, is_gemini

logger = logging.getLogger(__name__)

_TOKEN = re.compile(r"[a-záéíóúüñA-ZÁÉÍÓÚÜÑ0-9]{3,}")
_RETRY_STATUSES = {408, 429, 500, 502, 503, 504}
_GEMINI_BATCH = 50
_OPENAI_BATCH = 64
_MAX_ATTEMPTS = 5


def hashed_embedding(text: str, dim: int = EMBEDDING_DIM) -> list[float]:
    """Feature-hashing vector so RAG works without an embedding API."""
    vector = [0.0] * dim
    for token in _TOKEN.findall(text.lower()):
        digest = hashlib.sha256(token.encode("utf-8")).digest()
        index = int.from_bytes(digest[:4], "big") % dim
        sign = 1.0 if digest[4] % 2 == 0 else -1.0
        vector[index] += sign
    return _l2_normalize(vector)


def _l2_normalize(vector: list[float]) -> list[float]:
    norm = math.sqrt(sum(value * value for value in vector)) or 1.0
    return [value / norm for value in vector]


async def embed_texts(texts: list[str], *, task_type: str = "RETRIEVAL_DOCUMENT") -> list[list[float]]:
    if not texts:
        return []
    settings = get_settings()
    if not settings.llm_api_key.strip():
        return [hashed_embedding(text) for text in texts]
    if is_gemini(settings):
        return await _gemini_embed(texts, task_type)
    return await _openai_embed(texts)


async def embed_query(text: str) -> list[float]:
    return (await embed_texts([text], task_type="RETRIEVAL_QUERY"))[0]


async def _gemini_embed(texts: list[str], task_type: str) -> list[list[float]]:
    settings = get_settings()
    model = gemini_model(settings.llm_embedding_model)
    url = f"{GEMINI_API_ROOT}/models/{model}:batchEmbedContents"
    vectors: list[list[float]] = []
    total_batches = math.ceil(len(texts) / _GEMINI_BATCH)
    async with httpx.AsyncClient(timeout=settings.llm_timeout_seconds) as client:
        for start in range(0, len(texts), _GEMINI_BATCH):
            batch = texts[start : start + _GEMINI_BATCH]
            batch_no = start // _GEMINI_BATCH + 1
            payload = {
                "requests": [
                    {
                        "model": f"models/{model}",
                        "content": {"parts": [{"text": item}]},
                        "taskType": task_type,
                        "outputDimensionality": EMBEDDING_DIM,
                    }
                    for item in batch
                ]
            }
            data = await _post_json_with_retry(
                client,
                url,
                gemini_headers(settings),
                payload,
                label=f"Gemini embeddings {batch_no}/{total_batches}",
            )
            for item in data["embeddings"]:
                vector = item["values"]
                if len(vector) != EMBEDDING_DIM:
                    vector = _fit_dim(vector, EMBEDDING_DIM)
                vectors.append(_l2_normalize(vector))
            if start + _GEMINI_BATCH < len(texts):
                await asyncio.sleep(0.25)
    return vectors


async def _openai_embed(texts: list[str]) -> list[list[float]]:
    settings = get_settings()
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {settings.llm_api_key}",
    }
    url = settings.llm_base_url.rstrip("/") + "/embeddings"
    vectors: list[list[float]] = []
    total_batches = math.ceil(len(texts) / _OPENAI_BATCH)
    async with httpx.AsyncClient(timeout=settings.llm_timeout_seconds) as client:
        for start in range(0, len(texts), _OPENAI_BATCH):
            batch = texts[start : start + _OPENAI_BATCH]
            batch_no = start // _OPENAI_BATCH + 1
            payload: dict = {"model": settings.llm_embedding_model, "input": batch}
            data = await _post_json_with_retry(
                client,
                url,
                headers,
                payload,
                label=f"OpenAI embeddings {batch_no}/{total_batches}",
            )
            rows = data["data"]
            rows.sort(key=lambda item: item["index"])
            for item in rows:
                vector = item["embedding"]
                if len(vector) != EMBEDDING_DIM:
                    vector = _fit_dim(vector, EMBEDDING_DIM)
                vectors.append(_l2_normalize(vector))
    return vectors


async def _post_json_with_retry(
    client: httpx.AsyncClient,
    url: str,
    headers: dict[str, str],
    payload: dict,
    *,
    label: str,
) -> dict:
    delay = 1.0
    for attempt in range(1, _MAX_ATTEMPTS + 1):
        response = await client.post(url, headers=headers, json=payload)
        if response.status_code < 400:
            return response.json()
        retryable = response.status_code in _RETRY_STATUSES
        snippet = response.text[:400]
        if not retryable or attempt == _MAX_ATTEMPTS:
            raise RuntimeError(f"{label} {response.status_code}: {snippet}")
        wait = delay + random.random() * 0.4
        logger.warning(
            "%s failed with %s (attempt %s/%s); retrying in %.1fs",
            label,
            response.status_code,
            attempt,
            _MAX_ATTEMPTS,
            wait,
        )
        await asyncio.sleep(wait)
        delay = min(delay * 2, 20.0)
    raise RuntimeError(f"{label} failed")


def _fit_dim(vector: list[float], dim: int) -> list[float]:
    if len(vector) == dim:
        return vector
    if len(vector) > dim:
        return vector[:dim]
    return vector + [0.0] * (dim - len(vector))


def cosine(left: list[float], right: list[float]) -> float:
    return float(sum(float(a) * float(b) for a, b in zip(left, right, strict=False)))
