"""
Supabase Client Service for User Validation.

This service provides user validation functionality using Supabase SERVICE_ROLE_KEY
to check user existence in the Supabase users table.
"""

import asyncio
import logging
from typing import Optional, Dict, Any, List
from datetime import datetime
import httpx
from dataclasses import dataclass

from app.core.settings import get_settings
from app.middleware.supabase_auth import SupabaseJWTValidator
from app.exceptions.supabase_exceptions import SupabaseAuthenticationError

logger = logging.getLogger(__name__)
settings = get_settings()


@dataclass
class SupabaseUserInfo:
    """Supabase user information from users table."""
    id: str
    email: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    email_confirmed_at: Optional[datetime] = None
    app_metadata: Dict[str, Any] = None
    user_metadata: Dict[str, Any] = None
    
    def __post_init__(self):
        if self.app_metadata is None:
            self.app_metadata = {}
        if self.user_metadata is None:
            self.user_metadata = {}


class SupabaseClientError(Exception):
    """Base exception for Supabase client operations."""
    pass


class SupabaseUserNotFoundError(SupabaseClientError):
    """Exception raised when user is not found in Supabase."""
    pass


class SupabaseConnectionError(SupabaseClientError):
    """Exception raised when connection to Supabase fails."""
    pass


class SupabaseClientService:
    """
    Service for interacting with Supabase using SERVICE_ROLE_KEY.
    
    This service provides read-only access to the Supabase users table
    for user validation purposes.
    """

    def __init__(self):
        """Initialize the Supabase client service."""
        self.supabase_url = settings.SUPABASE_URL
        self.service_role_key = settings.SUPABASE_SERVICE_ROLE_KEY
        self.anon_key = settings.SUPABASE_ANON_KEY
        
        # Validate configuration
        self._validate_configuration()
        
        # HTTP client for API requests
        self.http_client = httpx.AsyncClient(
            timeout=30.0,
            headers={
                "apikey": self.service_role_key,
                "Authorization": f"Bearer {self.service_role_key}",
                "Content-Type": "application/json",
                "Prefer": "return=minimal"
            }
        )
        
        # JWT validator for token extraction
        self.jwt_validator = SupabaseJWTValidator()

    def _validate_configuration(self) -> None:
        """
        Validate Supabase configuration.
        
        Raises:
            SupabaseClientError: If configuration is invalid
        """
        if not self.supabase_url:
            raise SupabaseClientError("SUPABASE_URL is required")
        
        if not self.service_role_key:
            raise SupabaseClientError("SUPABASE_SERVICE_ROLE_KEY is required")
        
        if not self.anon_key:
            raise SupabaseClientError("SUPABASE_ANON_KEY is required")

    async def validate_user_exists(self, user_id: str) -> bool:
        """
        Validate that a user exists in the Supabase users table.
        
        Args:
            user_id: Supabase user ID (UUID)
            
        Returns:
            bool: True if user exists, False otherwise
            
        Raises:
            SupabaseConnectionError: If connection to Supabase fails
            SupabaseClientError: If validation fails due to other errors
        """
        try:
            # Query the auth.users table using the REST API
            url = f"{self.supabase_url}/rest/v1/auth/users"
            params = {
                "id": f"eq.{user_id}",
                "select": "id"
            }
            
            response = await self.http_client.get(url, params=params)
            
            if response.status_code == 200:
                users = response.json()
                return len(users) > 0
            elif response.status_code == 401:
                logger.error("Unauthorized access to Supabase users table - check SERVICE_ROLE_KEY")
                raise SupabaseConnectionError("Unauthorized access to Supabase")
            elif response.status_code == 404:
                logger.warning(f"User {user_id} not found in Supabase users table")
                return False
            else:
                logger.error(f"Supabase API error: {response.status_code} - {response.text}")
                raise SupabaseConnectionError(f"Supabase API error: {response.status_code}")
                
        except httpx.RequestError as e:
            logger.error(f"Connection error to Supabase: {e}")
            raise SupabaseConnectionError(f"Connection error to Supabase: {e}")
        except Exception as e:
            logger.error(f"Unexpected error validating user {user_id}: {e}")
            raise SupabaseClientError(f"Unexpected error validating user: {e}")

    async def get_user_info(self, user_id: str) -> Optional[SupabaseUserInfo]:
        """
        Get user information from Supabase users table.
        
        Args:
            user_id: Supabase user ID (UUID)
            
        Returns:
            Optional[SupabaseUserInfo]: User information if found, None otherwise
            
        Raises:
            SupabaseConnectionError: If connection to Supabase fails
            SupabaseClientError: If operation fails due to other errors
        """
        try:
            # Query the auth.users table using the REST API
            url = f"{self.supabase_url}/rest/v1/auth/users"
            params = {
                "id": f"eq.{user_id}",
                "select": "id,email,created_at,updated_at,email_confirmed_at,raw_app_meta_data,raw_user_meta_data"
            }
            
            response = await self.http_client.get(url, params=params)
            
            if response.status_code == 200:
                users = response.json()
                if users:
                    user_data = users[0]
                    return SupabaseUserInfo(
                        id=user_data["id"],
                        email=user_data.get("email"),
                        created_at=datetime.fromisoformat(user_data["created_at"].replace("Z", "+00:00")) if user_data.get("created_at") else None,
                        updated_at=datetime.fromisoformat(user_data["updated_at"].replace("Z", "+00:00")) if user_data.get("updated_at") else None,
                        email_confirmed_at=datetime.fromisoformat(user_data["email_confirmed_at"].replace("Z", "+00:00")) if user_data.get("email_confirmed_at") else None,
                        app_metadata=user_data.get("raw_app_meta_data", {}),
                        user_metadata=user_data.get("raw_user_meta_data", {})
                    )
                return None
            elif response.status_code == 401:
                logger.error("Unauthorized access to Supabase users table - check SERVICE_ROLE_KEY")
                raise SupabaseConnectionError("Unauthorized access to Supabase")
            else:
                logger.error(f"Supabase API error: {response.status_code} - {response.text}")
                raise SupabaseConnectionError(f"Supabase API error: {response.status_code}")
                
        except httpx.RequestError as e:
            logger.error(f"Connection error to Supabase: {e}")
            raise SupabaseConnectionError(f"Connection error to Supabase: {e}")
        except Exception as e:
            logger.error(f"Unexpected error getting user info for {user_id}: {e}")
            raise SupabaseClientError(f"Unexpected error getting user info: {e}")

    async def extract_and_validate_user_from_token(self, authorization_header: str) -> str:
        """
        Extract user ID from JWT token and validate user exists in Supabase.
        
        Args:
            authorization_header: Authorization header value (e.g., "Bearer <token>")
            
        Returns:
            str: Validated user ID
            
        Raises:
            SupabaseAuthError: If token is invalid or user doesn't exist
            SupabaseConnectionError: If connection to Supabase fails
        """
        try:
            # Extract token from authorization header
            if not authorization_header or not authorization_header.startswith("Bearer "):
                raise SupabaseAuthenticationError("Invalid authorization header format")
            
            token = authorization_header.replace("Bearer ", "").strip()
            if not token:
                raise SupabaseAuthenticationError("Missing JWT token")
            
            # Extract user ID from token
            user_id = self.jwt_validator.extract_user_id(token)
            
            # Validate user exists in Supabase
            user_exists = await self.validate_user_exists(user_id)
            if not user_exists:
                raise SupabaseUserNotFoundError(f"User {user_id} not found in Supabase")
            
            logger.debug(f"Successfully validated user {user_id} from JWT token")
            return user_id
            
        except (SupabaseAuthenticationError, SupabaseUserNotFoundError):
            # Re-raise authentication and user not found errors
            raise
        except Exception as e:
            logger.error(f"Unexpected error extracting and validating user from token: {e}")
            raise SupabaseAuthenticationError("Failed to validate user from token")

    async def update_user_metadata(self, user_id: str, metadata: Dict[str, Any]) -> bool:
        """
        Update user metadata in Supabase.

        Args:
            user_id: Supabase user ID (UUID)
            metadata: Metadata to update (will be merged with existing metadata)

        Returns:
            bool: True if update was successful

        Raises:
            SupabaseConnectionError: If connection to Supabase fails
            SupabaseUserNotFoundError: If user doesn't exist
            SupabaseClientError: If update fails due to other errors
        """
        try:
            # First get current user metadata
            current_user = await self.get_user_info(user_id)
            if not current_user:
                raise SupabaseUserNotFoundError(f"User {user_id} not found in Supabase")

            # Merge existing metadata with new metadata
            updated_metadata = current_user.user_metadata.copy() if current_user.user_metadata else {}
            updated_metadata.update(metadata)

            # Update user metadata using admin API
            url = f"{self.supabase_url}/auth/v1/admin/users/{user_id}"
            payload = {
                "user_metadata": updated_metadata
            }

            response = await self.http_client.put(url, json=payload)

            if response.status_code == 200:
                logger.info(f"Successfully updated metadata for user {user_id}")
                return True
            elif response.status_code == 404:
                raise SupabaseUserNotFoundError(f"User {user_id} not found in Supabase")
            elif response.status_code == 401:
                logger.error("Unauthorized access to update Supabase user - check SERVICE_ROLE_KEY")
                raise SupabaseConnectionError("Unauthorized access to Supabase")
            else:
                logger.error(f"Supabase API error updating user metadata: {response.status_code} - {response.text}")
                raise SupabaseClientError(f"Failed to update user metadata: {response.status_code}")

        except httpx.RequestError as e:
            logger.error(f"Connection error to Supabase: {e}")
            raise SupabaseConnectionError(f"Connection error to Supabase: {e}")
        except (SupabaseUserNotFoundError, SupabaseConnectionError, SupabaseClientError):
            # Re-raise known exceptions
            raise
        except Exception as e:
            logger.error(f"Unexpected error updating user metadata for {user_id}: {e}")
            raise SupabaseClientError(f"Unexpected error updating user metadata: {e}")

    async def batch_validate_users(self, user_ids: List[str]) -> Dict[str, bool]:
        """
        Validate multiple users exist in Supabase users table.

        Args:
            user_ids: List of Supabase user IDs

        Returns:
            Dict[str, bool]: Mapping of user_id to existence status

        Raises:
            SupabaseConnectionError: If connection to Supabase fails
        """
        try:
            if not user_ids:
                return {}

            # Query multiple users at once
            user_ids_filter = ",".join(user_ids)
            url = f"{self.supabase_url}/rest/v1/auth/users"
            params = {
                "id": f"in.({user_ids_filter})",
                "select": "id"
            }

            response = await self.http_client.get(url, params=params)

            if response.status_code == 200:
                existing_users = response.json()
                existing_user_ids = {user["id"] for user in existing_users}

                # Create result mapping
                result = {}
                for user_id in user_ids:
                    result[user_id] = user_id in existing_user_ids

                return result
            elif response.status_code == 401:
                logger.error("Unauthorized access to Supabase users table - check SERVICE_ROLE_KEY")
                raise SupabaseConnectionError("Unauthorized access to Supabase")
            else:
                logger.error(f"Supabase API error: {response.status_code} - {response.text}")
                raise SupabaseConnectionError(f"Supabase API error: {response.status_code}")

        except httpx.RequestError as e:
            logger.error(f"Connection error to Supabase: {e}")
            raise SupabaseConnectionError(f"Connection error to Supabase: {e}")
        except Exception as e:
            logger.error(f"Unexpected error batch validating users: {e}")
            raise SupabaseClientError(f"Unexpected error batch validating users: {e}")

    async def close(self):
        """Close the HTTP client."""
        await self.http_client.aclose()

    async def __aenter__(self):
        """Async context manager entry."""
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        await self.close()


# Global instance for dependency injection
_supabase_client_service: Optional[SupabaseClientService] = None


def get_supabase_client_service() -> SupabaseClientService:
    """
    Get or create global Supabase client service instance.
    
    Returns:
        SupabaseClientService: Global service instance
    """
    global _supabase_client_service
    if _supabase_client_service is None:
        _supabase_client_service = SupabaseClientService()
    return _supabase_client_service


async def get_supabase_client_service_dependency() -> SupabaseClientService:
    """
    FastAPI dependency for Supabase client service.
    
    Returns:
        SupabaseClientService: Service instance
    """
    return get_supabase_client_service()