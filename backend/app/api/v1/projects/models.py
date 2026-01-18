"""
Project API models for optional project management endpoints.

This module provides read-only response models for project and file information,
with comprehensive OpenAPI documentation for optional project management.
"""

from datetime import datetime
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field, ConfigDict
from enum import Enum


class ProjectStatus(str, Enum):
    """Project status enumeration."""

    ACTIVE = "active"
    ARCHIVED = "archived"
    DELETED = "deleted"


class FileType(str, Enum):
    """File type enumeration for generated files."""

    TERRAFORM = "terraform"
    TFVARS = "tfvars"
    JSON = "json"
    YAML = "yaml"
    OTHER = "other"


class ProjectSummaryResponse(BaseModel):
    """
    Summary response model for project listing.

    Provides essential project information for list views.
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
                "github_linked": True,
                "github_repo_id": 123456789,
                "github_repo_name": "my-terraform-project",
                "github_installation_id": 987654321,
                "last_github_sync": "2024-01-20T14:30:00Z",
            }
        },
    )

    id: str = Field(..., description="Unique project identifier (UUID)")
    name: str = Field(..., description="Project name")
    description: Optional[str] = Field(None, description="Project description")
    status: ProjectStatus = Field(..., description="Current project status")
    created_at: datetime = Field(..., description="Project creation timestamp")
    updated_at: datetime = Field(..., description="Last update timestamp")
    file_count: int = Field(..., description="Total number of files in project")
    total_size_bytes: int = Field(
        ..., description="Total size of all project files in bytes"
    )
    generation_count: int = Field(
        ..., description="Number of code generations for this project"
    )

    # Optional GitHub fields (included when include_github_info=true)
    github_linked: Optional[bool] = Field(
        None, description="Whether project is linked to GitHub"
    )
    github_repo_id: Optional[int] = Field(None, description="GitHub repository ID")
    github_repo_name: Optional[str] = Field(None, description="GitHub repository name")
    github_installation_id: Optional[int] = Field(
        None, description="GitHub App installation ID"
    )
    last_github_sync: Optional[datetime] = Field(
        None, description="Last GitHub sync timestamp"
    )


class ProjectFileResponse(BaseModel):
    """
    Response model for project file information.

    Provides detailed file metadata for project files.
    """

    model_config = ConfigDict(
        from_attributes=True,
        json_schema_extra={
            "example": {
                "id": 123,
                "file_path": "main.tf",
                "azure_path": "/projects/550e8400-e29b-41d4-a716-446655440000/gen_abc123/main.tf",
                "file_type": "tf",
                "size_bytes": 2048,
                "content_hash": "a1b2c3d4e5f6...",
                "created_at": "2024-01-15T10:30:00Z",
                "updated_at": "2024-01-15T10:30:00Z",
            }
        },
    )

    id: int = Field(..., description="File record ID")
    file_path: str = Field(..., description="Relative file path within project")
    azure_path: str = Field(..., description="Full Azure File Share path")
    file_type: str = Field(..., description="File type/extension")
    size_bytes: int = Field(..., description="File size in bytes")
    content_hash: str = Field(..., description="SHA-256 hash of file content")
    created_at: datetime = Field(..., description="File creation timestamp")
    updated_at: datetime = Field(..., description="Last modification timestamp")


class CodeGenerationResponse(BaseModel):
    """
    Response model for code generation information.

    Provides details about individual code generations within a project.
    """

    model_config = ConfigDict(
        from_attributes=True,
        json_schema_extra={
            "example": {
                "id": "gen_550e8400-e29b-41d4-a716-446655440000",
                "query": "Create an AWS VPC with public and private subnets",
                "scenario": "NEW_RESOURCE",
                "status": "completed",
                "generation_hash": "abc123def456",
                "created_at": "2024-01-15T10:30:00Z",
                "file_count": 3,
            }
        },
    )

    id: str = Field(..., description="Generation job ID")
    query: str = Field(..., description="Original generation query")
    scenario: str = Field(..., description="Generation scenario type")
    status: str = Field(..., description="Generation status")
    generation_hash: str = Field(..., description="Unique hash for this generation")
    created_at: datetime = Field(..., description="Generation timestamp")
    file_count: int = Field(..., description="Number of files generated")


class ProjectDetailResponse(BaseModel):
    """
    Detailed response model for individual project information.

    Provides comprehensive project details including files and generations.
    """

    model_config = ConfigDict(
        from_attributes=True,
        json_schema_extra={
            "example": {
                "id": "550e8400-e29b-41d4-a716-446655440000",
                "name": "AWS Infrastructure",
                "description": "Main AWS infrastructure project",
                "status": "active",
                "azure_folder_path": "/projects/550e8400-e29b-41d4-a716-446655440000",
                "created_at": "2024-01-15T10:30:00Z",
                "updated_at": "2024-01-20T14:45:00Z",
                "files": [],
                "file_count": 12,
                "total_size_bytes": 45678,
                "generations": [],
                "generation_count": 5,
                "insights": {
                    "complexity_score": 7.5,
                    "resource_types": ["vpc", "subnet", "security_group"],
                    "recommendations": [
                        "Consider adding monitoring",
                        "Review security groups",
                    ],
                },
            }
        },
    )

    id: str = Field(..., description="Unique project identifier (UUID)")
    name: str = Field(..., description="Project name")
    description: Optional[str] = Field(None, description="Project description")
    status: ProjectStatus = Field(..., description="Current project status")
    azure_folder_path: str = Field(..., description="Azure File Share folder path")
    created_at: datetime = Field(..., description="Project creation timestamp")
    updated_at: datetime = Field(..., description="Last update timestamp")

    # File information
    files: List[ProjectFileResponse] = Field(
        default_factory=list, description="List of project files"
    )
    file_count: int = Field(..., description="Total number of files")
    total_size_bytes: int = Field(..., description="Total size of all files in bytes")

    # Generation information
    generations: List[CodeGenerationResponse] = Field(
        default_factory=list, description="List of code generations"
    )
    generation_count: int = Field(..., description="Number of code generations")

    # Analytics (populated by Anthropic insights)
    insights: Optional[Dict[str, Any]] = Field(
        None, description="AI-generated project insights and analytics"
    )


class FileContentResponse(BaseModel):
    """
    Response model for file content retrieval.

    Provides file content along with metadata and AI-generated insights.
    """

    model_config = ConfigDict(
        from_attributes=True,
        json_schema_extra={
            "example": {
                "file_info": {
                    "id": 123,
                    "file_path": "main.tf",
                    "azure_path": "/projects/550e8400-e29b-41d4-a716-446655440000/gen_abc123/main.tf",
                    "file_type": "tf",
                    "size_bytes": 2048,
                    "content_hash": "a1b2c3d4e5f6...",
                    "created_at": "2024-01-15T10:30:00Z",
                    "updated_at": "2024-01-15T10:30:00Z",
                },
                "content": 'resource "aws_vpc" "main" {\n  cidr_block = "10.0.0.0/16"\n}',
                "content_type": "text/plain",
                "encoding": "utf-8",
                "analysis": {
                    "resource_count": 1,
                    "complexity": "low",
                    "best_practices": ["Uses standard CIDR block"],
                    "suggestions": ["Consider adding tags"],
                },
            }
        },
    )

    file_info: ProjectFileResponse = Field(..., description="File metadata")
    content: str = Field(..., description="File content")
    content_type: str = Field(..., description="MIME type of the content")
    encoding: str = Field(default="utf-8", description="Content encoding")

    # AI-generated insights about the file content
    analysis: Optional[Dict[str, Any]] = Field(
        None, description="AI-generated code analysis and insights"
    )


class ProjectListResponse(BaseModel):
    """
    Response model for project listing with pagination.

    Provides paginated list of projects with metadata.
    """

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "projects": [],
                "total_count": 25,
                "page": 1,
                "page_size": 10,
                "has_next": True,
                "has_previous": False,
            }
        }
    )

    projects: List[ProjectSummaryResponse] = Field(..., description="List of projects")
    total_count: int = Field(..., description="Total number of projects")
    page: int = Field(..., description="Current page number")
    page_size: int = Field(..., description="Number of items per page")
    has_next: bool = Field(..., description="Whether there are more pages")
    has_previous: bool = Field(..., description="Whether there are previous pages")


class ProjectInsightsResponse(BaseModel):
    """
    Response model for AI-generated project insights and analytics.

    Provides intelligent analysis of project structure and content.
    """

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "project_id": "550e8400-e29b-41d4-a716-446655440000",
                "generated_at": "2024-01-20T15:30:00Z",
                "complexity_analysis": {
                    "overall_score": 7.5,
                    "file_complexity": {"main.tf": 6.0, "variables.tf": 3.0},
                    "resource_dependencies": 12,
                },
                "resource_analysis": {
                    "total_resources": 15,
                    "resource_types": ["aws_vpc", "aws_subnet", "aws_security_group"],
                    "estimated_cost": "medium",
                },
                "security_analysis": {
                    "security_score": 8.0,
                    "encrypted_resources": 10,
                    "public_resources": 2,
                },
                "recommendations": [
                    "Consider adding monitoring for EC2 instances",
                    "Review security group rules for overly permissive access",
                ],
                "best_practices": [
                    "Uses consistent naming conventions",
                    "Properly tags resources",
                ],
                "potential_issues": [
                    "Security group allows 0.0.0.0/0 access on port 22"
                ],
                "metrics": {
                    "maintainability_score": 8.5,
                    "security_score": 7.0,
                    "cost_optimization_score": 6.5,
                },
            }
        }
    )

    project_id: str = Field(..., description="Project identifier")
    generated_at: datetime = Field(..., description="When insights were generated")

    # Code analysis
    complexity_analysis: Dict[str, Any] = Field(
        ..., description="Code complexity metrics"
    )
    resource_analysis: Dict[str, Any] = Field(
        ..., description="Infrastructure resource analysis"
    )
    security_analysis: Dict[str, Any] = Field(
        ..., description="Security best practices analysis"
    )

    # Recommendations
    recommendations: List[str] = Field(
        ..., description="AI-generated improvement recommendations"
    )
    best_practices: List[str] = Field(..., description="Best practices being followed")
    potential_issues: List[str] = Field(..., description="Potential issues identified")

    # Metrics
    metrics: Dict[str, float] = Field(..., description="Quantitative project metrics")


class FileTreeNodeResponse(BaseModel):
    """
    Response model for file tree node structure.

    Represents a hierarchical file tree with generation grouping.
    """

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "name": "main.tf",
                "path": "terraform/main.tf",
                "type": "file",
                "size_bytes": 2048,
                "file_type": "tf",
                "generation_id": "gen_123",
                "generation_hash": "abc123def",
                "children": [],
                "metadata": {
                    "content_hash": "a1b2c3...",
                    "created_at": "2024-01-15T10:30:00Z",
                },
            }
        }
    )

    name: str = Field(..., description="Node name (filename or directory name)")
    path: str = Field(..., description="Full path from project root")
    type: str = Field(..., description="Node type: 'file' or 'directory'")
    size_bytes: Optional[int] = Field(
        None, description="File size in bytes (files only)"
    )
    file_type: Optional[str] = Field(
        None, description="File extension/type (files only)"
    )
    generation_id: Optional[str] = Field(None, description="Associated generation ID")
    generation_hash: Optional[str] = Field(
        None, description="Generation hash for grouping"
    )
    children: Optional[List["FileTreeNodeResponse"]] = Field(
        None, description="Child nodes (directories only)"
    )
    metadata: Optional[Dict[str, Any]] = Field(None, description="Additional metadata")


class SyntaxHighlightedContentResponse(BaseModel):
    """
    Response model for syntax highlighted file content.

    Provides file content with syntax highlighting and analysis.
    """

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "content": 'resource "aws_vpc" "main" {\n  cidr_block = "10.0.0.0/16"\n}',
                "highlighted_content": '<span class="keyword">resource</span> <span class="string">"aws_vpc"</span>...',
                "language": "terraform",
                "line_count": 3,
                "tokens": [{"type": "keyword", "value": "resource", "line": 1}],
                "syntax_errors": [],
            }
        }
    )

    content: str = Field(..., description="Original file content")
    highlighted_content: str = Field(
        ..., description="Syntax highlighted content (HTML)"
    )
    language: str = Field(..., description="Detected programming language")
    line_count: int = Field(..., description="Number of lines in file")
    tokens: Optional[List[Dict[str, Any]]] = Field(
        None, description="Parsed syntax tokens"
    )
    syntax_errors: Optional[List[str]] = Field(None, description="Syntax errors found")


class FileSearchMatchResponse(BaseModel):
    """
    Response model for individual search match.

    Represents a single match within a file.
    """

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "line_number": 15,
                "line_content": '  cidr_block = "10.0.0.0/16"',
                "context": [
                    'resource "aws_vpc" "main" {',
                    '  cidr_block = "10.0.0.0/16"',
                    "}",
                ],
                "match_positions": [[15, 27]],
            }
        }
    )

    line_number: int = Field(..., description="Line number where match was found")
    line_content: str = Field(..., description="Content of the matching line")
    context: List[str] = Field(..., description="Surrounding lines for context")
    match_positions: List[List[int]] = Field(
        ..., description="Character positions of matches [start, end]"
    )


class FileSearchResultResponse(BaseModel):
    """
    Response model for file search results.

    Represents search results for a single file.
    """

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "file_path": "terraform/main.tf",
                "file_type": "tf",
                "size_bytes": 2048,
                "generation_id": "gen_123",
                "matches": [],
                "score": 8.5,
            }
        }
    )

    file_path: str = Field(..., description="File path within project")
    file_type: str = Field(..., description="File type/extension")
    size_bytes: int = Field(..., description="File size in bytes")
    generation_id: Optional[str] = Field(None, description="Associated generation ID")
    matches: List[FileSearchMatchResponse] = Field(
        ..., description="Search matches within file"
    )
    score: float = Field(..., description="Relevance score for ranking")


class EnhancedFileContentResponse(BaseModel):
    """
    Enhanced response model for file content with syntax highlighting.

    Combines file metadata, content, and syntax highlighting.
    """

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "file_info": {
                    "id": 123,
                    "file_path": "main.tf",
                    "file_type": "tf",
                    "size_bytes": 2048,
                },
                "syntax_content": {
                    "content": 'resource "aws_vpc" "main" {...}',
                    "highlighted_content": '<span class="keyword">resource</span>...',
                    "language": "terraform",
                    "line_count": 25,
                },
                "mime_type": "text/x-terraform",
                "download_url": "/api/v1/projects/123/files/main.tf/download",
            }
        }
    )

    file_info: ProjectFileResponse = Field(..., description="File metadata")
    syntax_content: SyntaxHighlightedContentResponse = Field(
        ..., description="Syntax highlighted content"
    )
    mime_type: str = Field(..., description="MIME type for proper handling")
    download_url: str = Field(..., description="Direct download URL")


class ProjectFileTreeResponse(BaseModel):
    """
    Response model for project file tree structure.

    Provides hierarchical view of project files with generation grouping.
    """

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "project_id": "550e8400-e29b-41d4-a716-446655440000",
                "tree": {
                    "name": "project",
                    "path": "",
                    "type": "directory",
                    "children": [],
                },
                "total_files": 25,
                "total_size_bytes": 102400,
                "generation_count": 5,
                "file_types": {"tf": 15, "tfvars": 5, "json": 3, "yaml": 2},
            }
        }
    )

    project_id: str = Field(..., description="Project identifier")
    tree: FileTreeNodeResponse = Field(..., description="Root node of file tree")
    total_files: int = Field(..., description="Total number of files")
    total_size_bytes: int = Field(..., description="Total size of all files")
    generation_count: int = Field(..., description="Number of generations")
    file_types: Dict[str, int] = Field(..., description="Count of files by type")


class FileSearchResponse(BaseModel):
    """
    Response model for file search operation.

    Provides search results with pagination and filtering info.
    """

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "query": "vpc",
                "results": [],
                "total_matches": 15,
                "file_types_searched": ["tf", "tfvars"],
                "search_time_ms": 125,
            }
        }
    )

    query: str = Field(..., description="Search query used")
    results: List[FileSearchResultResponse] = Field(..., description="Search results")
    total_matches: int = Field(..., description="Total number of matches found")
    file_types_searched: Optional[List[str]] = Field(
        None, description="File types included in search"
    )
    search_time_ms: int = Field(
        ..., description="Search execution time in milliseconds"
    )


class ProjectGenerationsResponse(BaseModel):
    """
    Response model for project generations list.

    Provides list of generation IDs for a specific project.
    """

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "project_id": "550e8400-e29b-41d4-a716-446655440000",
                "generation_ids": [
                    "gen_550e8400-e29b-41d4-a716-446655440001",
                    "gen_550e8400-e29b-41d4-a716-446655440002",
                    "gen_550e8400-e29b-41d4-a716-446655440003",
                ],
                "total_count": 3,
            }
        }
    )

    project_id: str = Field(..., description="Project identifier")
    generation_ids: List[str] = Field(
        ..., description="List of generation IDs for the project"
    )
    total_count: int = Field(..., description="Total number of generations")


class ErrorResponse(BaseModel):
    """
    Standard error response model.

    Provides consistent error information across all endpoints.
    """

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "error": "ProjectNotFound",
                "message": "Project with ID 550e8400-e29b-41d4-a716-446655440000 not found",
                "details": {"project_id": "550e8400-e29b-41d4-a716-446655440000"},
                "timestamp": "2024-01-20T15:30:00Z",
            }
        }
    )

    error: str = Field(..., description="Error type")
    message: str = Field(..., description="Human-readable error message")
    details: Optional[Dict[str, Any]] = Field(
        None, description="Additional error details"
    )
    timestamp: datetime = Field(..., description="Error timestamp")


# Update forward references for recursive models
FileTreeNodeResponse.model_rebuild()
