from datetime import datetime, timedelta
from typing import Optional, Tuple

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from firebase_admin import auth, credentials
import firebase_admin
from logconfig.logger import get_logger, get_context_filter

from app.core.config import get_settings
from app.core.security import create_access_token, create_refresh_token
from app.models.user import User, RefreshToken, UserRole
from app.schemas.user import UserCreate, User as UserSchema, UserInResponse
from app.schemas.token import Token, RefreshTokenCreate, RefreshTokenResponse

# Initialize logger
logger = get_logger()
context_filter = get_context_filter()
settings = get_settings()

# Initialize Firebase Admin SDK
if settings.FIREBASE_AUTH_ENABLED:
    try:
        cred = credentials.ApplicationDefault()
        firebase_admin.initialize_app(cred, {
            'projectId': settings.FIREBASE_PROJECT_ID,
        })
        logger.info("Firebase Admin SDK initialized successfully.")
    except Exception as e:
        logger.error(f"Error initializing Firebase Admin SDK: {e}", exc_info=True)

class AuthService:
    @classmethod
    async def get_user_by_email(cls, db: AsyncSession, email: str) -> Optional[User]:
        logger.debug(f"Looking up user by email: {email}")
        try:
            result = await db.execute(select(User).filter(User.email == email))
            user = result.scalars().first()
            if not user:
                logger.debug(f"User not found with email: {email}")
            return user
        except Exception as e:
            logger.error(f"Error looking up user by email {email}: {str(e)}", exc_info=True)
            raise

    @classmethod
    async def authenticate_user(cls, db: AsyncSession, id_token: str) -> Optional[User]:
        if not settings.FIREBASE_AUTH_ENABLED:
            logger.warning("Firebase authentication is disabled.")
            return None
        
        logger.info(f"Authentication attempt with Firebase ID token.")
        try:
            decoded_token = auth.verify_id_token(id_token)
            firebase_uid = decoded_token['uid']
            email = decoded_token.get('email')

            if not email:
                logger.error("Email not found in Firebase token.")
                return None

            user = await cls.get_user_by_email(db, email)

            if not user:
                logger.info(f"User with email {email} not found in DB. Creating new user.")
                user_in = UserCreate(email=email, password="") # Password not needed for Firebase auth
                user = await cls.create_user(db, user_in, firebase_uid)

            if not user.is_active:
                logger.warning(f"Authentication failed: User {email} is inactive")
                return None

            logger.info(f"User authenticated successfully: {email}")
            return user

        except auth.InvalidIdTokenError:
            logger.error("Invalid Firebase ID token.")
            return None
        except Exception as e:
            logger.error(f"Error during Firebase authentication: {str(e)}", exc_info=True)
            raise

    @classmethod
    async def create_user(cls, db: AsyncSession, user_in: UserCreate, firebase_uid: str) -> User:
        logger.info(f"Creating new user: {user_in.email}")
        try:
            existing_user = await cls.get_user_by_email(db, user_in.email)
            if existing_user:
                raise ValueError("User with this email already exists")

            db_user = User(
                id=firebase_uid, # Use firebase uid as primary key
                email=user_in.email,
                full_name=user_in.full_name,
                role=UserRole.USER,
                is_active=True,
            )
            db.add(db_user)
            await db.commit()
            await db.refresh(db_user)
            logger.info(f"User created successfully: {db_user.email} (ID: {db_user.id})")
            return db_user
        except Exception as e:
            logger.error(f"Error creating user {user_in.email}: {str(e)}", exc_info=True)
            await db.rollback()
            raise

    @classmethod
    async def create_tokens(
        cls, db: AsyncSession, user: User
    ) -> Tuple[str, str, datetime]:
        logger.info(f"Creating tokens for user: {user.email} (ID: {user.id})")
        try:
            access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
            access_token = create_access_token(
                data={"sub": str(user.id), "role": user.role.value},
                expires_delta=access_token_expires,
            )

            refresh_token_expires = timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)
            refresh_token = create_refresh_token(
                data={"sub": str(user.id)},
                expires_delta=refresh_token_expires,
            )

            db_refresh_token = RefreshToken(
                token=refresh_token,
                user_id=user.id,
                expires_at=datetime.utcnow() + refresh_token_expires,
            )
            db.add(db_refresh_token)
            await db.commit()

            logger.debug(f"Tokens created for user {user.id}")
            return access_token, refresh_token, datetime.utcnow() + access_token_expires

        except Exception as e:
            logger.error(f"Error creating tokens for user {user.id}: {str(e)}", exc_info=True)
            await db.rollback()
            raise

    @classmethod
    async def login(
        cls, db: AsyncSession, id_token: str
    ) -> Optional[UserInResponse]:
        user = await cls.authenticate_user(db, id_token)
        if not user:
            return None

        user.last_login = datetime.utcnow()
        await db.commit()

        access_token, refresh_token, expires_at = await cls.create_tokens(db, user)

        user_schema = UserSchema.from_orm(user)

        return UserInResponse(
            user=user_schema,
            token=access_token,
            refresh_token=refresh_token,
        )

    @classmethod
    async def refresh_token(
        cls, db: AsyncSession, token: str
    ) -> Optional[Token]:
        logger.debug("Refreshing access token")
        try:
            from app.core.security import verify_token
            token_data = verify_token(token)
            if not token_data:
                logger.warning("Invalid refresh token provided")
                return None

            result = await db.execute(
                select(RefreshToken)
                .filter(RefreshToken.token == token)
                .filter(RefreshToken.revoked == False)
                .filter(RefreshToken.expires_at > datetime.utcnow())
            )
            db_token = result.scalars().first()
            if not db_token:
                logger.warning("Refresh token not found or expired")
                return None

            result = await db.execute(select(User).filter(User.id == db_token.user_id))
            user = result.scalars().first()
            if not user or not user.is_active:
                logger.warning(f"User {db_token.user_id} not found or inactive")
                return None

            access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
            access_token = create_access_token(
                data={"sub": str(user.id), "role": user.role.value},
                expires_delta=access_token_expires,
            )

            logger.info(f"Access token refreshed for user: {user.email} (ID: {user.id})")
            return Token(
                access_token=access_token,
                token_type="bearer",
                expires_at=datetime.utcnow() + access_token_expires,
            )

        except Exception as e:
            logger.error(f"Error refreshing token: {str(e)}", exc_info=True)
            raise

    @classmethod
    async def logout(cls, db: AsyncSession, token: str) -> bool:
        logger.debug("Processing logout request")
        try:
            result = await db.execute(
                select(RefreshToken)
                .filter(RefreshToken.token == token)
                .filter(RefreshToken.revoked == False)
            )
            db_token = result.scalars().first()
            if not db_token:
                logger.warning("Invalid or already revoked refresh token provided for logout")
                return False

            db_token.revoked = True
            db_token.revoked_at = datetime.utcnow()
            await db.commit()

            logger.info(f"User logged out (token ID: {db_token.id}, user ID: {db_token.user_id})")
            return True

        except Exception as e:
            logger.error(f"Error during logout: {str(e)}", exc_info=True)
            await db.rollback()
            raise

    @classmethod
    async def logout_all_sessions(cls, db: AsyncSession, user_id: int) -> None:
        logger.info(f"Logging out all sessions for user ID: {user_id}")
        try:
            result = await db.execute(
                select(RefreshToken)
                .filter(RefreshToken.user_id == user_id)
                .filter(RefreshToken.revoked == False)
            )
            active_tokens = result.scalars().all()

            token_count = len(active_tokens)
            if token_count > 0:
                for token in active_tokens:
                    token.revoked = True
                    token.revoked_at = datetime.utcnow()

                await db.commit()
                logger.info(f"Revoked {token_count} active sessions for user ID: {user_id}")
            else:
                logger.info(f"No active sessions found for user ID: {user_id}")

        except Exception as e:
            logger.error(f"Error logging out all sessions for user {user_id}: {str(e)}", exc_info=True)
            await db.rollback()
            raise
