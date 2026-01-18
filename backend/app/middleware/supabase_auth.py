"""
Supabase JWT Authentication Middleware

This module provides JWT token validation and user extraction for Supabase authentication.
It replaces the previous Azure Entra ID authentication system.
"""

import logging
from typing import Optional, Dict, Any
from fastapi import HTTPException, status, Request, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import jwt, JWTError
import json
import base64
from datetime import datetime

from app.core.settings import get_settings
from app.exceptions.supabase_exceptions import (
    SupabaseError,
    SupabaseAuthenticationError,
    SupabaseTokenError,
    SupabaseTokenExpiredError,
    SupabaseTokenInvalidError,
    SupabaseTokenMissingError,
    SupabaseUserValidationError,
    SupabaseUserNotFoundError,
    SupabaseServiceError,
    SupabaseConnectionError,
    SupabaseConfigurationError,
)

logger = logging.getLogger(__name__)


class SupabaseUser:
    """Represents a Supabase user extracted from JWT token."""

    def __init__(self, user_id: str, email: Optional[str] = None, **kwargs):
        self.id = user_id
        self.email = email
        self.metadata = kwargs

    def __str__(self):
        return f"SupabaseUser(id={self.id}, email={self.email})"


class SupabaseJWTValidator:
    """Validates Supabase JWT tokens and extracts user information."""

    def __init__(self):
        self.settings = get_settings()
        self._validate_config()

    def _validate_config(self):
        """Validate that required Supabase configuration is present."""
        if not self.settings.SUPABASE_URL:
            raise ValueError("SUPABASE_URL is required for Supabase authentication")
        if not self.settings.SUPABASE_ANON_KEY:
            raise ValueError(
                "SUPABASE_ANON_KEY is required for Supabase authentication"
            )

    def _decode_token_payload(self, token: str) -> Dict[str, Any]:
        """
        Decode JWT token payload without verification for inspection.
        This is used to extract basic information before full validation.
        """
        try:
            # Split the token into parts
            parts = token.split(".")
            if len(parts) != 3:
                raise SupabaseTokenInvalidError("Token must have 3 parts")

            # Decode the payload (second part)
            payload_part = parts[1]
            # Add padding if needed
            padding = 4 - len(payload_part) % 4
            if padding != 4:
                payload_part += "=" * padding

            payload_bytes = base64.urlsafe_b64decode(payload_part)
            payload = json.loads(payload_bytes.decode("utf-8"))

            return payload
        except (ValueError, json.JSONDecodeError, UnicodeDecodeError) as e:
            logger.error(f"Failed to decode token payload: {e}")
            raise SupabaseTokenInvalidError("Failed to decode token payload")

    def validate_token(self, token: str) -> bool:
        """
        Validate Supabase JWT token.

        Args:
            token: The JWT token to validate

        Returns:
            bool: True if token is valid

        Raises:
            InvalidTokenError: If token is invalid or malformed
            ExpiredTokenError: If token has expired
        """
        try:
            # First, decode payload to check basic structure
            payload = self._decode_token_payload(token)

            # Check if token has expired
            if "exp" in payload:
                exp_timestamp = payload["exp"]
                current_timestamp = datetime.utcnow().timestamp()
                if current_timestamp > exp_timestamp:
                    raise SupabaseTokenExpiredError("Token has expired")

            # Check issuer (should be Supabase or Supabase auth URL)
            if "iss" in payload:
                issuer = payload["iss"]
                # Accept both "supabase" (for anon keys) and the full auth URL (for user tokens)
                valid_issuers = ["supabase", f"{self.settings.SUPABASE_URL}/auth/v1"]
                if issuer not in valid_issuers:
                    logger.warning(
                        f"Unexpected token issuer: {issuer}. Expected one of: {valid_issuers}"
                    )
                else:
                    logger.debug(f"Token issuer validated: {issuer}")

            # For now, we'll do basic validation without signature verification
            # In production, you might want to verify the signature using Supabase's public key
            # This would require fetching the public key from Supabase's JWKS endpoint

            return True

        except (SupabaseTokenExpiredError, SupabaseTokenInvalidError):
            # Re-raise our custom exceptions
            raise
        except Exception as e:
            logger.error(f"Token validation failed: {e}")
            raise SupabaseTokenInvalidError(f"Token validation failed: {str(e)}")

    def extract_user_id(self, token: str) -> str:
        """
        Extract user_id from Supabase JWT token.

        Args:
            token: The JWT token

        Returns:
            str: The user ID from the token

        Raises:
            InvalidTokenError: If user_id cannot be extracted
        """
        try:
            payload = self._decode_token_payload(token)

            # Supabase typically stores user ID in 'sub' claim
            user_id = payload.get("sub")
            if not user_id:
                raise SupabaseTokenInvalidError("No user ID found in token")

            return user_id

        except SupabaseTokenInvalidError:
            raise
        except Exception as e:
            logger.error(f"Failed to extract user_id: {e}")
            raise SupabaseTokenInvalidError("Failed to extract user ID from token")

    def extract_user_info(self, token: str) -> SupabaseUser:
        """
        Extract complete user information from Supabase JWT token.

        Args:
            token: The JWT token

        Returns:
            SupabaseUser: User information extracted from token

        Raises:
            InvalidTokenError: If user information cannot be extracted
        """
        try:
            # First validate the token
            self.validate_token(token)

            payload = self._decode_token_payload(token)

            # Extract user information
            user_id = payload.get("sub")
            if not user_id:
                raise SupabaseTokenInvalidError("No user ID found in token")

            email = payload.get("email")

            # Extract additional metadata
            user_metadata = payload.get("user_metadata", {})
            app_metadata = payload.get("app_metadata", {})

            return SupabaseUser(
                user_id=user_id,
                email=email,
                user_metadata=user_metadata,
                app_metadata=app_metadata,
                aud=payload.get("aud"),
                exp=payload.get("exp"),
                iat=payload.get("iat"),
            )

        except (SupabaseTokenInvalidError, SupabaseTokenExpiredError):
            raise
        except Exception as e:
            logger.error(f"Failed to extract user info: {e}")
            raise SupabaseTokenInvalidError(
                "Failed to extract user information from token"
            )

    async def validate_user_exists(self, user_id: str) -> bool:
        """
        Validate that a user exists in Supabase users table using SERVICE_ROLE_KEY.

        This method makes an API call to Supabase to verify the user exists using
        the SERVICE_ROLE_KEY for read-only access to the users table.

        Args:
            user_id: Supabase user ID to validate

        Returns:
            bool: True if user exists, False otherwise
        """
        try:
            if not user_id:
                return False

            # Check if we have SERVICE_ROLE_KEY configured
            if (
                not hasattr(self.settings, "SUPABASE_SERVICE_ROLE_KEY")
                or not self.settings.SUPABASE_SERVICE_ROLE_KEY
            ):
                logger.warning(
                    "SUPABASE_SERVICE_ROLE_KEY not configured, skipping user validation"
                )
                # If SERVICE_ROLE_KEY is not configured, assume user exists if we have a valid JWT
                return True

            # Import supabase client here to avoid circular imports
            try:
                from supabase import create_client
            except ImportError:
                logger.warning(
                    "Supabase client not available, skipping user validation"
                )
                return True

            # Create Supabase client with SERVICE_ROLE_KEY for admin access
            supabase_client = create_client(
                self.settings.SUPABASE_URL, self.settings.SUPABASE_SERVICE_ROLE_KEY
            )

            # Query users table to check if user exists
            response = (
                supabase_client.table("auth.users")
                .select("id")
                .eq("id", user_id)
                .execute()
            )

            user_exists = len(response.data) > 0

            if user_exists:
                logger.debug(
                    f"User {user_id} validated successfully in Supabase users table"
                )
            else:
                logger.warning(f"User {user_id} not found in Supabase users table")

            return user_exists

        except Exception as e:
            logger.error(f"Failed to validate user existence for {user_id}: {e}")
            # In case of error, assume user exists if we have a valid JWT token
            # This prevents authentication failures due to temporary Supabase issues
            return True


