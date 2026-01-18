"""
Enhanced project dashboard models with real-time status information.

This module provides response models for the enhanced project dashboard
with real-time updates, file tree structures, and generation monitoring.
"""

from datetime import datetime
from typing import List, Optional, Dict, Any, Union
from pydantic import BaseModel, Field, ConfigDict
from enum import Enum

from app.api.v1.projects.models import ProjectStatus


class RealtimeStatus(str, Enum):
    """Real-time status enumeration for projects."""
    IDLE = "idle"
    PENDING = "pending"
    GENERATING = "generating"
    SYNCING = "syncing"
    ERROR = "error"


class GenerationStatus(str, Enum):
    """Generation status enumeration."""
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class ProjectWithRealtimeStatus(BaseModel):
    """
    Project summary with real-time status information.
    
    Extends basic project information with real-time generation status,
    active generation counts, and WebSocket connection details.
    """
    model_config = ConfigDict(
        from_attributes=True,
        json_schema_extra={
            "example": {
                "id": "550e8400-e29b-41d4-a716-446655440000",
                "name": "AWS Infrastructure",
                "description": "Main AWS infrastructure project",
                "status": "active",
                "created_at": "2024-01-15T10:30:00Z",
                "updated_at": "2024-01-20T14:45:00Z",
                "file_count": 12,
                "total_size_bytes": 45678,
                "generation_count": 5,
                "realtime_status": "generating",
                "active_generation_count": 2,
                "last_generation_at": "2024-01-20T14:30:00Z",
                "last_generation_status": "in_progress"
            }
        }
    )
    
    # Basic project information
    id: str = Field(..., description="Unique project identifier (UUID)")
    name: str = Field(..., description="Project name")
    description: Optional[str] = Field(None, description="Project description")
    status: ProjectStatus = Field(..., description="Current project status")
    created_at: datetime = Field(..., description="Project creation timestamp")
    updated_at: datetime = Field(..., description="Last update timestamp")
    
    # File and generation statistics
    file_count: int = Field(..., description="Total number of files in project")
    total_size_bytes: int = Field(..., description="Total size of all project files in bytes")
    generation_count: int = Field(..., description="Total number of code generations")
    
    # Real-time status information
    realtime_status: RealtimeStatus = Field(..., description="Current real-time status")
    active_generation_count: int = Field(..., description="Number of active (pending/in-progress) generations")
    last_generation_at: Optional[datetime] = Field(None, description="Timestamp of most recent generation")
    last_generation_status: Optional[GenerationStatus] = Field(None, description="Status of most recent generation")


class GenerationSummary(BaseModel):
    """
    Summary information for a code generation within a project.
    
    Provides essential generation details for file tree organization
    and dashboard display.
    """
    model_config = ConfigDict(
        from_attributes=True,
        json_schema_extra={
            "example": {
                "generation_id": "gen_550e8400-e29b-41d4-a716-446655440000",
                "query": "Create an AWS VPC with public and private subnets",
                "scenario": "NEW_RESOURCE",
                "status": "completed",
                "generation_hash": "abc123def456",
                "created_at": "2024-01-15T10:30:00Z",
                "file_count": 3,
                "files": []
            }
        }
    )
    
    generation_id: str = Field(..., description="Generation job ID")
    query: str = Field(..., description="Original generation query")
    scenario: str = Field(..., description="Generation scenario type")
    status: GenerationStatus = Field(..., description="Generation status")
    generation_hash: str = Field(..., description="Unique hash for this generation")
    created_at: datetime = Field(..., description="Generation timestamp")
    file_count: int = Field(..., description="Number of files generated")
    files: List[Dict[str, Any]] = Field(default_factory=list, description="List of generated files")


class ActiveGenerationSummary(BaseModel):
    """
    Summary for active (pending or in-progress) generations.
    
    Used for dashboard monitoring of ongoing generation activities.
    """
    model_config = ConfigDict(
        from_attributes=True,
        json_schema_extra={
            "example": {
                "generation_id": "gen_550e8400-e29b-41d4-a716-446655440000",
                "project_id": "550e8400-e29b-41d4-a716-446655440000",
                "project_name": "AWS Infrastructure",
                "query": "Create an AWS VPC with public and private subnets",
                "scenario": "NEW_RESOURCE",
                "status": "in_progress",
                "created_at": "2024-01-20T14:30:00Z",
                "estimated_completion": "2024-01-20T14:35:00Z"
            }
        }
    )
    
    generation_id: str = Field(..., description="Generation job ID")
    project_id: str = Field(..., description="Project ID")
    project_name: str = Field(..., description="Project name")
    query: str = Field(..., description="Generation query")
    scenario: str = Field(..., description="Generation scenario")
    status: GenerationStatus = Field(..., description="Current generation status")
    created_at: datetime = Field(..., description="Generation start time")
    estimated_completion: Optional[datetime] = Field(None, description="Estimated completion time")


