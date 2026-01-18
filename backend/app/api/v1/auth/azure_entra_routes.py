"""
Azure Entra ID authentication routes.

This module implements OAuth2 authentication flow with Azure Entra ID,
including login, callback, token refresh, user profile, and logout endpoints.
"""

import secrets
from datetime import datetime, timedelta
from typing import Optional
from urllib.parse import urlencode

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status, Query
from fastapi.responses import RedirectResponse
from logconfig.logger import get_logger, get_context_filter
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.azure_entra import (
    AzureEntraService,
    AzureEntraError,
    TokenExpiredError,
    InvalidTokenError,
    AuthorizationError,
)
from app.core.settings import get_settings
from app.core.security import create_access_token, create_refresh_token
from app.db.session import get_db
from app.middleware.supabase_auth import get_current_user_id
from app.models.user import User, RefreshToken, UserRole
from app.schemas.token import Token
from app.schemas.user import User as UserSchema, UserInResponse
from app.services.azure_entra_service import AzureEntraAuthService

# Initialize logger
logger = get_logger()
context_filter = get_context_filter()
router = APIRouter()
settings = get_settings()

# Initialize Azure Entra service
azure_entra_config = settings.get_azure_entra_config()
azure_entra_service = AzureEntraService(azure_entra_config)
azure_auth_service = AzureEntraAuthService()


@router.get("/azure/login")
async def azure_login(
    request: Request,
    redirect_url: Optional[str] = None,
):
    """
    Initiate Azure Entra ID OAuth2 authentication flow.
    
    This endpoint redirects the user to Azure Entra ID for authentication.
    After successful authentication, the user will be redirected back to the callback endpoint.
    
    Args:
        redirect_url: Optional URL to redirect to after successful authentication
        
    Returns:
        RedirectResponse to Azure Entra ID authorization endpoint
    """
    # Set request context
    context_filter.set_context(
        request_id=request.headers.get("x-request-id", ""),
        path=request.url.path
    )
    
    logger.info("Initiating Azure Entra ID authentication flow")
    
    try:
        # Generate state parameter for CSRF protection
        state = secrets.token_urlsafe(32)
        
        # Store state and redirect URL in session/cache (simplified for now)
        # In production, you might want to use Redis or database for state storage
        try:
            request.session["oauth_state"] = state
            if redirect_url:
                request.session["redirect_after_auth"] = redirect_url
        except Exception as session_error:
            logger.warning(f"Session storage failed: {str(session_error)}")
            # Continue without session storage - state validation will be skipped
        
        # Get authorization URL from Azure Entra service
        auth_url = await azure_entra_service.get_authorization_url(state=state)
        
        logger.info(f"Redirecting to Azure Entra ID authorization URL with state: {state}")
        return RedirectResponse(url=auth_url, status_code=status.HTTP_302_FOUND)
        
    except AzureEntraError as e:
        logger.error(f"Azure Entra authentication initiation failed: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Authentication service error: {str(e)}"
        )
    except Exception as e:
        logger.error(f"Unexpected error during Azure authentication initiation: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Authentication service temporarily unavailable"
        )


