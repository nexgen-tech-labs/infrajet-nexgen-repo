from fastapi import APIRouter, Depends, HTTPException, Request, status, Body
from logconfig.logger import get_logger, get_context_filter
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.db.session import get_db
from app.dependencies.auth import get_current_user_id
from app.models.user import User
from app.schemas.token import Token
from app.schemas.user import UserInResponse
from app.services.auth import AuthService

# Initialize logger
logger = get_logger()
context_filter = get_context_filter()
router = APIRouter()
settings = get_settings()

@router.post("/login", response_model=UserInResponse)
async def login(
    request: Request,
    id_token: str = Body(..., embed=True),
    db: AsyncSession = Depends(get_db),
):
    """
    Firebase token login, get an access token for future requests
    """
    context_filter.set_context(
        request_id=request.headers.get("x-request-id", ""),
        path=request.url.path
    )
    
    logger.info(f"Login attempt with Firebase ID token")
    
    try:
        user_in_response = await AuthService.login(db=db, id_token=id_token)
        
        if not user_in_response:
            logger.warning(f"Failed login attempt with Firebase ID token")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid Firebase ID token",
            )
        
        logger.info(f"User logged in successfully")
        return user_in_response
        
    except Exception as e:
        logger.error(f"Error during login: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred during login"
        )

@router.post("/refresh", response_model=Token)
async def refresh_token(
    request: Request,
    refresh_token: str = Body(..., embed=True),
    db: AsyncSession = Depends(get_db),
):
    """
    Refresh access token using refresh token
    """
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
    refresh_token: str = Body(..., embed=True),
    db: AsyncSession = Depends(get_db),
):
    """
    Log out by invalidating the refresh token
    """
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
    current_user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    """
    Log out from all devices by invalidating all refresh tokens for the current user
    """
    context_filter.set_context(
        request_id=request.headers.get("x-request-id", ""),
        user_id=current_user_id,
        path=request.url.path
    )
    
    logger.info(f"Logout all sessions for user: {current_user_id}")
    
    try:
        await AuthService.logout_all_sessions(db, current_user_id)
        logger.info(f"Successfully logged out user {current_user_id} from all devices")
        return {"detail": "Successfully logged out from all devices"}
    except Exception as e:
        logger.error(f"Error during logout all: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Could not complete logout from all devices"
        )
