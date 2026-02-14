"""
Enhanced project dashboard routes with real-time updates.

This module provides enhanced project dashboard endpoints with real-time status
information, file tree structures, and WebSocket integration for live updates.
"""

import logging
from datetime import datetime
from typing import List, Optional, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, Query, Path, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import func, desc, and_, select

from app.db.session import get_async_db
from app.dependencies.auth import get_current_user_id
from app.models.user import User
from app.models.project import Project, ProjectStatus, CodeGeneration, GenerationStatus, GeneratedFile
from app.services.realtime_service import realtime_service
from app.api.v1.projects.dashboard_models import (
    ProjectDashboardResponse,
    ProjectWithRealtimeStatus,
    ProjectFileTree,
    GenerationSummary,
    ActiveGenerationSummary,
    ProjectListWithRealtimeResponse,
    ErrorResponse
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/projects/dashboard", tags=["project-dashboard"])


@router.get(
    "",
    response_model=ProjectDashboardResponse,
    summary="Get enhanced project dashboard",
    description="""
    Retrieve an enhanced dashboard view of all user projects with real-time status information.
    
    Includes:
    - Project summaries with real-time generation status
    - Active generation monitoring
    - File counts and size statistics
    - Recent activity timeline
    - WebSocket connection information for real-time updates
    """,
    responses={
        200: {"description": "Successfully retrieved project dashboard"},
        401: {"description": "Authentication required"},
        500: {"description": "Internal server error", "model": ErrorResponse}
    }
)
async def get_project_dashboard(
    include_archived: bool = Query(False, description="Include archived projects"),
    limit: int = Query(20, ge=1, le=100, description="Maximum number of projects to return"),
    db: AsyncSession = Depends(get_async_db),
    user_id: str = Depends(get_current_user_id)
) -> ProjectDashboardResponse:
    """
    Get enhanced project dashboard with real-time status information.
    
    Args:
        include_archived: Whether to include archived projects
        limit: Maximum number of projects to return
        db: Database session
        current_user: Authenticated user
        
    Returns:
        ProjectDashboardResponse with enhanced project information
    """
    try:
        # Build status filter
        status_filters = [ProjectStatus.ACTIVE]
        if include_archived:
            status_filters.append(ProjectStatus.ARCHIVED)
        
        # Get projects with real-time status
        projects_query = select(Project).filter(
            and_(
                Project.user_id == user_id,
                Project.status.in_(status_filters)
            )
        ).order_by(desc(Project.updated_at)).limit(limit)
        
        projects_result = await db.execute(projects_query)
        projects = projects_result.scalars().all()
        
        # Get active generations across all projects
        active_generations_query = select(CodeGeneration).filter(
            and_(
                CodeGeneration.user_id == user_id,
                CodeGeneration.status.in_([GenerationStatus.PENDING, GenerationStatus.IN_PROGRESS])
            )
        ).order_by(desc(CodeGeneration.created_at))
        
        active_generations_result = await db.execute(active_generations_query)
        active_generations = active_generations_result.scalars().all()
        
        # Build project summaries with real-time status
        project_summaries = []
        for project in projects:
            # Get project statistics using proper relationship queries
            file_count = len(project.files)
            total_size = sum(f.size_bytes for f in project.files)
            generation_count = len(project.generations)
            
            # Get active generations for this project
            project_active_gens = [g for g in active_generations if g.project_id == project.id]
            
            # Determine real-time status
            realtime_status = "idle"
            if project_active_gens:
                if any(g.status == GenerationStatus.IN_PROGRESS for g in project_active_gens):
                    realtime_status = "generating"
                else:
                    realtime_status = "pending"
            
            # Get most recent generation
            recent_generation_query = select(CodeGeneration).filter(
                CodeGeneration.project_id == project.id
            ).order_by(desc(CodeGeneration.created_at)).limit(1)
            recent_generation_result = await db.execute(recent_generation_query)
            recent_generation = recent_generation_result.scalar_one_or_none()
            
            project_summary = ProjectWithRealtimeStatus(
                id=project.id,
                name=project.name,
                description=project.description,
                status=project.status,
                created_at=project.created_at,
                updated_at=project.updated_at,
                file_count=file_count,
                total_size_bytes=total_size,
                generation_count=generation_count,
                realtime_status=realtime_status,
                active_generation_count=len(project_active_gens),
                last_generation_at=recent_generation.created_at if recent_generation else None,
                last_generation_status=recent_generation.status if recent_generation else None
            )
            project_summaries.append(project_summary)
        
        # Build active generation summaries
        active_generation_summaries = []
        for generation in active_generations:
            project = next((p for p in projects if p.id == generation.project_id), None)
            if project:
                active_gen_summary = ActiveGenerationSummary(
                    generation_id=generation.id,
                    project_id=generation.project_id,
                    project_name=project.name,
                    query=generation.query,
                    scenario=generation.scenario,
                    status=generation.status,
                    created_at=generation.created_at,
                    estimated_completion=None  # Would be calculated based on generation progress
                )
                active_generation_summaries.append(active_gen_summary)
        
        # Get WebSocket connection stats for this user
        ws_stats = realtime_service.get_connection_stats()
        user_connections = ws_stats.get("connections_by_user", {}).get(user_id, 0)
        
        return ProjectDashboardResponse(
            projects=project_summaries,
            active_generations=active_generation_summaries,
            total_projects=len(project_summaries),
            total_active_generations=len(active_generation_summaries),
            websocket_connections=user_connections,
            dashboard_generated_at=datetime.utcnow()
        )
        
    except Exception as e:
        logger.error(f"Failed to get project dashboard for user {user_id}: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to retrieve project dashboard: {str(e)}"
        )


@router.get(
    "/{project_id}/realtime-status",
    response_model=ProjectWithRealtimeStatus,
    summary="Get project with real-time status",
    description="""
    Get detailed project information with real-time status updates.
    
    Includes current generation status, active WebSocket connections,
    and real-time file tree structure.
    """,
    responses={
        200: {"description": "Successfully retrieved project with real-time status"},
        401: {"description": "Authentication required"},
        403: {"description": "Access denied - project belongs to another user"},
        404: {"description": "Project not found", "model": ErrorResponse},
        500: {"description": "Internal server error", "model": ErrorResponse}
    }
)
async def get_project_realtime_status(
    project_id: str = Path(..., description="Project UUID"),
    db: AsyncSession = Depends(get_async_db),
    user_id: str = Depends(get_current_user_id)
) -> ProjectWithRealtimeStatus:
    """
    Get project with real-time status information.
    
    Args:
        project_id: Project UUID
        db: Database session
        current_user: Authenticated user
        
    Returns:
        ProjectWithRealtimeStatus with real-time information
    """
    try:
        # Get project with authorization check
        project_query = select(Project).filter(
            and_(
                Project.id == project_id,
                Project.user_id == user_id
            )
        )
        project_result = await db.execute(project_query)
        project = project_result.scalar_one_or_none()
        
        if not project:
            raise HTTPException(
                status_code=404,
                detail=f"Project {project_id} not found"
            )
        
        # Get project statistics
        file_count = len(project.files)
        total_size_bytes = sum(f.size_bytes for f in project.files)
        generation_count = len(project.generations)
        
        # Get active generations for this project
        active_generations_query = select(CodeGeneration).filter(
            and_(
                CodeGeneration.project_id == project_id,
                CodeGeneration.status.in_([GenerationStatus.PENDING, GenerationStatus.IN_PROGRESS])
            )
        )
        active_generations_result = await db.execute(active_generations_query)
        active_generations = active_generations_result.scalars().all()
        
        # Determine real-time status
        realtime_status = "idle"
        if active_generations:
            if any(g.status == GenerationStatus.IN_PROGRESS for g in active_generations):
                realtime_status = "generating"
            else:
                realtime_status = "pending"
        
        # Get most recent generation
        recent_generation_query = select(CodeGeneration).filter(
            CodeGeneration.project_id == project_id
        ).order_by(desc(CodeGeneration.created_at)).limit(1)
        recent_generation_result = await db.execute(recent_generation_query)
        recent_generation = recent_generation_result.scalar_one_or_none()
        
        return ProjectWithRealtimeStatus(
            id=project.id,
            name=project.name,
            description=project.description,
            status=project.status,
            created_at=project.created_at,
            updated_at=project.updated_at,
            file_count=file_count,
            total_size_bytes=total_size_bytes,
            generation_count=generation_count,
            realtime_status=realtime_status,
            active_generation_count=len(active_generations),
            last_generation_at=recent_generation.created_at if recent_generation else None,
            last_generation_status=recent_generation.status if recent_generation else None
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get real-time status for project {project_id}: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to retrieve project real-time status: {str(e)}"
        )


@router.get(
    "/{project_id}/file-tree",
    response_model=ProjectFileTree,
    summary="Get project file tree with generation organization",
    description="""
    Get project file tree structure organized by generation sessions.
    
    Files are grouped by their generation hash, showing the hierarchical
    structure of generated code with metadata for each file.
    """,
    responses={
        200: {"description": "Successfully retrieved project file tree"},
        401: {"description": "Authentication required"},
        403: {"description": "Access denied - project belongs to another user"},
        404: {"description": "Project not found", "model": ErrorResponse},
        500: {"description": "Internal server error", "model": ErrorResponse}
    }
)
async def get_project_file_tree(
    project_id: str = Path(..., description="Project UUID"),
    include_content_preview: bool = Query(False, description="Include content preview for small files"),
    db: AsyncSession = Depends(get_async_db),
    user_id: str = Depends(get_current_user_id)
) -> ProjectFileTree:
    """
    Get project file tree organized by generation sessions.
    
    Args:
        project_id: Project UUID
        include_content_preview: Whether to include content preview for small files
        db: Database session
        current_user: Authenticated user
        
    Returns:
        ProjectFileTree with hierarchical file structure
    """
    try:
        # Get project with files
        project_query = select(Project).filter(
            and_(
                Project.id == project_id,
                Project.user_id == user_id
            )
        )
        project_result = await db.execute(project_query)
        project = project_result.scalar_one_or_none()
        
        if not project:
            raise HTTPException(
                status_code=404,
                detail=f"Project {project_id} not found"
            )
        
        # Get generations for this project
        generations_query = select(CodeGeneration).filter(
            CodeGeneration.project_id == project_id
        ).order_by(desc(CodeGeneration.created_at))
        generations_result = await db.execute(generations_query)
        generations = generations_result.scalars().all()
        
        # Build generation summaries
        generation_summaries = []
        for generation in generations:
            # Get files for this generation through the GeneratedFile relationship
            generation_files_query = select(GeneratedFile).filter(
                GeneratedFile.generation_id == generation.id
            )
            generation_files_result = await db.execute(generation_files_query)
            generation_files_query_results = generation_files_result.scalars().all()
            
            generation_files = [gf.project_file for gf in generation_files_query_results]
            
            gen_summary = GenerationSummary(
                generation_id=generation.id,
                query=generation.query,
                scenario=generation.scenario,
                status=generation.status,
                generation_hash=generation.generation_hash,
                created_at=generation.created_at,
                file_count=len(generation_files),
                files=[
                    {
                        "id": f.id,
                        "file_path": f.file_path,
                        "azure_path": f.azure_path,
                        "file_type": f.file_type,
                        "size_bytes": f.size_bytes,
                        "content_hash": f.content_hash,
                        "created_at": f.created_at,
                        "updated_at": f.updated_at
                    }
                    for f in generation_files
                ]
            )
            generation_summaries.append(gen_summary)
        
        # Build file tree structure
        file_tree = {
            "project_root": {
                "type": "directory",
                "name": project.name,
                "path": "/",
                "children": {}
            }
        }
        
        # Organize files by generation
        for generation in generation_summaries:
            gen_folder_name = f"generation_{generation.generation_hash}"
            file_tree["project_root"]["children"][gen_folder_name] = {
                "type": "directory",
                "name": f"Generation: {generation.query[:50]}...",
                "path": f"/{gen_folder_name}",
                "generation_id": generation.generation_id,
                "generation_status": generation.status,
                "created_at": generation.created_at,
                "children": {}
            }
            
            # Add files to generation folder
            for file_info in generation.files:
                file_path_parts = file_info["file_path"].split("/")
                current_level = file_tree["project_root"]["children"][gen_folder_name]["children"]
                
                # Build nested directory structure
                for i, part in enumerate(file_path_parts):
                    if i == len(file_path_parts) - 1:
                        # This is the file
                        current_level[part] = {
                            "type": "file",
                            "name": part,
                            "path": f"/{gen_folder_name}/{file_info['file_path']}",
                            "file_id": file_info["id"],
                            "file_type": file_info["file_type"],
                            "size_bytes": file_info["size_bytes"],
                            "content_hash": file_info["content_hash"],
                            "azure_path": file_info["azure_path"],
                            "created_at": file_info["created_at"],
                            "updated_at": file_info["updated_at"]
                        }
                    else:
                        # This is a directory
                        if part not in current_level:
                            current_level[part] = {
                                "type": "directory",
                                "name": part,
                                "path": f"/{gen_folder_name}/{'/'.join(file_path_parts[:i+1])}",
                                "children": {}
                            }
                        current_level = current_level[part]["children"]
        
        return ProjectFileTree(
            project_id=project_id,
            project_name=project.name,
            generations=generation_summaries,
            file_tree=file_tree,
            total_files=len(project.files),
            total_generations=len(generations),
            tree_generated_at=datetime.utcnow()
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get file tree for project {project_id}: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to retrieve project file tree: {str(e)}"
        )


@router.post(
    "/{project_id}/subscribe-updates",
    summary="Subscribe to project real-time updates",
    description="""
    Subscribe to real-time updates for a specific project.
    
    This endpoint triggers WebSocket subscription setup and returns
    connection information for the client to establish WebSocket connection.
    """,
    responses={
        200: {"description": "Successfully set up subscription"},
        401: {"description": "Authentication required"},
        403: {"description": "Access denied - project belongs to another user"},
        404: {"description": "Project not found", "model": ErrorResponse},
        500: {"description": "Internal server error", "model": ErrorResponse}
    }
)
async def subscribe_to_project_updates(
    project_id: str = Path(..., description="Project UUID"),
    db: AsyncSession = Depends(get_async_db),
    user_id: str = Depends(get_current_user_id),
    background_tasks: BackgroundTasks = None
):
    """
    Subscribe to real-time updates for a project.
    
    Args:
        project_id: Project UUID
        background_tasks: Background tasks for async operations
        db: Database session
        current_user: Authenticated user
        
    Returns:
        Subscription information and WebSocket connection details
    """
    try:
        # Verify project exists and user has access
        project_query = select(Project).filter(
            and_(
                Project.id == project_id,
                Project.user_id == user_id
            )
        )
        project_result = await db.execute(project_query)
        project = project_result.scalar_one_or_none()
        
        if not project:
            raise HTTPException(
                status_code=404,
                detail=f"Project {project_id} not found"
            )
        
        # Get WebSocket connection stats
        ws_stats = realtime_service.get_connection_stats()
        
        return {
            "status": "success",
            "message": f"Ready to subscribe to updates for project {project.name}",
            "data": {
                "project_id": project_id,
                "project_name": project.name,
                "websocket_endpoints": {
                    "project_updates": f"/api/v1/websocket/ws/project/{project_id}",
                    "dashboard_updates": f"/api/v1/websocket/dashboard/ws/project/{project_id}/dashboard",
                    "general_websocket": "/api/v1/websocket/ws"
                },
                "subscription_types": [
                    "generation_progress",
                    "file_created",
                    "project_updated",
                    "sync_status",
                    "dashboard_update"
                ],
                "current_connections": ws_stats.get("connections_by_user", {}).get(user_id, 0),
                "setup_at": datetime.utcnow()
            }
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to set up subscription for project {project_id}: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to set up project subscription: {str(e)}"
        )


@router.get(
    "/active-generations",
    response_model=List[ActiveGenerationSummary],
    summary="Get active generations across all projects",
    description="""
    Get all active (pending or in-progress) generations across all user projects.
    
    Useful for monitoring ongoing code generation activities and providing
    real-time updates on the dashboard.
    """,
    responses={
        200: {"description": "Successfully retrieved active generations"},
        401: {"description": "Authentication required"},
        500: {"description": "Internal server error", "model": ErrorResponse}
    }
)
async def get_active_generations(
    db: AsyncSession = Depends(get_async_db),
    user_id: str = Depends(get_current_user_id)
) -> List[ActiveGenerationSummary]:
    """
    Get all active generations for the user.
    
    Args:
        db: Database session
        current_user: Authenticated user
        
    Returns:
        List of active generation summaries
    """
    try:
        # Get active generations
        active_generations_query = select(CodeGeneration).filter(
            and_(
                CodeGeneration.user_id == user_id,
                CodeGeneration.status.in_([GenerationStatus.PENDING, GenerationStatus.IN_PROGRESS])
            )
        ).order_by(desc(CodeGeneration.created_at))
        active_generations_result = await db.execute(active_generations_query)
        active_generations = active_generations_result.scalars().all()
        
        # Build summaries
        summaries = []
        for generation in active_generations:
            project_query = select(Project).filter(Project.id == generation.project_id)
            project_result = await db.execute(project_query)
            project = project_result.scalar_one_or_none()
            if project:
                summary = ActiveGenerationSummary(
                    generation_id=generation.id,
                    project_id=generation.project_id,
                    project_name=project.name,
                    query=generation.query,
                    scenario=generation.scenario,
                    status=generation.status,
                    created_at=generation.created_at,
                    estimated_completion=None  # Would be calculated based on progress
                )
                summaries.append(summary)
        
        return summaries
        
    except Exception as e:
        logger.error(f"Failed to get active generations for user {user_id}: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to retrieve active generations: {str(e)}"
        )


@router.post(
    "/realtime-update",
    summary="Trigger real-time dashboard update",
    description="""
    Trigger a real-time update to all connected dashboard clients.
    
    This endpoint can be called by internal services when project
    status changes, generations complete, or other dashboard-relevant
    events occur.
    """,
    responses={
        200: {"description": "Successfully triggered real-time update"},
        401: {"description": "Authentication required"},
        500: {"description": "Internal server error", "model": ErrorResponse}
    }
)
async def trigger_realtime_dashboard_update(
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_async_db),
    user_id: str = Depends(get_current_user_id)
):
    """
    Trigger real-time dashboard update for the user.
    
    Args:
        background_tasks: Background tasks for async operations
        db: Database session
        current_user: Authenticated user
        
    Returns:
        Status of the real-time update trigger
    """
    try:
        # Get current dashboard data
        dashboard_data = await get_project_dashboard(
            include_archived=False,
            limit=20,
            db=db,
            user_id=user_id
        )
        
        # Prepare real-time update message
        update_message = {
            "event_type": "dashboard_refresh",
            "timestamp": datetime.utcnow().isoformat(),
            "data": {
                "total_projects": dashboard_data.total_projects,
                "total_active_generations": dashboard_data.total_active_generations,
                "websocket_connections": dashboard_data.websocket_connections,
                "projects_summary": [
                    {
                        "id": p.id,
                        "name": p.name,
                        "realtime_status": p.realtime_status,
                        "active_generation_count": p.active_generation_count,
                        "file_count": p.file_count,
                        "generation_count": p.generation_count,
                        "last_generation_status": p.last_generation_status
                    }
                    for p in dashboard_data.projects
                ],
                "active_generations_summary": [
                    {
                        "generation_id": g.generation_id,
                        "project_id": g.project_id,
                        "project_name": g.project_name,
                        "status": g.status,
                        "query_preview": g.query[:100] + "..." if len(g.query) > 100 else g.query
                    }
                    for g in dashboard_data.active_generations
                ]
            }
        }
        
        # Send real-time update to user's WebSocket connections
        sent_count = await realtime_service.websocket_manager.send_to_user(
            user_id, 
            update_message
        )
        
        return {
            "status": "success",
            "message": "Real-time dashboard update triggered",
            "data": {
                "user_id": user_id,
                "sessions_notified": sent_count,
                "projects_count": dashboard_data.total_projects,
                "active_generations_count": dashboard_data.total_active_generations,
                "update_timestamp": datetime.utcnow()
            }
        }
        
    except Exception as e:
        logger.error(f"Failed to trigger real-time dashboard update for user {user_id}: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to trigger real-time dashboard update: {str(e)}"
        )
