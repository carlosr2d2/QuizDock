import asyncio

import httpx

from app.core.config import get_settings
from app.core.llm_provider import GEMINI_API_ROOT, gemini_headers, gemini_model
from app.core.db import SessionLocal
from app.models.document import Document, DocumentStatus
from app.services.rag import RagService
from sqlalchemy import select


async def probe() -> None:
    settings = get_settings()
    marker = settings.llm_api_key[19:23] if len(settings.llm_api_key) > 23 else ""
    print(f"key_len={len(settings.llm_api_key)} marker={marker}")
    headers = gemini_headers(settings)
    model = gemini_model(settings.llm_model)
    async with httpx.AsyncClient(timeout=45.0) as client:
        response = await client.post(
            f"{GEMINI_API_ROOT}/models/{model}:generateContent",
            headers=headers,
            json={"contents": [{"parts": [{"text": "Responde solo la palabra ok"}]}]},
        )
        print(f"generate status={response.status_code}")
        if response.status_code >= 400:
            print(response.text[:400])
            raise SystemExit(1)
        text = response.json()["candidates"][0]["content"]["parts"][0]["text"]
        print(f"generate text={text[:80]!r}")


async def reindex() -> None:
    async with SessionLocal() as session:
        result = await session.execute(select(Document).where(Document.status == DocumentStatus.READY))
        documents = list(result.scalars().all())
        rag = RagService(session)
        if not documents:
            print("no ready documents")
            return
        for document in documents:
            count = await rag.index_document(document)
            print(f"indexed {document.filename} chunks={count}")


async def main() -> None:
    await probe()
    await reindex()


if __name__ == "__main__":
    asyncio.run(main())