class SupabaseJWTBearer(HTTPBearer):
    """
    FastAPI dependency for Supabase JWT authentication.

    This class handles JWT token extraction from Authorization header
    and validates it using Supabase JWT validation.
    """

    def __init__(self, auto_error: bool = True):
        super().__init__(auto_error=auto_error)
        self.validator = SupabaseJWTValidator()

    async def __call__(self, request: Request) -> Optional[SupabaseUser]:
        """
        Extract and validate JWT token from request.

        Args:
            request: FastAPI request object

        Returns:
            SupabaseUser: Authenticated user information

        Raises:
            MissingTokenError: If no token is provided and auto_error is True
            InvalidTokenError: If token is invalid
            ExpiredTokenError: If token has expired
        """
        credentials: HTTPAuthorizationCredentials = await super().__call__(request)

        if not credentials:
            if self.auto_error:
                raise SupabaseTokenMissingError("Authorization token required")
            return None

        token = credentials.credentials
        if not token:
            if self.auto_error:
                raise SupabaseTokenMissingError("Authorization token required")
            return None

        try:
            # Extract user information from token
            user = self.validator.extract_user_info(token)

            # Store user in request state for later access
            request.state.user = user
            request.state.user_id = user.id

            logger.debug(f"Successfully authenticated user: {user.id}")
            return user

        except (
            SupabaseTokenInvalidError,
            SupabaseTokenExpiredError,
            SupabaseTokenMissingError,
        ):
            if self.auto_error:
                raise
            return None
        except Exception as e:
            logger.error(f"Unexpected authentication error: {e}")
            if self.auto_error:
                raise SupabaseAuthenticationError("Authentication failed")
            return None


