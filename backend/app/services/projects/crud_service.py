"""
Project CRUD service for managing project lifecycle operations.

This module provides comprehensive CRUD operations for projects including:
- Creating new projects with automatic UUID generation
- Retrieving projects with user authorization
- Updating project metadata
- Soft deletion and archiving
- Listing user projects with filtering and pagination
"""

import uuid
from datetime import datetime
from typing import List, Optional, Dict, Any
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, delete, and_, or_, func
from sqlalchemy.orm import selectinload

from app.models.project import Project, ProjectStatus, ProjectFile, CodeGeneration
from app.services.projects.auth_service import ProjectAuthService


class ProjectNotFoundError(Exception):
    """Raised when a project is not found."""
    pass


class ProjectAccessDeniedError(Exception):
    """Raised when user doesn't have access to a project."""
    pass


class ProjectValidationError(Exception):
    """Raised when project data validation fails."""
    pass


class ProjectCRUDService:
    """
    Service for managing project CRUD operations with proper authorization.
    
    This service handles all database operations for projects while ensuring
    proper user authorization and data validation.
    """

    def __init__(self, db_session: AsyncSession, auth_service: Optional[ProjectAuthService] = None):
        """
        Initialize the CRUD service.
        
        Args:
            db_session: Database session for operations
            auth_service: Authorization service for access control
        """
        self.db = db_session
        self.auth_service = auth_service or ProjectAuthService()

    async def create_project(
        self,
        user_id: str,  # Supabase UUID
        name: str,
        description: Optional[str] = None,
        project_id: Optional[str] = None
    ) -> Project:
        """
        Create a new project for a user.
        
        Args:
            user_id: Supabase UUID of the user creating the project
            name: Name of the project
            description: Optional project description
            project_id: Optional custom project ID (UUID will be generated if not provided)
            
        Returns:
            Created project instance
            
        Raises:
            ProjectValidationError: If project data is invalid
        """
        # Validate input
        if not name or not name.strip():
            raise ProjectValidationError("Project name cannot be empty")
        
        if len(name.strip()) > 100:
            raise ProjectValidationError("Project name cannot exceed 100 characters")
        
        if description and len(description) > 500:
            raise ProjectValidationError("Project description cannot exceed 500 characters")

        # Generate project ID if not provided
        if not project_id:
            project_id = str(uuid.uuid4())
        
        # Validate project ID format
        try:
            uuid.UUID(project_id)
        except ValueError:
            raise ProjectValidationError("Invalid project ID format")

        # Check if project ID already exists
        existing = await self._get_project_by_id(project_id)
        if existing:
            raise ProjectValidationError(f"Project with ID {project_id} already exists")

        # Skip user existence check since users are managed in Supabase
        # The user_id is validated through JWT token authentication

        # Create project
        project = Project(
            id=project_id,
            name=name.strip(),
            description=description.strip() if description else None,
            user_id=user_id,
            status=ProjectStatus.ACTIVE
        )

        self.db.add(project)
        await self.db.flush()  # Flush to get the ID
        await self.db.refresh(project)
        
        return project

    async def get_project(self, project_id: str, user_id: str, include_files: bool = False) -> Project:
        """
        Get a project by ID with authorization check.
        
        Args:
            project_id: Project ID to retrieve
            user_id: User ID requesting the project
            include_files: Whether to include project files in the result
            
        Returns:
            Project instance
            
        Raises:
            ProjectNotFoundError: If project doesn't exist
            ProjectAccessDeniedError: If user doesn't have access
        """
        # Build query with optional file loading
        query = select(Project).where(Project.id == project_id)
        
        if include_files:
            query = query.options(
                selectinload(Project.files),
                selectinload(Project.generations)
            )

        result = await self.db.execute(query)
        project = result.scalar_one_or_none()

        if not project:
            raise ProjectNotFoundError(f"Project {project_id} not found")

        # Check authorization
        if not await self.auth_service.can_access_project(user_id, project):
            raise ProjectAccessDeniedError(f"User {user_id} cannot access project {project_id}")

        return project

    async def list_user_projects(
        self,
        user_id: str,  # Supabase UUID
        status_filter: Optional[ProjectStatus] = None,
        search_query: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
        include_files: bool = False
    ) -> List[Project]:
        """
        List projects for a user with filtering and pagination.
        
        Args:
            user_id: User ID to list projects for
            status_filter: Optional status filter
            search_query: Optional search query for name/description
            limit: Maximum number of projects to return
            offset: Number of projects to skip
            include_files: Whether to include project files
            
        Returns:
            List of projects
        """
        # Build base query
        query = select(Project).where(Project.user_id == user_id)

        # Apply status filter
        if status_filter:
            query = query.where(Project.status == status_filter)
        else:
            # By default, exclude deleted projects
            query = query.where(Project.status != ProjectStatus.DELETED)

        # Apply search filter
        if search_query and search_query.strip():
            search_term = f"%{search_query.strip()}%"
            query = query.where(
                or_(
                    Project.name.ilike(search_term),
                    Project.description.ilike(search_term)
                )
            )

        # Add file loading if requested
        if include_files:
            query = query.options(
                selectinload(Project.files),
                selectinload(Project.generations)
            )

        # Apply pagination and ordering
        query = query.order_by(Project.updated_at.desc()).limit(limit).offset(offset)

        result = await self.db.execute(query)
        return result.scalars().all()

    async def update_project(
        self,
        project_id: str,
        user_id: str,  # Supabase UUID
        name: Optional[str] = None,
        description: Optional[str] = None,
        status: Optional[ProjectStatus] = None
    ) -> Project:
        """
        Update project metadata.
        
        Args:
            project_id: Project ID to update
            user_id: User ID making the update
            name: New project name
            description: New project description
            status: New project status
            
        Returns:
            Updated project instance
            
        Raises:
            ProjectNotFoundError: If project doesn't exist
            ProjectAccessDeniedError: If user doesn't have access
            ProjectValidationError: If update data is invalid
        """
        # Get existing project with authorization check
        project = await self.get_project(project_id, user_id)

        # Validate updates
        updates = {}
        
        if name is not None:
            if not name.strip():
                raise ProjectValidationError("Project name cannot be empty")
            if len(name.strip()) > 100:
                raise ProjectValidationError("Project name cannot exceed 100 characters")
            updates['name'] = name.strip()

        if description is not None:
            if description and len(description) > 500:
                raise ProjectValidationError("Project description cannot exceed 500 characters")
            updates['description'] = description.strip() if description else None

        if status is not None:
            updates['status'] = status

        # Apply updates if any
        if updates:
            updates['updated_at'] = datetime.utcnow()
            
            stmt = (
                update(Project)
                .where(Project.id == project_id)
                .values(**updates)
            )
            await self.db.execute(stmt)
            await self.db.refresh(project)

        return project

    async def delete_project(self, project_id: str, user_id: str, soft_delete: bool = True) -> bool:
        """
        Delete a project (soft or hard delete).
        
        Args:
            project_id: Project ID to delete
            user_id: User ID requesting deletion
            soft_delete: Whether to soft delete (mark as deleted) or hard delete
            
        Returns:
            True if deletion was successful
            
        Raises:
            ProjectNotFoundError: If project doesn't exist
            ProjectAccessDeniedError: If user doesn't have access
        """
        # Get project with authorization check
        project = await self.get_project(project_id, user_id)

        if soft_delete:
            # Soft delete - mark as deleted
            await self.update_project(project_id, user_id, status=ProjectStatus.DELETED)
        else:
            # Hard delete - remove from database
            stmt = delete(Project).where(Project.id == project_id)
            await self.db.execute(stmt)

        return True

    async def archive_project(self, project_id: str, user_id: str) -> Project:
        """
        Archive a project (set status to archived).
        
        Args:
            project_id: Project ID to archive
            user_id: User ID requesting archival
            
        Returns:
            Archived project instance
        """
        return await self.update_project(project_id, user_id, status=ProjectStatus.ARCHIVED)

    async def restore_project(self, project_id: str, user_id: str) -> Project:
        """
        Restore a deleted or archived project.
        
        Args:
            project_id: Project ID to restore
            user_id: User ID requesting restoration
            
        Returns:
            Restored project instance
        """
        return await self.update_project(project_id, user_id, status=ProjectStatus.ACTIVE)

    async def get_project_stats(self, project_id: str, user_id: str) -> Dict[str, Any]:
        """
        Get statistics for a project.
        
        Args:
            project_id: Project ID to get stats for
            user_id: User ID requesting stats
            
        Returns:
            Dictionary with project statistics
        """
        # Get project with authorization check
        project = await self.get_project(project_id, user_id)

        # Count files
        file_count_query = select(func.count(ProjectFile.id)).where(
            ProjectFile.project_id == project_id
        )
        file_count_result = await self.db.execute(file_count_query)
        file_count = file_count_result.scalar() or 0

        # Count generations
        generation_count_query = select(func.count(CodeGeneration.id)).where(
            CodeGeneration.project_id == project_id
        )
        generation_count_result = await self.db.execute(generation_count_query)
        generation_count = generation_count_result.scalar() or 0

        # Calculate total file size
        total_size_query = select(func.sum(ProjectFile.size_bytes)).where(
            ProjectFile.project_id == project_id
        )
        total_size_result = await self.db.execute(total_size_query)
        total_size = total_size_result.scalar() or 0

        return {
            'project_id': project_id,
            'name': project.name,
            'status': project.status.value,
            'file_count': file_count,
            'generation_count': generation_count,
            'total_size_bytes': total_size,
            'created_at': project.created_at,
            'updated_at': project.updated_at
        }

    async def _get_project_by_id(self, project_id: str) -> Optional[Project]:
        """Get project by ID without authorization check."""
        query = select(Project).where(Project.id == project_id)
        result = await self.db.execute(query)
        return result.scalar_one_or_none()

    async def _verify_user_exists(self, user_id: str) -> bool:
        """
        Verify that a user exists.
        
        Since users are managed in Supabase, we'll always return True
        as user validation is handled through JWT token authentication.
        """
        return True