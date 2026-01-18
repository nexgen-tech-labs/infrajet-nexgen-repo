from datetime import timedelta
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordRequestForm
from logconfig.logger import get_logger, get_context_filter
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.db.session import get_db
from app.middleware.supabase_auth import get_current_user_id
from app.models.user import User
from app.schemas.token import Token
from app.schemas.user import UserCreate, UserInResponse, UserRegister
from app.services.auth import AuthService

# Initialize logger
logger = get_logger()
context_filter = get_context_filter()
router = APIRouter()
settings = get_settings()

@router.post("/register", response_model=UserInResponse, status_code=status.HTTP_201_CREATED)
async def register(
    request: Request,
    user_in: UserRegister,
    db: AsyncSession = Depends(get_db)
):
    """
    Register a new user.
    """
    # Set request context
    context_filter.set_context(
        request_id=request.headers.get("x-request-id", ""),
        user_email=user_in.email,
        path=request.url.path
    )
    
    logger.info(f"Registration attempt for email: {user_in.email}")
    
    # Check if passwords match
    if user_in.password != user_in.password_confirm:
        logger.warning("Passwords do not match during registration")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Passwords do not match",
        )
    
    try:
        # Create user
        user = await AuthService.create_user(
            db=db,
            user_in=UserCreate(
                email=user_in.email,
                password=user_in.password,
                full_name=user_in.full_name,
            ),
        )
        logger.info(f"User registered successfully: {user_in.email}")
        
        # Generate tokens
        access_token, refresh_token, expires_at = await AuthService.create_tokens(db, user)
        logger.debug("Access and refresh tokens generated")
        
        return UserInResponse(
            user=user,
            token=access_token,
            refresh_token=refresh_token,
        )
    except Exception as e:
        logger.error(f"Error during user registration: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Could not register user. Please try again."
        )

@router.post("/login", response_model=UserInResponse)
async def login(
    request: Request,
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: AsyncSession = Depends(get_db),
):
    """
    OAuth2 compatible token login, get an access token for future requests
    """
    # Set request context
    context_filter.set_context(
        request_id=request.headers.get("x-request-id", ""),
        user_email=form_data.username,
        path=request.url.path
    )
    
    logger.info(f"Login attempt for email: {form_data.username}")
    
    try:
        user = await AuthService.login(
            db=db,
            email=form_data.username,
            password=form_data.password,
        )
        
        if not user:
            logger.warning(f"Failed login attempt for email: {form_data.username}")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Incorrect email or password",
            )
        
        logger.info(f"User logged in successfully: {form_data.username}")
        return user
        
    except Exception as e:
        logger.error(f"Error during login: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred during login"
        )

@router.post("/refresh", response_model=Token)
async def refresh_token(
    request: Request,
    refresh_token: str,
    db: AsyncSession = Depends(get_db),
):
    """
    Refresh access token using refresh token
    """
    # Set request context
    context_filter.set_context(
        request_id=request.headers.get("x-request-id", ""),
        path=request.url.path
    )
    
    logger.info("Token refresh attempt")
    
    try:
        token = await AuthService.refresh_token(db, refresh_token)
        if not token:
            logger.warning("Invalid refresh token provided")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid refresh token",
            )
        logger.info("Token refreshed successfully")
        return token
    except Exception as e:
        logger.error(f"Error refreshing token: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Could not refresh token"
        )

@router.post("/logout")
async def logout(
    request: Request,
    refresh_token: str,
    db: AsyncSession = Depends(get_db),
):
    """
    Log out by invalidating the refresh token
    """
    # Set request context
    context_filter.set_context(
        request_id=request.headers.get("x-request-id", ""),
        path=request.url.path
    )
    
    logger.info("Logout attempt")
    
    try:
        success = await AuthService.logout(db, refresh_token)
        if not success:
            logger.warning("Invalid refresh token provided for logout")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid refresh token",
            )
        logger.info("User logged out successfully")
        return {"detail": "Successfully logged out"}
    except Exception as e:
        logger.error(f"Error during logout: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Could not complete logout"
        )

@router.post("/logout/all")
async def logout_all(
    request: Request,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Log out from all devices by invalidating all refresh tokens for the current user
    """
    # Set request context
    context_filter.set_context(
        request_id=request.headers.get("x-request-id", ""),
        user_id=current_user.id,
        path=request.url.path
    )
    
    logger.info(f"Logout all sessions for user: {current_user.id}")
    
    try:
        await AuthService.logout_all_sessions(db, current_user.id)
        logger.info(f"Successfully logged out user {current_user.id} from all devices")
        return {"detail": "Successfully logged out from all devices"}
    except Exception as e:
        logger.error(f"Error during logout all: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Could not complete logout from all devices"
        )