@router.get("/azure/callback")
async def azure_callback(
    request: Request,
    code: Optional[str] = Query(None),
    state: Optional[str] = Query(None),
    error: Optional[str] = Query(None),
    error_description: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db),
):
    """
    Handle Azure Entra ID OAuth2 callback.
    
    This endpoint processes the authorization code returned by Azure Entra ID
    and exchanges it for access and refresh tokens. It also creates or updates
    the user record in the database.
    
    Args:
        code: Authorization code from Azure Entra ID
        state: State parameter for CSRF validation
        error: Error code if authentication failed
        error_description: Human-readable error description
        
    Returns:
        UserInResponse with user data and tokens, or redirects to error page
    """
    # Set request context
    context_filter.set_context(
        request_id=request.headers.get("x-request-id", ""),
        path=request.url.path
    )
    
    logger.info(f"Processing Azure Entra ID callback with state: {state}")
    
    # Check for authentication errors
    if error:
        logger.warning(f"Azure Entra authentication error: {error} - {error_description}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Authentication failed: {error_description or error}"
        )
    
    # Validate required parameters
    if not code or not state:
        logger.warning("Missing required parameters in Azure callback")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Missing authorization code or state parameter"
        )
    
    try:
        # Validate state parameter for CSRF protection
        try:
            stored_state = request.session.get("oauth_state")
            if stored_state and stored_state != state:
                logger.warning(f"Invalid state parameter. Expected: {stored_state}, Got: {state}")
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Invalid state parameter. Possible CSRF attack."
                )
        except Exception as session_error:
            logger.warning(f"Session validation failed: {str(session_error)}")
            # Continue without state validation if session is not available
        
        # Exchange authorization code for tokens
        logger.info("Exchanging authorization code for tokens")
        token_response = await azure_entra_service.exchange_code_for_tokens(code, state)
        
        # Get user profile from Azure Entra
        logger.info("Retrieving user profile from Azure Entra")
        azure_profile = await azure_entra_service.get_user_profile(token_response.access_token)
        
        # Create or update user in database
        logger.info(f"Creating/updating user: {azure_profile.email}")
        user = await azure_auth_service.create_or_update_user_from_azure(
            db=db,
            azure_profile=azure_profile,
            token_response=token_response
        )
        
        # Generate application tokens
        logger.info(f"Generating application tokens for user: {user.id}")
        access_token, refresh_token, expires_at = await azure_auth_service.create_tokens(db, user)
        
        # Clean up session
        redirect_url = None
        try:
            request.session.pop("oauth_state", None)
            redirect_url = request.session.pop("redirect_after_auth", None)
        except Exception as session_error:
            logger.warning(f"Session cleanup failed: {str(session_error)}")
        
        # Convert user to schema
        user_schema = UserSchema.from_orm(user)
        
        response_data = UserInResponse(
            user=user_schema,
            token=access_token,
            refresh_token=refresh_token,
        )
        
        logger.info(f"Azure Entra authentication successful for user: {user.email}")
        
        # If there's a redirect URL, you might want to redirect there with tokens
        # For API usage, return the response directly
        if redirect_url:
            # In a real application, you might want to redirect with tokens in a secure way
            # For now, we'll just return the response
            pass
            
        return response_data
        
    except AuthorizationError as e:
        logger.error(f"Azure authorization error: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Authorization failed: {str(e)}"
        )
    except AzureEntraError as e:
        logger.error(f"Azure Entra service error: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Authentication service error: {str(e)}"
        )
    except Exception as e:
        logger.error(f"Unexpected error during Azure callback processing: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Authentication processing failed"
        )


@router.post("/azure/refresh", response_model=Token)
async def azure_refresh_token(
    request: Request,
    refresh_token: str,
    db: AsyncSession = Depends(get_db),
):
    """
    Refresh access token using Azure Entra refresh token.
    
    This endpoint refreshes both the Azure Entra access token and the application
    access token using the stored refresh token.
    
    Args:
        refresh_token: Valid refresh token
        
    Returns:
        Token with new access token and expiration
    """
    # Set request context
    context_filter.set_context(
        request_id=request.headers.get("x-request-id", ""),
        path=request.url.path
    )
    
    logger.info("Processing Azure Entra token refresh request")
    
    try:
        # Refresh tokens using Azure Entra service
        new_token = await azure_auth_service.refresh_azure_token(db, refresh_token)
        
        if not new_token:
            logger.warning("Invalid or expired refresh token provided")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid or expired refresh token"
            )
        
        logger.info("Azure Entra token refreshed successfully")
        return new_token
        
    except TokenExpiredError as e:
        logger.warning(f"Token expired during refresh: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Refresh token has expired. Please log in again."
        )
    except InvalidTokenError as e:
        logger.warning(f"Invalid token during refresh: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid refresh token. Please log in again."
        )
    except AzureEntraError as e:
        logger.error(f"Azure Entra error during token refresh: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Token refresh failed: {str(e)}"
        )
    except Exception as e:
        logger.error(f"Unexpected error during token refresh: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Token refresh service temporarily unavailable"
        )


