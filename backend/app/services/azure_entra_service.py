"""
Azure Entra ID authentication service.

This service handles OAuth2 authentication flow with Azure Entra ID,
including authorization URL generation, token exchange, validation,
refresh, and user profile retrieval.
"""

import hashlib
import json
import secrets
from datetime import datetime, timedelta
from typing import Dict, Optional, Tuple

from logconfig.logger import get_logger
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from app.core.azure_entra import (
    AzureEntraConfig,
    AzureEntraService,
    AzureTokenResponse,
    AzureUserProfile,
    TokenValidationResult,
    AzureEntraError,
    TokenExpiredError,
    InvalidTokenError,
)
from app.core.security import create_access_token, create_refresh_token
from app.core.settings import get_settings
from app.models.user import User, RefreshToken, UserRole
from app.schemas.token import Token
from app.schemas.user import User as UserSchema

logger = get_logger()
settings = get_settings()


class AzureEntraAuthService:
    """
    Service for handling Azure Entra ID authentication and user management.

    This service bridges the Azure Entra ID OAuth2 flow with the application's
    user management system, handling user creation, token management, and
    profile synchronization.
    """

    def __init__(self):
        """Initialize the Azure Entra authentication service."""
        self.azure_config = settings.get_azure_entra_config()
        self.azure_service = AzureEntraService(self.azure_config)

    async def create_or_update_user_from_azure(
        self,
        db: AsyncSession,
        azure_profile: AzureUserProfile,
        token_response: AzureTokenResponse,
    ) -> User:
        """
        Create or update user from Azure Entra profile.

        Args:
            db: Database session
            azure_profile: Azure Entra user profile
            token_response: Azure token response

        Returns:
            User object (created or updated)
        """
        logger.info(f"Creating/updating user from Azure profile: {azure_profile.email}")

        try:
            # Look for existing user by Azure Entra ID or email
            result = await db.execute(
                select(User).filter(
                    (User.azure_entra_id == azure_profile.id)
                    | (User.email == azure_profile.email)
                )
            )
            existing_user = result.scalars().first()

            if existing_user:
                # Update existing user
                logger.info(f"Updating existing user: {existing_user.id}")
                existing_user.azure_entra_id = azure_profile.id
                existing_user.email = azure_profile.email
                existing_user.full_name = azure_profile.full_name
                existing_user.profile_picture_url = azure_profile.picture
                existing_user.organization = azure_profile.company_name
                existing_user.department = azure_profile.department
                existing_user.azure_tenant_id = azure_profile.tenant_id
                existing_user.last_login = datetime.utcnow()

                # Update Azure tokens (hashed for security)
                existing_user.azure_access_token_hash = self._hash_token(
                    token_response.access_token
                )
                if token_response.refresh_token:
                    existing_user.azure_refresh_token_hash = self._hash_token(
                        token_response.refresh_token
                    )
                existing_user.azure_token_expires_at = datetime.utcnow() + timedelta(
                    seconds=token_response.expires_in
                )

                await db.commit()
                await db.refresh(existing_user)
                return existing_user
            else:
                # Create new user
                logger.info(
                    f"Creating new user from Azure profile: {azure_profile.email}"
                )
                new_user = User(
                    email=azure_profile.email,
                    full_name=azure_profile.full_name,
                    azure_entra_id=azure_profile.id,
                    azure_tenant_id=azure_profile.tenant_id,
                    profile_picture_url=azure_profile.picture,
                    organization=azure_profile.company_name,
                    department=azure_profile.department,
                    role=UserRole.USER,
                    is_active=True,
                    last_login=datetime.utcnow(),
                    azure_access_token_hash=self._hash_token(
                        token_response.access_token
                    ),
                    azure_refresh_token_hash=(
                        self._hash_token(token_response.refresh_token)
                        if token_response.refresh_token
                        else None
                    ),
                    azure_token_expires_at=datetime.utcnow()
                    + timedelta(seconds=token_response.expires_in),
                )

                db.add(new_user)
                await db.commit()
                await db.refresh(new_user)
                logger.info(f"Created new user: {new_user.id}")
                return new_user

        except Exception as e:
            logger.error(
                f"Error creating/updating user from Azure profile: {str(e)}",
                exc_info=True,
            )
            await db.rollback()
            raise

    async def create_tokens(
        self, db: AsyncSession, user: User
    ) -> Tuple[str, str, datetime]:
        """
        Create application access and refresh tokens for user.

        Args:
            db: Database session
            user: User object

        Returns:
            Tuple of (access_token, refresh_token, expires_at)
        """
        logger.info(f"Creating application tokens for user: {user.id}")

        try:
            # Create access token
            access_token_expires = timedelta(
                minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES
            )
            access_token = create_access_token(
                subject=str(user.id),
                expires_delta=access_token_expires,
                data={
                    "role": user.role.value,
                    "email": user.email,
                },
            )

            # Create refresh token
            refresh_token = create_refresh_token(
                subject=str(user.id),
                expires_delta_days=settings.REFRESH_TOKEN_EXPIRE_DAYS,
            )

            # Store refresh token in database
            db_refresh_token = RefreshToken(
                token=refresh_token,
                user_id=user.id,
                expires_at=datetime.utcnow() + refresh_token_expires,
            )
            db.add(db_refresh_token)
            await db.commit()

            logger.info(f"Application tokens created for user: {user.id}")
            return access_token, refresh_token, datetime.utcnow() + access_token_expires

        except Exception as e:
            logger.error(
                f"Error creating tokens for user {user.id}: {str(e)}", exc_info=True
            )
            await db.rollback()
            raise

    async def refresh_azure_token(
        self, db: AsyncSession, refresh_token: str
    ) -> Optional[Token]:
        """
        Refresh application access token using refresh token.

        Args:
            db: Database session
            refresh_token: Application refresh token

        Returns:
            New Token object or None if refresh failed
        """
        logger.info("Refreshing application access token")

        try:
            # Verify the refresh token
            from app.core.security import verify_token

            token_data = verify_token(refresh_token)
            if not token_data:
                logger.warning("Invalid refresh token provided")
                return None

            # Check if token exists in database and is not expired
            result = await db.execute(
                select(RefreshToken)
                .filter(RefreshToken.token == refresh_token)
                .filter(RefreshToken.revoked == False)
                .filter(RefreshToken.expires_at > datetime.utcnow())
            )
            db_token = result.scalars().first()
            if not db_token:
                logger.warning("Refresh token not found or expired")
                return None

            # Get user
            result = await db.execute(select(User).filter(User.id == db_token.user_id))
            user = result.scalars().first()
            if not user or not user.is_active:
                logger.warning(f"User {db_token.user_id} not found or inactive")
                return None

            # Try to refresh Azure token if it's close to expiring
            if user.azure_refresh_token_hash and user.azure_token_expires_at:
                time_until_expiry = user.azure_token_expires_at - datetime.utcnow()
                if time_until_expiry < timedelta(
                    minutes=5
                ):  # Refresh if less than 5 minutes left
                    logger.info("Azure token close to expiry, attempting refresh")
                    try:
                        # Note: We can't directly use the hashed token, so this is a limitation
                        # In a real implementation, you might want to store encrypted tokens instead
                        # For now, we'll just create a new application token
                        pass
                    except Exception as azure_error:
                        logger.warning(
                            f"Failed to refresh Azure token: {str(azure_error)}"
                        )

            # Create new application access token
            access_token_expires = timedelta(
                minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES
            )
            access_token = create_access_token(
                subject=str(user.id),
                expires_delta=access_token_expires,
                data={
                    "role": user.role.value,
                    "email": user.email,
                },
            )

            logger.info(f"Application access token refreshed for user: {user.id}")
            return Token(
                access_token=access_token,
                token_type="bearer",
                expires_at=datetime.utcnow() + access_token_expires,
            )

        except Exception as e:
            logger.error(f"Error refreshing token: {str(e)}", exc_info=True)
            raise

    async def sync_user_profile_from_azure(
        self, db: AsyncSession, user: User
    ) -> Optional[User]:
        """
        Sync user profile from Azure Entra ID.

        Args:
            db: Database session
            user: User object to sync

        Returns:
            Updated User object or None if sync failed
        """
        logger.info(f"Syncing user profile from Azure for user: {user.id}")

        try:
            # Check if we have a valid Azure token
            if not user.azure_access_token_hash or not user.azure_token_expires_at:
                logger.warning(f"No Azure token available for user: {user.id}")
                return None

            # Check if token is expired
            if user.azure_token_expires_at <= datetime.utcnow():
                logger.warning(f"Azure token expired for user: {user.id}")
                return None

            # Note: Since we store hashed tokens, we can't directly use them for API calls
            # In a production system, you would store encrypted tokens that can be decrypted
            # For now, we'll return the current user without syncing
            logger.warning(
                "Cannot sync profile - tokens are hashed and cannot be used for API calls"
            )
            return user

        except Exception as e:
            logger.error(
                f"Error syncing user profile for user {user.id}: {str(e)}",
                exc_info=True,
            )
            return None

    async def logout_azure_user(
        self, db: AsyncSession, user: User, refresh_token: str
    ) -> bool:
        """
        Log out user and revoke tokens.

        Args:
            db: Database session
            user: User object
            refresh_token: Refresh token to revoke

        Returns:
            True if logout was successful
        """
        logger.info(f"Logging out Azure user: {user.id}")

        try:
            # Revoke the application refresh token
            result = await db.execute(
                select(RefreshToken)
                .filter(RefreshToken.token == refresh_token)
                .filter(RefreshToken.user_id == user.id)
                .filter(RefreshToken.revoked == False)
            )
            db_token = result.scalars().first()

            if db_token:
                db_token.revoked = True
                db_token.revoked_at = datetime.utcnow()

            # Clear Azure token information
            user.azure_access_token_hash = None
            user.azure_refresh_token_hash = None
            user.azure_token_expires_at = None

            await db.commit()
            logger.info(f"Successfully logged out user: {user.id}")
            return True

        except Exception as e:
            logger.error(
                f"Error during logout for user {user.id}: {str(e)}", exc_info=True
            )
            await db.rollback()
            return False

    async def logout_all_azure_sessions(self, db: AsyncSession, user: User) -> None:
        """
        Log out user from all sessions and revoke all tokens.

        Args:
            db: Database session
            user: User object
        """
        logger.info(f"Logging out all Azure sessions for user: {user.id}")

        try:
            # Revoke all refresh tokens for the user
            result = await db.execute(
                select(RefreshToken)
                .filter(RefreshToken.user_id == user.id)
                .filter(RefreshToken.revoked == False)
            )
            active_tokens = result.scalars().all()

            token_count = len(active_tokens)
            if token_count > 0:
                for token in active_tokens:
                    token.revoked = True
                    token.revoked_at = datetime.utcnow()

            # Clear Azure token information
            user.azure_access_token_hash = None
            user.azure_refresh_token_hash = None
            user.azure_token_expires_at = None

            await db.commit()
            logger.info(f"Revoked {token_count} active sessions for user: {user.id}")

        except Exception as e:
            logger.error(
                f"Error logging out all sessions for user {user.id}: {str(e)}",
                exc_info=True,
            )
            await db.rollback()
            raise

    def _hash_token(self, token: str) -> str:
        """
        Hash a token for secure storage.

        Args:
            token: Token to hash

        Returns:
            Hashed token string
        """
        if not token:
            return ""
        return hashlib.sha256(token.encode()).hexdigest()
