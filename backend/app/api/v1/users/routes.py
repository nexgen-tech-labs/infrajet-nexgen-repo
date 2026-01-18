from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from logconfig.logger import get_logger, get_context_filter
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.middleware.auth import (
    get_current_active_user,
    get_current_admin_user,
    get_current_superuser,
)
from app.models.user import User, UserRole
from app.schemas.user import (
    User as UserSchema,
    UserCreate,
    UserList,
    UserUpdate,
    UserProfileComplete,
    UserPreferences,
    UserPreferencesUpdate,
    UserSession,
    ConnectedServices,
    SessionRevocationRequest,
    SessionRevocationResponse,
)
from app.services.auth import AuthService
from app.services.user_profile_service import UserProfileService

# Initialize logger
logger = get_logger()
context_filter = get_context_filter()
router = APIRouter()


@router.get("/me", response_model=UserSchema)
async def read_users_me(
    request: Request,
    current_user: User = Depends(get_current_active_user),
):
    """
    Get current user.
    """
    # Set request context
    context_filter.set_context(
        request_id=request.headers.get("x-request-id", ""),
        user_id=current_user.id,
        path=request.url.path,
    )

    logger.info(f"Fetching current user: {current_user.email}")
    return current_user


@router.put("/me", response_model=UserSchema)
async def update_user_me(
    request: Request,
    user_in: UserUpdate,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Update current user.
    """
    # Set request context
    context_filter.set_context(
        request_id=request.headers.get("x-request-id", ""),
        user_id=current_user.id,
        path=request.url.path,
    )

    logger.info(f"Updating user profile: {current_user.email}")

    try:
        update_data = user_in.dict(exclude_unset=True)
        logger.debug(f"Update data: {update_data}")

        # Update user fields
        if user_in.full_name is not None:
            current_user.full_name = user_in.full_name

        if user_in.email is not None and user_in.email != current_user.email:
            logger.info(f"Updating email from {current_user.email} to {user_in.email}")
            # Check if email is already taken
            existing_user = await AuthService.get_user_by_email(db, user_in.email)
            if existing_user and existing_user.id != current_user.id:
                logger.warning(f"Email {user_in.email} is already registered")
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Email already registered",
                )
            current_user.email = user_in.email

        # Update password if provided
        if user_in.password:
            logger.info("Updating user password")
            from app.core.security import get_password_hash

            current_user.hashed_password = get_password_hash(user_in.password)

        await db.commit()
        await db.refresh(current_user)
        logger.info(f"Successfully updated user: {current_user.email}")
        return current_user

    except Exception as e:
        logger.error(f"Error updating user profile: {str(e)}", exc_info=True)
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Could not update user profile",
        )


@router.get("/", response_model=List[UserSchema])
async def read_users(
    request: Request,
    skip: int = 0,
    limit: int = 100,
    current_user: User = Depends(get_current_admin_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Retrieve users (admin only).
    """
    # Set request context
    context_filter.set_context(
        request_id=request.headers.get("x-request-id", ""),
        user_id=current_user.id,
        path=request.url.path,
    )

    logger.info(
        f"Admin {current_user.email} fetching users list (skip={skip}, limit={limit})"
    )

    try:
        from sqlalchemy.future import select

        result = await db.execute(select(User).offset(skip).limit(limit))
        users = result.scalars().all()
        logger.info(f"Retrieved {len(users)} users")
        return users
    except Exception as e:
        logger.error(f"Error retrieving users: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Could not retrieve users",
        )


@router.get("/{user_id}", response_model=UserSchema)
async def read_user(
    request: Request,
    user_id: int,
    current_user: User = Depends(get_current_admin_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Get a specific user by ID (admin only).
    """
    # Set request context
    context_filter.set_context(
        request_id=request.headers.get("x-request-id", ""),
        user_id=current_user.id,
        path=request.url.path,
    )

    logger.info(f"Admin {current_user.email} fetching user with ID: {user_id}")

    try:
        from sqlalchemy.future import select

        result = await db.execute(select(User).filter(User.id == user_id))
        user = result.scalars().first()

        if not user:
            logger.warning(f"User with ID {user_id} not found")
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found",
            )

        logger.info(f"Successfully retrieved user: {user.email}")
        return user

    except Exception as e:
        logger.error(f"Error retrieving user {user_id}: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Could not retrieve user",
        )


@router.post("/", response_model=UserSchema, status_code=status.HTTP_201_CREATED)
async def create_user(
    request: Request,
    user_in: UserCreate,
    current_user: User = Depends(get_current_superuser),
    db: AsyncSession = Depends(get_db),
):
    """
    Create new user (superuser only).
    """
    # Set request context
    context_filter.set_context(
        request_id=request.headers.get("x-request-id", ""),
        user_id=current_user.id,
        path=request.url.path,
    )

    logger.info(f"Superuser {current_user.email} creating new user: {user_in.email}")

    try:
        # Check if user already exists
        existing_user = await AuthService.get_user_by_email(db, user_in.email)
        if existing_user:
            logger.warning(f"User with email {user_in.email} already exists")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="User with this email already exists",
            )

        user = await AuthService.create_user(db=db, user_in=user_in)
        logger.info(f"Successfully created user: {user.email}")
        return user

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating user: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Could not create user",
        )


@router.put("/{user_id}", response_model=UserSchema)
async def update_user(
    request: Request,
    user_id: int,
    user_in: UserUpdate,
    current_user: User = Depends(get_current_admin_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Update a user (admin only).
    """
    # Set request context
    context_filter.set_context(
        request_id=request.headers.get("x-request-id", ""),
        user_id=current_user.id,
        target_user_id=user_id,
        path=request.url.path,
    )

    logger.info(f"Admin {current_user.email} updating user with ID: {user_id}")

    try:
        from sqlalchemy.future import select

        result = await db.execute(select(User).filter(User.id == user_id))
        user = result.scalars().first()

        if not user:
            logger.warning(f"User with ID {user_id} not found")
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found",
            )

        # Only superuser can update other users' roles
        if user_in.role is not None and current_user.role != UserRole.SUPERUSER:
            logger.warning(
                f"Non-superuser {current_user.email} attempted to change role for user {user_id}"
            )
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Only superuser can change user roles",
            )

        update_data = user_in.dict(exclude_unset=True)
        logger.debug(f"Update data: {update_data}")

        # Track changes for logging
        changes = []

        # Update user fields
        if user_in.full_name is not None and user_in.full_name != user.full_name:
            changes.append(f"name: {user.full_name} -> {user_in.full_name}")
            user.full_name = user_in.full_name

        if user_in.email is not None and user_in.email != user.email:
            changes.append(f"email: {user.email} -> {user_in.email}")
            # Check if email is already taken
            existing_user = await AuthService.get_user_by_email(db, user_in.email)
            if existing_user and existing_user.id != user_id:
                logger.warning(f"Email {user_in.email} is already registered")
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Email already registered",
                )
            user.email = user_in.email

        if user_in.is_active is not None and user_in.is_active != user.is_active:
            status_change = "active" if user_in.is_active else "inactive"
            changes.append(f"status: {status_change}")
            user.is_active = user_in.is_active

        if user_in.role is not None and user_in.role != user.role:
            changes.append(f"role: {user.role} -> {user_in.role}")
            user.role = user_in.role

        if user_in.password:
            changes.append("password: [updated]")
            from app.core.security import get_password_hash

            user.hashed_password = get_password_hash(user_in.password)

        if changes:
            logger.info(f"Updating user {user_id}. Changes: {', '.join(changes)}")
            await db.commit()
            await db.refresh(user)
            logger.info(f"Successfully updated user {user_id}")
        else:
            logger.info("No changes detected in update request")

        return user

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating user {user_id}: {str(e)}", exc_info=True)
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Could not update user",
        )


