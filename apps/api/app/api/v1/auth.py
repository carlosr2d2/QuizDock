from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_db
from app.models import User
from app.schemas.auth import AuthResponse, LoginRequest, RegisterRequest, UserRead
from app.services.auth import AuthError, AuthService

router = APIRouter(prefix="/auth", tags=["auth"])


def _auth_response(result) -> AuthResponse:
    return AuthResponse(
        access_token=result.access_token,
        user=UserRead.model_validate(result.user),
        organization_id=result.organization_id,
    )


@router.post("/register", response_model=AuthResponse, status_code=201)
async def register(payload: RegisterRequest, db: AsyncSession = Depends(get_db)) -> AuthResponse:
    service = AuthService(db)
    try:
        result = await service.register(
            payload.email, payload.password, payload.full_name, payload.invite_token
        )
    except AuthError as extra:
        raise HTTPException(status_code=extra.status_code, detail=extra.message) from extra
    return _auth_response(result)


@router.post("/login", response_model=AuthResponse)
async def login(payload: LoginRequest, db: AsyncSession = Depends(get_db)) -> AuthResponse:
    service = AuthService(db)
    try:
        result = await service.login(payload.email, payload.password, payload.invite_token)
    except AuthError as extra:
        raise HTTPException(status_code=extra.status_code, detail=extra.message) from extra
    return _auth_response(result)


@router.get("/me", response_model=UserRead)
async def me(user: User = Depends(get_current_user)) -> User:
    return user