# Global instance for dependency injection
supabase_jwt_bearer = SupabaseJWTBearer()
supabase_jwt_bearer_optional = SupabaseJWTBearer(auto_error=False)


# FastAPI Dependencies
async def get_current_user(
    user: SupabaseUser = Depends(supabase_jwt_bearer),
) -> SupabaseUser:
    """
    FastAPI dependency to get current authenticated user.

    Returns:
        SupabaseUser: Current authenticated user

    Raises:
        HTTPException: If user is not authenticated
    """
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return user


async def get_current_user_optional(
    user: Optional[SupabaseUser] = Depends(supabase_jwt_bearer_optional),
) -> Optional[SupabaseUser]:
    """
    FastAPI dependency to get current user (optional).

    Returns:
        Optional[SupabaseUser]: Current user if authenticated, None otherwise
    """
    return user


async def get_current_user_id(user: SupabaseUser = Depends(get_current_user)) -> str:
    """
    FastAPI dependency to get current user ID.

    Returns:
        str: Current user's ID
    """
    return user.id


async def get_current_user_id_optional(
    user: Optional[SupabaseUser] = Depends(get_current_user_optional),
) -> Optional[str]:
    """
    FastAPI dependency to get current user ID (optional).

    Returns:
        Optional[str]: Current user's ID if authenticated, None otherwise
    """
    return user.id if user else None


async def get_current_supabase_user(
    user: SupabaseUser = Depends(get_current_user),
) -> str:
    """
    FastAPI dependency to get current Supabase user ID.

    This is an alias for get_current_user_id for consistency with the project management service.

    Returns:
        str: Current user's Supabase ID
    """
    return user.id


def get_user_from_request_state(request: Request) -> Optional[SupabaseUser]:
    """
    Utility function to get user from request state.

    Args:
        request: FastAPI request object

    Returns:
        Optional[SupabaseUser]: User if stored in request state
    """
    return getattr(request.state, "user", None)


def get_user_id_from_request_state(request: Request) -> Optional[str]:
    """
    Utility function to get user ID from request state.

    Args:
        request: FastAPI request object

    Returns:
        Optional[str]: User ID if stored in request state
    """
    return getattr(request.state, "user_id", None)