@router.delete("/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_user(
    request: Request,
    user_id: int,
    current_user: User = Depends(get_current_superuser),
    db: AsyncSession = Depends(get_db),
):
    """
    Delete a user (superuser only).
    """
    # Set request context
    context_filter.set_context(
        request_id=request.headers.get("x-request-id", ""),
        user_id=current_user.id,
        target_user_id=user_id,
        path=request.url.path,
    )

    logger.info(f"Superuser {current_user.email} deleting user with ID: {user_id}")

    try:
        # Prevent self-deletion
        if current_user.id == user_id:
            logger.warning("Superuser attempted to delete themselves")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot delete yourself",
            )

        # Get the user to be deleted
        from sqlalchemy.future import select

        result = await db.execute(select(User).filter(User.id == user_id))
        user = result.scalars().first()

        if not user:
            logger.warning(f"User with ID {user_id} not found for deletion")
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found",
            )

        # Log the deletion
        logger.info(f"Deleting user: {user.email} (ID: {user.id})")

        # Delete the user
        await db.delete(user)
        await db.commit()

        logger.info(f"Successfully deleted user: {user.email}")
        return None

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting user {user_id}: {str(e)}", exc_info=True)
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Could not delete user",
        )


# Comprehensive User Profile Management Routes


@router.get("/me/profile", response_model=UserProfileComplete)
async def get_complete_user_profile(
    request: Request,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Get complete user profile with all related information.
    """
    # Set request context
    context_filter.set_context(
        request_id=request.headers.get("x-request-id", ""),
        user_id=current_user.id,
        path=request.url.path,
    )

    logger.info(f"Fetching complete profile for user: {current_user.email}")

    try:
        profile = await UserProfileService.get_complete_user_profile(
            db, current_user.id
        )
        if not profile:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="User profile not found"
            )

        logger.info(
            f"Successfully retrieved complete profile for user: {current_user.email}"
        )
        return profile

    except Exception as e:
        logger.error(f"Error fetching complete user profile: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Could not retrieve user profile",
        )


@router.get("/me/connected-services", response_model=ConnectedServices)
async def get_connected_services(
    request: Request,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Get connected services status for current user.
    """
    # Set request context
    context_filter.set_context(
        request_id=request.headers.get("x-request-id", ""),
        user_id=current_user.id,
        path=request.url.path,
    )

    logger.info(f"Fetching connected services for user: {current_user.email}")

    try:
        services = await UserProfileService.get_connected_services_status(
            db, current_user.id
        )
        logger.info(
            f"Successfully retrieved connected services for user: {current_user.email}"
        )
        return services

    except Exception as e:
        logger.error(f"Error fetching connected services: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Could not retrieve connected services",
        )


@router.get("/me/sessions", response_model=List[UserSession])
async def get_user_sessions(
    request: Request,
    include_inactive: bool = Query(False, description="Include inactive sessions"),
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Get user's WebSocket sessions.
    """
    # Set request context
    context_filter.set_context(
        request_id=request.headers.get("x-request-id", ""),
        user_id=current_user.id,
        path=request.url.path,
    )

    logger.info(
        f"Fetching sessions for user: {current_user.email} (include_inactive={include_inactive})"
    )

    try:
        sessions = await UserProfileService.get_user_sessions(
            db, current_user.id, include_inactive
        )
        logger.info(
            f"Successfully retrieved {len(sessions)} sessions for user: {current_user.email}"
        )
        return sessions

    except Exception as e:
        logger.error(f"Error fetching user sessions: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Could not retrieve user sessions",
        )


@router.post("/me/sessions/revoke", response_model=SessionRevocationResponse)
async def revoke_user_sessions(
    request: Request,
    revocation_request: SessionRevocationRequest,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Revoke user sessions for security management.
    """
    # Set request context
    context_filter.set_context(
        request_id=request.headers.get("x-request-id", ""),
        user_id=current_user.id,
        path=request.url.path,
    )

    logger.info(
        f"Revoking sessions for user: {current_user.email} (revoke_all={revocation_request.revoke_all})"
    )

    try:
        revoked_sessions, failed_sessions = (
            await UserProfileService.revoke_user_sessions(
                db,
                current_user.id,
                revocation_request.session_ids,
                revocation_request.revoke_all,
            )
        )

        total_revoked = len(revoked_sessions)
        message = f"Successfully revoked {total_revoked} session(s)"

        if failed_sessions:
            message += f", failed to revoke {len(failed_sessions)} session(s)"

        logger.info(
            f"Session revocation completed for user {current_user.email}: {message}"
        )

        return SessionRevocationResponse(
            revoked_sessions=revoked_sessions,
            failed_sessions=failed_sessions,
            total_revoked=total_revoked,
            message=message,
        )

    except Exception as e:
        logger.error(f"Error revoking user sessions: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Could not revoke user sessions",
        )


@router.post("/me/sessions/cleanup")
async def cleanup_stale_sessions(
    request: Request,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Clean up stale sessions for current user.
    """
    # Set request context
    context_filter.set_context(
        request_id=request.headers.get("x-request-id", ""),
        user_id=current_user.id,
        path=request.url.path,
    )

    logger.info(f"Cleaning up stale sessions for user: {current_user.email}")

    try:
        cleaned_count = await UserProfileService.cleanup_stale_sessions(
            db, current_user.id
        )

        message = f"Cleaned up {cleaned_count} stale session(s)"
        logger.info(
            f"Stale session cleanup completed for user {current_user.email}: {message}"
        )

        return {"message": message, "cleaned_sessions": cleaned_count}

    except Exception as e:
        logger.error(f"Error cleaning up stale sessions: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Could not clean up stale sessions",
        )


@router.get("/me/preferences", response_model=UserPreferences)
async def get_user_preferences(
    request: Request,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Get user preferences and settings.
    """
    # Set request context
    context_filter.set_context(
        request_id=request.headers.get("x-request-id", ""),
        user_id=current_user.id,
        path=request.url.path,
    )

    logger.info(f"Fetching preferences for user: {current_user.email}")

    try:
        preferences = await UserProfileService._get_or_create_preferences(
            db, current_user.id
        )
        logger.info(
            f"Successfully retrieved preferences for user: {current_user.email}"
        )
        return UserPreferences(**preferences.to_dict())

    except Exception as e:
        logger.error(f"Error fetching user preferences: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Could not retrieve user preferences",
        )


@router.put("/me/preferences", response_model=UserPreferences)
async def update_user_preferences(
    request: Request,
    preferences_update: UserPreferencesUpdate,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Update user preferences and settings.
    """
    # Set request context
    context_filter.set_context(
        request_id=request.headers.get("x-request-id", ""),
        user_id=current_user.id,
        path=request.url.path,
    )

    logger.info(f"Updating preferences for user: {current_user.email}")

    try:
        preferences = await UserProfileService.update_user_preferences(
            db, current_user.id, preferences_update
        )

        logger.info(f"Successfully updated preferences for user: {current_user.email}")
        return UserPreferences(**preferences.to_dict())

    except Exception as e:
        logger.error(f"Error updating user preferences: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Could not update user preferences",
        )
