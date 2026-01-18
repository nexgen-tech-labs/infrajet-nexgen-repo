from fastapi import Request, HTTPException, status, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import jwt, JWTError
from typing import Optional
from sqlalchemy import select
from datetime import datetime, timedelta
import logging

from app.core.config import get_settings
# Disabled Azure Entra imports
# from app.core.azure_entra import (
#     AzureEntraService,
#     TokenValidationResult,
#     AzureEntraError,
#     TokenExpiredError,
#     InvalidTokenError,
# )
# from app.services.azure_entra_service import AzureEntraAuthService

from app.db.session import get_db
from app.models.user import User, UserRole


# Custom exception classes for authentication errors
class AuthenticationError(HTTPException):
    """Base authentication error."""

    def __init__(self, detail: str = "Authentication failed"):
        super().__init__(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=detail,
            headers={"WWW-Authenticate": "Bearer"},
        )


class TokenExpiredAuthError(AuthenticationError):
    """Token expired error."""

    def __init__(self, detail: str = "Token has expired"):
        super().__init__(detail=detail)


class InvalidTokenAuthError(AuthenticationError):
    """Invalid token error."""

    def __init__(self, detail: str = "Invalid token"):
        super().__init__(detail=detail)


class InactiveUserError(HTTPException):
    """Inactive user error."""

    def __init__(self, detail: str = "User account is inactive"):
        super().__init__(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=detail,
        )


logger = logging.getLogger(__name__)
settings = get_settings()


# DISABLED: Azure Entra JWT Bearer authentication
# This will be replaced with Supabase JWT authentication in a future task

# class AzureEntraJWTBearer(HTTPBearer):
#     """Enhanced JWT Bearer authentication with Azure Entra ID support."""
#     ... (implementation commented out)

# class JWTBearer(AzureEntraJWTBearer):
#     """Legacy JWT Bearer class - redirects to Azure Entra implementation."""
#     pass

# class AzureEntraAuthMiddleware:
#     """FastAPI middleware for Azure Entra authentication with automatic token refresh."""
#     ... (implementation commented out)

# Import Supabase authentication components
from app.middleware.supabase_auth import (
    SupabaseJWTBearer,
    SupabaseUser,
    get_current_user as get_supabase_user,
    get_current_user_optional as get_supabase_user_optional,
    get_current_user_id,
)
from app.exceptions.supabase_exceptions import (
    SupabaseAuthenticationError as SupabaseAuthError,
    SupabaseTokenInvalidError as SupabaseInvalidTokenError,
    SupabaseTokenExpiredError as SupabaseExpiredTokenError,
    SupabaseTokenMissingError as SupabaseMissingTokenError,
)

# Updated JWT Bearer class using Supabase authentication
class JWTBearer(SupabaseJWTBearer):
    """JWT Bearer class using Supabase authentication."""
    
    def __init__(self, auto_error: bool = True):
        super().__init__(auto_error=auto_error)


# Utility function to get user from request state
def get_user_from_request_state(request: Request) -> Optional[User]:
    """Get user from request state set by middleware."""
    return getattr(request.state, "user", None)


# Updated dependencies using Supabase authentication
async def get_current_user(supabase_user: SupabaseUser = Depends(get_supabase_user)) -> SupabaseUser:
    """Get current authenticated Supabase user."""
    if not supabase_user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return supabase_user


# Optional authentication dependency
async def get_current_user_optional(
    supabase_user: Optional[SupabaseUser] = Depends(get_supabase_user_optional),
) -> Optional[SupabaseUser]:
    """Get current authenticated Supabase user (optional)."""
    return supabase_user


# Dependency to get current active user (Supabase users are considered active by default)
async def get_current_active_user(
    current_user: SupabaseUser = Depends(get_current_user),
) -> SupabaseUser:
    # Supabase users are considered active by default
    # Additional checks can be added here if needed
    return current_user


# Note: Role-based access control dependencies are commented out
# as they depend on database User model which is not used with Supabase auth
# These can be re-implemented using Supabase user metadata if needed

# # Dependency to check if user is admin
# async def get_current_admin_user(
#     current_user: SupabaseUser = Depends(get_current_user),
# ) -> SupabaseUser:
#     # Role checking would need to be implemented using Supabase user metadata
#     # or app_metadata fields
#     user_role = current_user.metadata.get('app_metadata', {}).get('role')
#     if user_role not in ['admin', 'superuser']:
#         raise HTTPException(
#             status_code=status.HTTP_403_FORBIDDEN,
#             detail="The user doesn't have enough privileges",
#         )
#     return current_user


# # Dependency to check if user is superuser
# async def get_current_superuser(
#     current_user: SupabaseUser = Depends(get_current_user),
# ) -> SupabaseUser:
#     user_role = current_user.metadata.get('app_metadata', {}).get('role')
#     if user_role != 'superuser':
#         raise HTTPException(
#             status_code=status.HTTP_403_FORBIDDEN,
#             detail="The user doesn't have enough privileges",
#         )
#     return current_user
