import logging

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.v1.router import api_router
from app.core.config import get_settings
from app.services.auth import AuthError
from app.services.errors import DomainError

settings = get_settings()
logger = logging.getLogger("quizdock")

app = FastAPI(
    title=settings.app_name,
    version="0.1.0",
    docs_url="/api/docs",
    openapi_url="/api/openapi.json",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router, prefix="/api/v1")


@app.middleware("http")
async def disable_client_cache(request: Request, call_next):
    response = await call_next(request)
    response.headers["Cache-Control"] = "no-store"
    return response


@app.exception_handler(DomainError)
async def domain_error_handler(_request: Request, exc: DomainError) -> JSONResponse:
    return JSONResponse(status_code=exc.status_code, content={"detail": exc.message})


@app.exception_handler(AuthError)
async def auth_error_handler(_request: Request, exc: AuthError) -> JSONResponse:
    return JSONResponse(status_code=exc.status_code, content={"detail": exc.message})


@app.exception_handler(Exception)
async def unhandled_error_handler(_request: Request, exc: Exception) -> JSONResponse:
    if isinstance(exc, HTTPException):
        raise exc
    logger.exception("Unhandled API error")
    return JSONResponse(
        status_code=500,
        content={"detail": "El servidor no pudo completar la solicitud."},
    )


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok", "service": "quizdock-api"}