class ProjectFileTree(BaseModel):
    """
    Hierarchical file tree structure for a project.
    
    Organizes files by generation sessions and provides a tree view
    of the project structure with metadata for each file and directory.
    """
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "project_id": "550e8400-e29b-41d4-a716-446655440000",
                "project_name": "AWS Infrastructure",
                "generations": [],
                "file_tree": {
                    "project_root": {
                        "type": "directory",
                        "name": "AWS Infrastructure",
                        "path": "/",
                        "children": {
                            "generation_abc123": {
                                "type": "directory",
                                "name": "Generation: Create VPC...",
                                "path": "/generation_abc123",
                                "generation_id": "gen_123",
                                "children": {
                                    "main.tf": {
                                        "type": "file",
                                        "name": "main.tf",
                                        "path": "/generation_abc123/main.tf",
                                        "file_type": ".tf",
                                        "size_bytes": 2048
                                    }
                                }
                            }
                        }
                    }
                },
                "total_files": 12,
                "total_generations": 3,
                "tree_generated_at": "2024-01-20T15:00:00Z"
            }
        }
    )
    
    project_id: str = Field(..., description="Project ID")
    project_name: str = Field(..., description="Project name")
    generations: List[GenerationSummary] = Field(..., description="List of generations in the project")
    file_tree: Dict[str, Any] = Field(..., description="Hierarchical file tree structure")
    total_files: int = Field(..., description="Total number of files in project")
    total_generations: int = Field(..., description="Total number of generations")
    tree_generated_at: datetime = Field(..., description="When the tree was generated")


class ProjectDashboardResponse(BaseModel):
    """
    Enhanced project dashboard response with real-time information.
    
    Provides comprehensive dashboard data including project summaries,
    active generations, and WebSocket connection information.
    """
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "projects": [],
                "active_generations": [],
                "total_projects": 5,
                "total_active_generations": 2,
                "websocket_connections": 1,
                "dashboard_generated_at": "2024-01-20T15:00:00Z"
            }
        }
    )
    
    projects: List[ProjectWithRealtimeStatus] = Field(..., description="List of projects with real-time status")
    active_generations: List[ActiveGenerationSummary] = Field(..., description="List of active generations")
    total_projects: int = Field(..., description="Total number of projects")
    total_active_generations: int = Field(..., description="Total number of active generations")
    websocket_connections: int = Field(..., description="Number of active WebSocket connections for user")
    dashboard_generated_at: datetime = Field(..., description="When the dashboard data was generated")


class ProjectListWithRealtimeResponse(BaseModel):
    """
    Project list response with real-time status and pagination.
    
    Extends the basic project list with real-time status information
    and active generation monitoring.
    """
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "projects": [],
                "active_generations": [],
                "total_count": 25,
                "page": 1,
                "page_size": 10,
                "has_next": True,
                "has_previous": False,
                "realtime_summary": {
                    "total_active_generations": 3,
                    "projects_with_activity": 2,
                    "websocket_connections": 1
                }
            }
        }
    )
    
    projects: List[ProjectWithRealtimeStatus] = Field(..., description="List of projects with real-time status")
    active_generations: List[ActiveGenerationSummary] = Field(..., description="Active generations across all projects")
    total_count: int = Field(..., description="Total number of projects")
    page: int = Field(..., description="Current page number")
    page_size: int = Field(..., description="Number of items per page")
    has_next: bool = Field(..., description="Whether there are more pages")
    has_previous: bool = Field(..., description="Whether there are previous pages")
    realtime_summary: Dict[str, Any] = Field(..., description="Real-time activity summary")


