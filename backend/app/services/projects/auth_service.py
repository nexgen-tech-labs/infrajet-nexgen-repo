"""
Project authorization service for managing access control.

This module provides authorization logic for project operations including:
- User access validation
- Role-based permissions
- Project ownership verification
- Admin override capabilities
"""

from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.models.project import Project, ProjectStatus
from app.models.user import User, UserRole


class ProjectAuthService:
    """
    Service for handling project authorization and access control.
    
    This service determines whether users can perform specific operations
    on projects based on ownership, roles, and project status.
    """

    def __init__(self, db_session: Optional[AsyncSession] = None):
        """
        Initialize the authorization service.
        
        Args:
            db_session: Optional database session for user lookups
        """
        self.db = db_session

    async def can_access_project(self, user_id: int, project: Project) -> bool:
        """
        Check if a user can access a project.
        
        Args:
            user_id: User ID to check access for
            project: Project to check access to
            
        Returns:
            True if user can access the project
        """
        # Project owner always has access (unless project is deleted)
        if project.user_id == user_id:
            return project.status != ProjectStatus.DELETED

        # Check if user is admin/superuser (requires db session)
        if self.db:
            user_role = await self._get_user_role(user_id)
            if user_role in [UserRole.ADMIN, UserRole.SUPERUSER]:
                return True

        return False

    async def can_modify_project(self, user_id: int, project: Project) -> bool:
        """
        Check if a user can modify a project.
        
        Args:
            user_id: User ID to check modification rights for
            project: Project to check modification rights for
            
        Returns:
            True if user can modify the project
        """
        # Only active projects can be modified
        if project.status == ProjectStatus.DELETED:
            return False

        # Project owner can modify
        if project.user_id == user_id:
            return True

        # Check if user is admin/superuser (requires db session)
        if self.db:
            user_role = await self._get_user_role(user_id)
            if user_role in [UserRole.ADMIN, UserRole.SUPERUSER]:
                return True

        return False

    async def can_delete_project(self, user_id: int, project: Project) -> bool:
        """
        Check if a user can delete a project.
        
        Args:
            user_id: User ID to check deletion rights for
            project: Project to check deletion rights for
            
        Returns:
            True if user can delete the project
        """
        # Already deleted projects cannot be deleted again
        if project.status == ProjectStatus.DELETED:
            return False

        # Project owner can delete
        if project.user_id == user_id:
            return True

        # Check if user is admin/superuser (requires db session)
        if self.db:
            user_role = await self._get_user_role(user_id)
            if user_role in [UserRole.ADMIN, UserRole.SUPERUSER]:
                return True

        return False

    async def can_restore_project(self, user_id: int, project: Project) -> bool:
        """
        Check if a user can restore a deleted/archived project.
        
        Args:
            user_id: User ID to check restoration rights for
            project: Project to check restoration rights for
            
        Returns:
            True if user can restore the project
        """
        # Only deleted or archived projects can be restored
        if project.status == ProjectStatus.ACTIVE:
            return False

        # Project owner can restore
        if project.user_id == user_id:
            return True

        # Check if user is admin/superuser (requires db session)
        if self.db:
            user_role = await self._get_user_role(user_id)
            if user_role in [UserRole.ADMIN, UserRole.SUPERUSER]:
                return True

        return False

    async def can_view_all_projects(self, user_id: int) -> bool:
        """
        Check if a user can view all projects (admin function).
        
        Args:
            user_id: User ID to check admin rights for
            
        Returns:
            True if user can view all projects
        """
        if not self.db:
            return False

        user_role = await self._get_user_role(user_id)
        return user_role in [UserRole.ADMIN, UserRole.SUPERUSER]

    def is_project_owner(self, user_id: int, project: Project) -> bool:
        """
        Check if a user is the owner of a project.
        
        Args:
            user_id: User ID to check ownership for
            project: Project to check ownership of
            
        Returns:
            True if user owns the project
        """
        return project.user_id == user_id

    def can_access_deleted_project(self, user_id: int, project: Project) -> bool:
        """
        Check if a user can access a deleted project.
        
        Only project owners and admins can access deleted projects.
        
        Args:
            user_id: User ID to check access for
            project: Deleted project to check access to
            
        Returns:
            True if user can access the deleted project
        """
        if project.status != ProjectStatus.DELETED:
            return True  # Not deleted, use normal access rules

        # Only owner can access deleted projects (admins need db check)
        return project.user_id == user_id

    async def filter_accessible_projects(self, user_id: int, projects: list[Project]) -> list[Project]:
        """
        Filter a list of projects to only include those accessible to the user.
        
        Args:
            user_id: User ID to filter for
            projects: List of projects to filter
            
        Returns:
            Filtered list of accessible projects
        """
        accessible_projects = []
        
        # Check if user is admin (if db session available)
        is_admin = False
        if self.db:
            user_role = await self._get_user_role(user_id)
            is_admin = user_role in [UserRole.ADMIN, UserRole.SUPERUSER]

        for project in projects:
            # Admin can see all projects
            if is_admin:
                accessible_projects.append(project)
                continue

            # Owner can see their projects (except deleted ones)
            if project.user_id == user_id and project.status != ProjectStatus.DELETED:
                accessible_projects.append(project)

        return accessible_projects

    async def validate_project_access(self, user_id: int, project_id: str) -> bool:
        """
        Validate that a user has access to a project by ID.
        
        This is a convenience method that requires a database session.
        
        Args:
            user_id: User ID to validate access for
            project_id: Project ID to validate access to
            
        Returns:
            True if user has access to the project
            
        Raises:
            ValueError: If no database session is available
        """
        if not self.db:
            raise ValueError("Database session required for project access validation")

        # Get project from database
        query = select(Project).where(Project.id == project_id)
        result = await self.db.execute(query)
        project = result.scalar_one_or_none()

        if not project:
            return False

        return await self.can_access_project(user_id, project)

    async def _get_user_role(self, user_id: int) -> Optional[UserRole]:
        """
        Get the role of a user.
        
        Args:
            user_id: User ID to get role for
            
        Returns:
            User role or None if user not found
        """
        if not self.db:
            return None

        query = select(User.role).where(User.id == user_id)
        result = await self.db.execute(query)
        return result.scalar_one_or_none()

    def get_permission_summary(self, user_id: int, project: Project) -> dict:
        """
        Get a summary of permissions for a user on a project.
        
        Args:
            user_id: User ID to get permissions for
            project: Project to check permissions on
            
        Returns:
            Dictionary with permission flags
        """
        is_owner = self.is_project_owner(user_id, project)
        
        return {
            'can_access': project.user_id == user_id and project.status != ProjectStatus.DELETED,
            'can_modify': is_owner and project.status != ProjectStatus.DELETED,
            'can_delete': is_owner and project.status != ProjectStatus.DELETED,
            'can_restore': is_owner and project.status in [ProjectStatus.DELETED, ProjectStatus.ARCHIVED],
            'is_owner': is_owner,
            'project_status': project.status.value
        }