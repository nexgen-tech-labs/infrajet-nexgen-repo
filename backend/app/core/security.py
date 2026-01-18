from datetime import datetime, timedelta
from typing import Any, Optional, Union

from fastapi import Request, HTTPException, status, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import jwt, JWTError
from passlib.context import CryptContext
from sqlalchemy import select
from logconfig.logger import get_logger, get_context_filter

from app.core.config import get_settings
from app.db.session import get_db
from app.models.user import User

# Initialize logger
logger = get_logger()
context_filter = get_context_filter()
settings = get_settings()
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def create_access_token(
    subject: Union[str, Any],
    expires_delta: Optional[timedelta] = None,
    data: Optional[dict] = None,
) -> str:
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(
            minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES
        )

    to_encode = {"exp": expire, "sub": str(subject), "type": "access"}

    # Add additional data if provided
    if data:
        to_encode.update(data)

    encoded_jwt = jwt.encode(
        to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM
    )
    return encoded_jwt


def create_refresh_token(
    subject: Union[str, Any], expires_delta_days: Optional[int] = None
) -> str:
    if expires_delta_days:
        expire = datetime.utcnow() + timedelta(days=expires_delta_days)
    else:
        expire = datetime.utcnow() + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)

    to_encode = {"exp": expire, "sub": str(subject), "type": "refresh"}
    encoded_jwt = jwt.encode(
        to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM
    )
    return encoded_jwt


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)


def get_password_hash(password: str) -> str:
    return pwd_context.hash(password)


def verify_token(token: str) -> dict:
    try:
        payload = jwt.decode(
            token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM]
        )
        return payload
    except jwt.JWTError:
        return None


def generate_password_reset_token(email: str) -> str:
    delta = timedelta(hours=settings.EMAIL_RESET_TOKEN_EXPIRE_HOURS)
    now = datetime.utcnow()
    expires = now + delta
    exp = expires.timestamp()
    encoded_jwt = jwt.encode(
        {"exp": exp, "nbf": now, "sub": email, "type": "password_reset"},
        settings.SECRET_KEY,
        algorithm=settings.ALGORITHM,
    )
    return encoded_jwt


def verify_password_reset_token(token: str) -> Optional[str]:
    try:
        decoded_token = jwt.decode(
            token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM]
        )
        if decoded_token.get("type") != "password_reset":
            return None
        return decoded_token["sub"]
    except jwt.JWTError:
        return None


class OptionalJWTBearer(HTTPBearer):
    def __init__(self):
        super().__init__(auto_error=False)

    async def __call__(self, request: Request) -> Optional[str]:
        credentials: Optional[HTTPAuthorizationCredentials] = await super().__call__(
            request
        )
        if not credentials:
            return None
        if credentials.scheme != "Bearer":
            return None
        return credentials.credentials


# Dependency to get current user (optional authentication)
async def get_current_user_optional(
    token: Optional[str] = Depends(OptionalJWTBearer()),
) -> Optional[User]:
    # TEMPORARY: Return dummy user for testing Azure File Share integration
    # TODO: Remove this and restore proper authentication once testing is complete

    # Create a dummy user object for testing
    # Note: This creates a User instance without database persistence
    dummy_user = User()
    dummy_user.id = 1
    dummy_user.email = "dummy@test.com"
    dummy_user.hashed_password = "dummy_hash"
    dummy_user.full_name = "Dummy Test User"
    dummy_user.is_active = True
    dummy_user.is_superuser = False
    return dummy_user

    # Original authentication code (commented out for testing)
    # if not token:
    #     return None

    # try:
    #     payload = jwt.decode(
    #         token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM]
    #     )
    #     user_id: str = payload.get("sub")
    #     if user_id is None:
    #         return None
    # except JWTError:
    #     return None

    # async for db in get_db():
    #     result = await db.execute(select(User).filter(User.id == int(user_id)))
    #     user = result.scalars().first()
    #     if user is None or not user.is_active:
    #         return None
    #     return user