class WebSocketSubscriptionInfo(BaseModel):
    """
    Information about WebSocket subscription setup.
    
    Provides details needed for clients to establish WebSocket connections
    for real-time updates.
    """
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "project_id": "550e8400-e29b-41d4-a716-446655440000",
                "project_name": "AWS Infrastructure",
                "websocket_endpoint": "/api/v1/websocket/ws/project/550e8400-e29b-41d4-a716-446655440000",
                "subscription_types": [
                    "generation_progress",
                    "file_created",
                    "project_updated",
                    "sync_status"
                ],
                "current_connections": 1,
                "setup_at": "2024-01-20T15:00:00Z"
            }
        }
    )
    
    project_id: str = Field(..., description="Project ID")
    project_name: str = Field(..., description="Project name")
    websocket_endpoint: str = Field(..., description="WebSocket endpoint URL")
    subscription_types: List[str] = Field(..., description="Available subscription event types")
    current_connections: int = Field(..., description="Current number of WebSocket connections")
    setup_at: datetime = Field(..., description="When subscription was set up")


class RealtimeEventMessage(BaseModel):
    """
    Real-time event message structure for WebSocket communication.
    
    Standardized format for all real-time events sent through WebSocket
    connections for project updates.
    """
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "event_type": "generation_progress",
                "timestamp": "2024-01-20T15:00:00Z",
                "project_id": "550e8400-e29b-41d4-a716-446655440000",
                "data": {
                    "generation_id": "gen_123",
                    "status": "in_progress",
                    "progress_percentage": 75,
                    "current_step": "Generating Terraform files",
                    "files_generated": ["main.tf", "variables.tf"]
                }
            }
        }
    )
    
    event_type: str = Field(..., description="Type of real-time event")
    timestamp: datetime = Field(..., description="Event timestamp")
    project_id: str = Field(..., description="Associated project ID")
    data: Dict[str, Any] = Field(..., description="Event-specific data")


class ErrorResponse(BaseModel):
    """
    Standard error response model for dashboard endpoints.
    
    Provides consistent error information across all dashboard endpoints.
    """
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "error": "ProjectNotFound",
                "message": "Project with ID 550e8400-e29b-41d4-a716-446655440000 not found",
                "details": {"project_id": "550e8400-e29b-41d4-a716-446655440000"},
                "timestamp": "2024-01-20T15:30:00Z"
            }
        }
    )
    
    error: str = Field(..., description="Error type")
    message: str = Field(..., description="Human-readable error message")
    details: Optional[Dict[str, Any]] = Field(None, description="Additional error details")
    timestamp: datetime = Field(..., description="Error timestamp")


# Helper models for file tree structure
class FileTreeNode(BaseModel):
    """
    Individual node in the file tree structure.
    
    Can represent either a file or directory with appropriate metadata.
    """
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "type": "file",
                "name": "main.tf",
                "path": "/generation_abc123/main.tf",
                "file_id": 123,
                "file_type": ".tf",
                "size_bytes": 2048,
                "content_hash": "a1b2c3d4e5f6...",
                "azure_path": "/projects/550e8400-e29b-41d4-a716-446655440000/abc123/main.tf",
                "created_at": "2024-01-15T10:30:00Z",
                "updated_at": "2024-01-15T10:30:00Z"
            }
        }
    )
    
    type: str = Field(..., description="Node type: 'file' or 'directory'")
    name: str = Field(..., description="File or directory name")
    path: str = Field(..., description="Full path from project root")
    
    # File-specific fields (only present for files)
    file_id: Optional[int] = Field(None, description="Database file ID")
    file_type: Optional[str] = Field(None, description="File extension/type")
    size_bytes: Optional[int] = Field(None, description="File size in bytes")
    content_hash: Optional[str] = Field(None, description="SHA-256 hash of file content")
    azure_path: Optional[str] = Field(None, description="Azure File Share path")
    created_at: Optional[datetime] = Field(None, description="File creation timestamp")
    updated_at: Optional[datetime] = Field(None, description="File modification timestamp")
    
    # Directory-specific fields (only present for directories)
    generation_id: Optional[str] = Field(None, description="Associated generation ID for generation directories")
    generation_status: Optional[GenerationStatus] = Field(None, description="Generation status for generation directories")
    children: Optional[Dict[str, "FileTreeNode"]] = Field(None, description="Child nodes for directories")


# Update forward reference
FileTreeNode.model_rebuild()