"""
Authentication dependencies for FastAPI endpoints.

This module provides authentication dependencies that work with Supabase JWT tokens
while integrating with the local Azure PostgreSQL database for GitHub connections.
"""

from typing import Optional
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.ext.asyncio import AsyncSession
import jwt
import httpx

from app.db.session import get_async_db
from app.core.settings import get_settings
from app.models.user import User
from logconfig.logger import get_logger

logger = get_logger()
settings = get_settings()
security = HTTPBearer()


class CurrentUser:
    """Simple user object for current user context."""
    
    def __init__(self, id: str, email: str, supabase_user_id: str):
        self.id = id
        self.supabase_user_id = supabase_user_id
        self.email = email


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: AsyncSession = Depends(get_async_db)
) -> CurrentUser:
    """
    Get current user from Supabase JWT token.
    
    This dependency extracts user information from the Supabase JWT token
    and creates a CurrentUser object for use in endpoints.
    """
    try:
        token = credentials.credentials
        
        # For development/testing, allow a simple mock token
        if token == "your-jwt-token-here" or token.startswith("mock-"):
            logger.warning("Using mock authentication token - for development only!")
            return CurrentUser(
                id="mock-user-id",
                email="test@example.com",
                supabase_user_id="mock-supabase-user-id"
            )
        
        # Decode JWT token without verification for now
        # In production, you should verify the token with Supabase
        try:
            # Decode without verification to extract user info
            decoded_token = jwt.decode(token, options={"verify_signature": False})
            
            user_id = decoded_token.get("sub")
            email = decoded_token.get("email")
            
            if not user_id:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Invalid token: missing user ID"
                )
            
            return CurrentUser(
                id=user_id,
                email=email or "unknown@example.com",
                supabase_user_id=user_id
            )
            
        except jwt.DecodeError:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token format"
            )
        
    except Exception as e:
        logger.error(f"Error getting current user: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials"
        )


async def get_current_user_with_supabase_validation(
    credentials: HTTPAuthorizationCredentials = Depends(security)
) -> CurrentUser:
    """
    Get current user with full Supabase token validation.
    
    This is a more secure version that validates the token with Supabase.
    Use this in production.
    """
    try:
        token = credentials.credentials
        
        # Validate token with Supabase
        async with httpx.AsyncClient() as client:
            headers = {
                "Authorization": f"Bearer {token}",
                "apikey": settings.SUPABASE_ANON_KEY
            }
            
            response = await client.get(
                f"{settings.SUPABASE_URL}/auth/v1/user",
                headers=headers
            )
            
            if response.status_code != 200:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Invalid or expired token"
                )
            
            user_data = response.json()
            
            return CurrentUser(
                id=user_data["id"],
                email=user_data.get("email", "unknown@example.com"),
                supabase_user_id=user_data["id"]
            )
            
    except httpx.RequestError:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Could not validate token with Supabase"
        )
    except Exception as e:
        logger.error(f"Error validating user with Supabase: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials"
        )


# Optional dependency for endpoints that don't require authentication
async def get_current_user_optional(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(HTTPBearer(auto_error=False))
) -> Optional[CurrentUser]:
    """
    Get current user optionally (for endpoints that work with or without auth).
    """
    if not credentials:
        return None
    
    try:
        return await get_current_user(credentials)
    except HTTPException:
        return None