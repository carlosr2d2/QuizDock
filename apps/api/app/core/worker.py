from collections.abc import Awaitable, Callable
from typing import TypeVar

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.config import get_settings

T = TypeVar("T")


def run_worker_job(handler: Callable[[AsyncSession], Awaitable[T | None]]) -> T | None:
    """Run an async job on a fresh engine/loop. Celery prefork cannot reuse the API engine."""

    async def _runner() -> T | None:
        engine = create_async_engine(get_settings().database_url, echo=False, pool_pre_ping=True)
        factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
        try:
            async with factory() as session:
                return await handler(session)
        finally:
            await engine.dispose()

    import asyncio

    return asyncio.run(_runner())
