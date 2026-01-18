"""
Project Integration Schemas for Code Generation API.

This module defines enhanced request/response models that integrate project management
with the existing code generation system, maintaining backward compatibility.
"""

from typing import Dict, Any, Optional, List
from datetime import datetime
from pydantic import BaseModel, Field, field_validator

from app.api.v1.code_generation.models import (
    GenerateRequest as BaseGenerateRequest,
    GenerateResponse as BaseGenerateResponse,
    JobResultResponse as BaseJobResultResponse,
    GenerationScenario,
    JobStatus
)


class ProjectIntegrationRequest(BaseGenerateRequest):
    """
    Enhanced GenerateRequest with optional project integration fields.
    
    Extends the existing GenerateRequest to support automatic project creation
    and file management while maintaining full backward compatibility.
    """
    # Project integration fields (all optional for backward compatibility)
    project_id: Optional[str] = Field(
        None, 
        description="Existing project ID to associate generated code with",
        pattern=r'^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$'
    )
    project_name: Optional[str] = Field(
        None, 
        description="Name for new project (creates project if project_id not provided)",
        min_length=1,
        max_length=100
    )
    project_description: Optional[str] = Field(
        None,
        description="Description for new project (used only when creating new project)",
        max_length=500
    )
    save_to_project: bool = Field(
        True,
        description="Whether to save generated files to project storage (Azure File Share)"
    )
    
    @field_validator('project_name')
    @classmethod
    def validate_project_name(cls, v):
        """Validate project name format."""
        if v is not None:
            v = v.strip()
            if not v:
                raise ValueError('Project name cannot be empty or whitespace only')
            # Check for invalid characters
            invalid_chars = ['/', '\\', ':', '*', '?', '"', '<', '>', '|']
            if any(char in v for char in invalid_chars):
                raise ValueError(f'Project name cannot contain: {", ".join(invalid_chars)}')
        return v
    
    @field_validator('project_description')
    @classmethod
    def validate_project_description(cls, v):
        """Validate project description."""
        if v is not None:
            v = v.strip()
            if not v:
                return None  # Empty description is allowed
        return v
    
    class Config:
        """Pydantic configuration."""
        schema_extra = {
            "example": {
                "query": "Create an AWS VPC with public and private subnets",
                "scenario": "NEW_RESOURCE",
                "project_name": "aws-vpc-infrastructure",
                "project_description": "Infrastructure for AWS VPC with multi-AZ setup",
                "save_to_project": True,
                "repository_name": "terraform-aws-vpc",
                "provider_type": "claude",
                "temperature": 0.7
            }
        }


class ProjectInfo(BaseModel):
    """Project information included in responses."""
    project_id: str = Field(..., description="Project UUID")
    project_name: str = Field(..., description="Project name")
    project_description: Optional[str] = Field(None, description="Project description")
    azure_folder_path: str = Field(..., description="Azure File Share folder path")
    is_new_project: bool = Field(..., description="Whether this project was created during this request")


class GitHubStatus(BaseModel):
    """GitHub integration status for hybrid architecture."""
    pushed: bool = Field(..., description="Whether files were successfully pushed to GitHub")
    repo_url: Optional[str] = Field(None, description="GitHub repository URL if pushed")
    commit_sha: Optional[str] = Field(None, description="GitHub commit SHA if pushed")
    error: Optional[str] = Field(None, description="Error message if GitHub operation failed")


class FileInfo(BaseModel):
    """File information for generated files."""
    file_path: str = Field(..., description="Relative file path within project")
    azure_path: str = Field(..., description="Full Azure File Share path")
    file_type: str = Field(..., description="File extension/type")
    size_bytes: int = Field(..., description="File size in bytes")
    content_hash: str = Field(..., description="SHA-256 hash of file content")


class ProjectIntegrationResponse(BaseGenerateResponse):
    """
    Enhanced GenerateResponse with optional project information.
    
    Extends the existing GenerateResponse to include project details when
    project integration is used, maintaining backward compatibility.
    """
    # Project integration fields (only present when projects are used)
    project_info: Optional[ProjectInfo] = Field(
        None,
        description="Project information (only present when project integration is used)"
    )
    
    class Config:
        """Pydantic configuration."""
        schema_extra = {
            "example": {
                "job_id": "job_123456789",
                "status": "accepted",
                "message": "Code generation started successfully",
                "project_info": {
                    "project_id": "550e8400-e29b-41d4-a716-446655440000",
                    "project_name": "aws-vpc-infrastructure",
                    "project_description": "Infrastructure for AWS VPC with multi-AZ setup",
                    "azure_folder_path": "projects/550e8400-e29b-41d4-a716-446655440000",
                    "is_new_project": True
                }
            }
        }