@router.get("/azure/profile")
async def get_azure_profile(
    request: Request,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Get current user's Azure Entra profile information.
    
    This endpoint returns the user's profile information synchronized from
    Azure Entra ID, including any recent updates.
    
    Returns:
        User profile with Azure Entra information
    """
    # Set request context
    context_filter.set_context(
        request_id=request.headers.get("x-request-id", ""),
        user_id=current_user.id,
        path=request.url.path
    )
    
    logger.info(f"Retrieving Azure profile for user: {current_user.id}")
    
    try:
        # Get fresh profile from Azure Entra if we have a valid token
        updated_user = await azure_auth_service.sync_user_profile_from_azure(
            db=db,
            user=current_user
        )
        
        if updated_user:
            # Convert to schema and return updated profile
            user_schema = UserSchema.from_orm(updated_user)
            logger.info(f"Azure profile retrieved and updated for user: {current_user.id}")
            return user_schema
        else:
            # Return current user data if sync failed or token expired
            user_schema = UserSchema.from_orm(current_user)
            logger.info(f"Returning cached profile for user: {current_user.id}")
            return user_schema
            
    except Exception as e:
        logger.error(f"Error retrieving Azure profile for user {current_user.id}: {str(e)}", exc_info=True)
        # Return current user data as fallback
        user_schema = UserSchema.from_orm(current_user)
        return user_schema


@router.post("/azure/logout")
async def azure_logout(
    request: Request,
    refresh_token: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Log out user and revoke Azure Entra tokens.
    
    This endpoint logs out the user by revoking both the application refresh token
    and the Azure Entra tokens, ensuring complete session termination.
    
    Args:
        refresh_token: Refresh token to revoke
        
    Returns:
        Success message
    """
    # Set request context
    context_filter.set_context(
        request_id=request.headers.get("x-request-id", ""),
        user_id=current_user.id,
        path=request.url.path
    )
    
    logger.info(f"Processing Azure logout for user: {current_user.id}")
    
    try:
        # Revoke tokens using Azure auth service
        success = await azure_auth_service.logout_azure_user(
            db=db,
            user=current_user,
            refresh_token=refresh_token
        )
        
        if not success:
            logger.warning(f"Failed to revoke tokens for user: {current_user.id}")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Failed to revoke tokens. Session may already be expired."
            )
        
        logger.info(f"Azure logout successful for user: {current_user.id}")
        return {"detail": "Successfully logged out and revoked all tokens"}
        
    except Exception as e:
        logger.error(f"Error during Azure logout for user {current_user.id}: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Logout service temporarily unavailable"
        )


@router.post("/azure/logout/all")
async def azure_logout_all(
    request: Request,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Log out user from all devices and revoke all Azure Entra tokens.
    
    This endpoint logs out the user from all devices by revoking all refresh tokens
    and Azure Entra tokens associated with the user account.
    
    Returns:
        Success message
    """
    # Set request context
    context_filter.set_context(
        request_id=request.headers.get("x-request-id", ""),
        user_id=current_user.id,
        path=request.url.path
    )
    
    logger.info(f"Processing Azure logout all sessions for user: {current_user.id}")
    
    try:
        # Revoke all tokens for the user
        await azure_auth_service.logout_all_azure_sessions(db=db, user=current_user)
        
        logger.info(f"Azure logout all sessions successful for user: {current_user.id}")
        return {"detail": "Successfully logged out from all devices and revoked all tokens"}
        
    except Exception as e:
        logger.error(f"Error during Azure logout all for user {current_user.id}: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Logout service temporarily unavailable"
        )