from datetime import datetime, timedelta, timezone
from typing import Any
from uuid import UUID

from jose import JWTError, jwt
from passlib.context import CryptContext

from app.core.config import get_settings

settings = get_settings()
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
ALGORITHM = "HS256"


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(plain: str, hashed: str) -> bool:
    return pwd_context.verify(plain, hashed)


def create_access_token(subject: UUID, extra: dict[str, Any] | None = None) -> str:
    expire = datetime.now(timezone.utc) + timedelta(minutes=settings.api_access_token_expire_minutes)
    payload: dict[str, Any] = {"sub": str(subject), "exp": expire}
    if extra:
        payload.update(extra)
    return jwt.encode(payload, settings.api_secret_key, algorithm=ALGORITHM)


def decode_token(token: str) -> dict[str, Any]:
    try:
        return jwt.decode(token, settings.api_secret_key, algorithms=[ALGORITHM])
    except JWTError as exc:
        raise ValueError("Invalid token") from exc