class ProjectJobResultResponse(BaseJobResultResponse):
    """
    Enhanced JobResultResponse with project and file information.
    
    Extends the existing JobResultResponse to include project details and
    Azure File Share paths when project integration is used.
    """
    # Project integration fields (only present when projects are used)
    project_info: Optional[ProjectInfo] = Field(
        None,
        description="Project information (only present when project integration is used)"
    )
    generated_file_info: Optional[List[FileInfo]] = Field(
        None,
        description="Detailed information about generated files in Azure File Share"
    )
    generation_folder_path: Optional[str] = Field(
        None,
        description="Azure File Share folder path for this specific generation"
    )
    # Hybrid architecture fields
    azure_paths: Optional[List[str]] = Field(
        None,
        description="List of Azure File Share paths where files were saved"
    )
    github_status: Optional[GitHubStatus] = Field(
        None,
        description="GitHub integration status (only present when GitHub operations are attempted)"
    )
    
    class Config:
        """Pydantic configuration."""
        schema_extra = {
            "example": {
                "job_id": "job_123456789",
                "status": "completed",
                "generated_code": "# Legacy field for backward compatibility",
                "generated_files": {
                    "main.tf": "resource \"aws_vpc\" \"main\" { ... }",
                    "variables.tf": "variable \"vpc_cidr\" { ... }"
                },
                "success": True,
                "processing_time_ms": 2500.0,
                "project_info": {
                    "project_id": "550e8400-e29b-41d4-a716-446655440000",
                    "project_name": "aws-vpc-infrastructure",
                    "project_description": "Infrastructure for AWS VPC with multi-AZ setup",
                    "azure_folder_path": "projects/550e8400-e29b-41d4-a716-446655440000",
                    "is_new_project": False
                },
                "generated_file_info": [
                    {
                        "file_path": "main.tf",
                        "azure_path": "projects/550e8400-e29b-41d4-a716-446655440000/abc123def456/main.tf",
                        "file_type": ".tf",
                        "size_bytes": 1024,
                        "content_hash": "a1b2c3d4e5f6..."
                    }
                ],
                "generation_folder_path": "projects/550e8400-e29b-41d4-a716-446655440000/abc123def456"
            }
        }


# Backward compatibility aliases - these allow existing code to continue working
GenerateRequest = ProjectIntegrationRequest
GenerateResponse = ProjectIntegrationResponse
JobResultResponse = ProjectJobResultResponse


class ProjectCreationResult(BaseModel):
    """Result of automatic project creation during code generation."""
    project: ProjectInfo = Field(..., description="Created project information")
    created_folders: List[str] = Field(..., description="Azure File Share folders created")
    
    
class ProjectValidationError(BaseModel):
    """Error details for project validation failures."""
    field: str = Field(..., description="Field that failed validation")
    message: str = Field(..., description="Validation error message")
    code: str = Field(..., description="Error code for programmatic handling")


def create_backward_compatible_response(
    job_id: str,
    status: str,
    message: str,
    project_info: Optional[ProjectInfo] = None
) -> ProjectIntegrationResponse:
    """
    Create a backward-compatible response that includes project info only when needed.
    
    This helper function ensures that responses maintain backward compatibility
    by only including project information when it's actually used.
    """
    response_data = {
        "job_id": job_id,
        "status": status,
        "message": message
    }
    
    # Only include project_info if it's provided
    if project_info:
        response_data["project_info"] = project_info
    
    return ProjectIntegrationResponse(**response_data)


def create_backward_compatible_job_result(
    job_id: str,
    status: JobStatus,
    success: bool,
    generated_code: Optional[str] = None,
    generated_files: Optional[Dict[str, str]] = None,
    project_info: Optional[ProjectInfo] = None,
    generated_file_info: Optional[List[FileInfo]] = None,
    generation_folder_path: Optional[str] = None,
    azure_paths: Optional[List[str]] = None,
    github_status: Optional[GitHubStatus] = None,
    **kwargs
) -> ProjectJobResultResponse:
    """
    Create a backward-compatible job result response.
    
    This helper function ensures that job result responses maintain backward
    compatibility while optionally including enhanced project information.
    """
    response_data = {
        "job_id": job_id,
        "status": status,
        "success": success,
        **kwargs  # Include any additional fields like processing_time_ms, error_message, etc.
    }
    
    # Include legacy fields for backward compatibility
    if generated_code:
        response_data["generated_code"] = generated_code
    if generated_files:
        response_data["generated_files"] = generated_files
    
    # Only include project fields when they're provided
    if project_info:
        response_data["project_info"] = project_info
    if generated_file_info:
        response_data["generated_file_info"] = generated_file_info
    if generation_folder_path:
        response_data["generation_folder_path"] = generation_folder_path
    if azure_paths:
        response_data["azure_paths"] = azure_paths
    if github_status:
        response_data["github_status"] = github_status
    
    return ProjectJobResultResponse(**response_data)