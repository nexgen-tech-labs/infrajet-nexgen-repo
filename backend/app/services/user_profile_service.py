"""
User Profile Service for comprehensive user profile management.

This service handles user profile operations, session management,
connected services, and user preferences.
"""

import logging
from datetime import datetime, timedelta
from typing import List, Optional, Dict, Any, Tuple
from sqlalchemy import select, func, and_, or_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.user import User, UserPreferences, WebSocketSession, GitHubSyncRecord, GitHubConnection
from app.models.project import Project, CodeGeneration
from app.schemas.user import (
    UserProfileComplete,
    UserPreferences as UserPreferencesSchema,
    UserPreferencesUpdate,
    UserSession,
    ConnectedServices,
    AzureEntraProfile,
    GitHubIntegration,
)
from app.services.websocket_manager import websocket_manager

logger = logging.getLogger(__name__)


class UserProfileService:
    """Service for comprehensive user profile management."""

    @staticmethod
    async def get_complete_user_profile(
        db: AsyncSession, user_id: int
    ) -> Optional[UserProfileComplete]:
        """
        Get complete user profile with all related information.

        Args:
            db: Database session
            user_id: User ID

        Returns:
            Complete user profile or None if user not found
        """
        try:
            # Get user with all relationships
            result = await db.execute(
                select(User)
                .options(
                    selectinload(User.preferences),
                    selectinload(User.websocket_sessions),
                    selectinload(User.github_sync_records),
                )
                .filter(User.id == user_id)
            )
            user = result.scalars().first()

            if not user:
                return None

            # Get user statistics
            stats = await UserProfileService._get_user_statistics(db, user_id)

            # Get active WebSocket sessions
            active_sessions = await UserProfileService._get_active_websocket_sessions(
                db, user_id
            )

            # Get GitHub connection info
            github_result = await db.execute(
                select(GitHubConnection).filter(
                    GitHubConnection.supabase_user_id == user.supabase_user_id,
                    GitHubConnection.is_github_oauth_connected == True
                )
            )
            github_connection = github_result.scalars().first()

            # Build connected services info
            connected_services = ConnectedServices(
                github=GitHubIntegration(
                    is_connected=github_connection is not None,
                    username=github_connection.github_username if github_connection else None,
                    connected_at=github_connection.github_connected_at if github_connection else None,
                ),
                azure_entra=AzureEntraProfile(
                    azure_entra_id=user.azure_entra_id,
                    azure_tenant_id=user.azure_tenant_id,
                    organization=user.organization,
                    department=user.department,
                    profile_picture_url=user.profile_picture_url,
                    token_expires_at=user.azure_token_expires_at,
                ),
            )

            # Get or create user preferences
            preferences = await UserProfileService._get_or_create_preferences(
                db, user_id
            )

            return UserProfileComplete(
                id=user.id,
                email=user.email,
                full_name=user.full_name,
                is_active=user.is_active,
                role=user.role,
                created_at=user.created_at,
                updated_at=user.updated_at,
                last_login=user.last_login,
                connected_services=connected_services,
                active_sessions=active_sessions,
                preferences=UserPreferencesSchema(**preferences.to_dict()),
                total_projects=stats["total_projects"],
                total_generations=stats["total_generations"],
                github_sync_count=stats["github_sync_count"],
            )

        except Exception as e:
            logger.error(
                f"Error getting complete user profile for user {user_id}: {str(e)}"
            )
            raise

    @staticmethod
    async def _get_user_statistics(db: AsyncSession, user_id: int) -> Dict[str, int]:
        """Get user statistics."""
        try:
            # Count projects
            projects_result = await db.execute(
                select(func.count(Project.id)).filter(Project.user_id == user_id)
            )
            total_projects = projects_result.scalar() or 0

            # Count code generations
            generations_result = await db.execute(
                select(func.count(CodeGeneration.id))
                .join(Project)
                .filter(Project.user_id == user_id)
            )
            total_generations = generations_result.scalar() or 0

            # Count GitHub syncs
            sync_result = await db.execute(
                select(func.count(GitHubSyncRecord.id)).filter(
                    GitHubSyncRecord.user_id == user_id
                )
            )
            github_sync_count = sync_result.scalar() or 0

            return {
                "total_projects": total_projects,
                "total_generations": total_generations,
                "github_sync_count": github_sync_count,
            }

        except Exception as e:
            logger.error(f"Error getting user statistics for user {user_id}: {str(e)}")
            return {"total_projects": 0, "total_generations": 0, "github_sync_count": 0}

    @staticmethod
    async def _get_active_websocket_sessions(
        db: AsyncSession, user_id: int
    ) -> List[UserSession]:
        """Get active WebSocket sessions for user."""
        try:
            # Get sessions from database
            result = await db.execute(
                select(WebSocketSession)
                .filter(
                    and_(
                        WebSocketSession.user_id == user_id,
                        WebSocketSession.is_active == True,
                    )
                )
                .order_by(WebSocketSession.connected_at.desc())
            )
            db_sessions = result.scalars().all()

            # Get active sessions from WebSocket manager
            active_session_ids = set()
            if user_id in websocket_manager.user_sessions:
                active_session_ids = websocket_manager.user_sessions[user_id]

            # Build session list
            sessions = []
            for db_session in db_sessions:
                # Check if session is actually active in WebSocket manager
                is_actually_active = db_session.session_id in active_session_ids

                sessions.append(
                    UserSession(
                        session_id=db_session.session_id,
                        user_id=db_session.user_id,
                        connected_at=db_session.connected_at,
                        last_heartbeat=db_session.last_heartbeat,
                        metadata=db_session.session_metadata or {},
                        is_active=is_actually_active,
                    )
                )

            return sessions

        except Exception as e:
            logger.error(
                f"Error getting active WebSocket sessions for user {user_id}: {str(e)}"
            )
            return []

    @staticmethod
    async def _get_or_create_preferences(
        db: AsyncSession, user_id: int
    ) -> UserPreferences:
        """Get or create user preferences."""
        try:
            # Try to get existing preferences
            result = await db.execute(
                select(UserPreferences).filter(UserPreferences.user_id == user_id)
            )
            preferences = result.scalars().first()

            if not preferences:
                # Create default preferences
                preferences = UserPreferences(user_id=user_id)
                db.add(preferences)
                await db.commit()
                await db.refresh(preferences)
                logger.info(f"Created default preferences for user {user_id}")

            return preferences

        except Exception as e:
            logger.error(
                f"Error getting/creating preferences for user {user_id}: {str(e)}"
            )
            raise

    @staticmethod
    async def update_user_preferences(
        db: AsyncSession, user_id: int, preferences_update: UserPreferencesUpdate
    ) -> UserPreferences:
        """
        Update user preferences.

        Args:
            db: Database session
            user_id: User ID
            preferences_update: Preferences update data

        Returns:
            Updated preferences
        """
        try:
            # Get or create preferences
            preferences = await UserProfileService._get_or_create_preferences(
                db, user_id
            )

            # Update preferences
            update_data = preferences_update.dict(exclude_unset=True)
            preferences.update_preferences(**update_data)

            await db.commit()
            await db.refresh(preferences)

            logger.info(f"Updated preferences for user {user_id}: {update_data}")
            return preferences

        except Exception as e:
            logger.error(f"Error updating preferences for user {user_id}: {str(e)}")
            await db.rollback()
            raise

    @staticmethod
    async def get_user_sessions(
        db: AsyncSession, user_id: int, include_inactive: bool = False
    ) -> List[UserSession]:
        """
        Get user sessions.

        Args:
            db: Database session
            user_id: User ID
            include_inactive: Whether to include inactive sessions

        Returns:
            List of user sessions
        """
        try:
            query = select(WebSocketSession).filter(WebSocketSession.user_id == user_id)

            if not include_inactive:
                query = query.filter(WebSocketSession.is_active == True)

            query = query.order_by(WebSocketSession.connected_at.desc())

            result = await db.execute(query)
            db_sessions = result.scalars().all()

            # Get active sessions from WebSocket manager
            active_session_ids = set()
            if user_id in websocket_manager.user_sessions:
                active_session_ids = websocket_manager.user_sessions[user_id]

            sessions = []
            for db_session in db_sessions:
                is_actually_active = db_session.session_id in active_session_ids

                sessions.append(
                    UserSession(
                        session_id=db_session.session_id,
                        user_id=db_session.user_id,
                        connected_at=db_session.connected_at,
                        last_heartbeat=db_session.last_heartbeat,
                        metadata=db_session.session_metadata or {},
                        is_active=is_actually_active,
                    )
                )

            return sessions

        except Exception as e:
            logger.error(f"Error getting sessions for user {user_id}: {str(e)}")
            raise

    @staticmethod
    async def revoke_user_sessions(
        db: AsyncSession, user_id: int, session_ids: List[str], revoke_all: bool = False
    ) -> Tuple[List[str], List[str]]:
        """
        Revoke user sessions.

        Args:
            db: Database session
            user_id: User ID
            session_ids: List of session IDs to revoke
            revoke_all: Whether to revoke all sessions

        Returns:
            Tuple of (revoked_session_ids, failed_session_ids)
        """
        try:
            revoked_sessions = []
            failed_sessions = []

            if revoke_all:
                # Get all active sessions for user
                result = await db.execute(
                    select(WebSocketSession).filter(
                        and_(
                            WebSocketSession.user_id == user_id,
                            WebSocketSession.is_active == True,
                        )
                    )
                )
                sessions_to_revoke = result.scalars().all()
                session_ids = [session.session_id for session in sessions_to_revoke]

            for session_id in session_ids:
                try:
                    # Disconnect from WebSocket manager
                    await websocket_manager.disconnect(session_id)

                    # Update database record
                    result = await db.execute(
                        select(WebSocketSession).filter(
                            and_(
                                WebSocketSession.session_id == session_id,
                                WebSocketSession.user_id == user_id,
                            )
                        )
                    )
                    db_session = result.scalars().first()

                    if db_session:
                        db_session.disconnect()
                        revoked_sessions.append(session_id)
                        logger.info(f"Revoked session {session_id} for user {user_id}")
                    else:
                        failed_sessions.append(session_id)
                        logger.warning(
                            f"Session {session_id} not found for user {user_id}"
                        )

                except Exception as e:
                    logger.error(f"Error revoking session {session_id}: {str(e)}")
                    failed_sessions.append(session_id)

            await db.commit()
            return revoked_sessions, failed_sessions

        except Exception as e:
            logger.error(f"Error revoking sessions for user {user_id}: {str(e)}")
            await db.rollback()
            raise

    @staticmethod
    async def cleanup_stale_sessions(db: AsyncSession, user_id: int) -> int:
        """
        Clean up stale sessions for a user.

        Args:
            db: Database session
            user_id: User ID

        Returns:
            Number of sessions cleaned up
        """
        try:
            # Define stale threshold (sessions inactive for more than 1 hour)
            stale_threshold = datetime.utcnow() - timedelta(hours=1)

            # Find stale sessions
            result = await db.execute(
                select(WebSocketSession).filter(
                    and_(
                        WebSocketSession.user_id == user_id,
                        WebSocketSession.is_active == True,
                        WebSocketSession.last_heartbeat < stale_threshold,
                    )
                )
            )
            stale_sessions = result.scalars().all()

            cleaned_count = 0
            for session in stale_sessions:
                try:
                    # Disconnect from WebSocket manager
                    await websocket_manager.disconnect(session.session_id)

                    # Mark as disconnected in database
                    session.disconnect()
                    cleaned_count += 1

                except Exception as e:
                    logger.error(
                        f"Error cleaning up session {session.session_id}: {str(e)}"
                    )

            if cleaned_count > 0:
                await db.commit()
                logger.info(
                    f"Cleaned up {cleaned_count} stale sessions for user {user_id}"
                )

            return cleaned_count

        except Exception as e:
            logger.error(
                f"Error cleaning up stale sessions for user {user_id}: {str(e)}"
            )
            await db.rollback()
            return 0

    @staticmethod
    async def get_connected_services_status(
        db: AsyncSession, user_id: int
    ) -> ConnectedServices:
        """
        Get connected services status for user.

        Args:
            db: Database session
            user_id: User ID

        Returns:
            Connected services information
        """
        try:
            result = await db.execute(select(User).filter(User.id == user_id))
            user = result.scalars().first()

            if not user:
                raise ValueError(f"User {user_id} not found")

            # Get GitHub connection info
            github_result = await db.execute(
                select(GitHubConnection).filter(
                    GitHubConnection.supabase_user_id == user.supabase_user_id,
                    GitHubConnection.is_github_oauth_connected == True
                )
            )
            github_connection = github_result.scalars().first()

            return ConnectedServices(
                github=GitHubIntegration(
                    is_connected=github_connection is not None,
                    username=github_connection.github_username if github_connection else None,
                    connected_at=github_connection.github_connected_at if github_connection else None,
                ),
                azure_entra=AzureEntraProfile(
                    azure_entra_id=user.azure_entra_id,
                    azure_tenant_id=user.azure_tenant_id,
                    organization=user.organization,
                    department=user.department,
                    profile_picture_url=user.profile_picture_url,
                    token_expires_at=user.azure_token_expires_at,
                ),
            )

        except Exception as e:
            logger.error(
                f"Error getting connected services for user {user_id}: {str(e)}"
            )
            raise

    @staticmethod
    async def record_websocket_session(
        db: AsyncSession,
        session_id: str,
        user_id: int,
        metadata: Optional[Dict[str, Any]] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
    ) -> WebSocketSession:
        """
        Record a new WebSocket session in the database.

        Args:
            db: Database session
            session_id: WebSocket session ID
            user_id: User ID
            metadata: Optional session metadata
            ip_address: Client IP address
            user_agent: Client user agent

        Returns:
            Created WebSocket session record
        """
        try:
            session = WebSocketSession(
                session_id=session_id,
                user_id=user_id,
                session_metadata=metadata,
                ip_address=ip_address,
                user_agent=user_agent,
            )

            db.add(session)
            await db.commit()
            await db.refresh(session)

            logger.info(f"Recorded WebSocket session {session_id} for user {user_id}")
            return session

        except Exception as e:
            logger.error(f"Error recording WebSocket session {session_id}: {str(e)}")
            await db.rollback()
            raise
