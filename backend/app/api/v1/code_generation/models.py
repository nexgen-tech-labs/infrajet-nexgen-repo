"""
Pydantic models for Code Generation API.

This module defines request/response models for the code generation endpoints,
including validation, error handling, and proper typing.
"""

from typing import Dict, Any, Optional, List
from datetime import datetime
from enum import Enum
from pydantic import BaseModel, Field, validator


class GenerationScenario(str, Enum):
    """Generation scenario types."""
    NEW_RESOURCE = "NEW_RESOURCE"
    MODIFY_RESOURCE = "MODIFY_RESOURCE"
    NEW_MODULE = "NEW_MODULE"
    NEW_VARIABLES = "NEW_VARIABLES"
    NEW_OUTPUTS = "NEW_OUTPUTS"


class JobStatus(str, Enum):
    """Job status enumeration."""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class GenerateRequest(BaseModel):
    """Request model for code generation."""
    query: str = Field(..., description="User's code generation request", min_length=1, max_length=1000)
    scenario: GenerationScenario = Field(GenerationScenario.NEW_RESOURCE, description="Type of generation scenario")
    repository_name: Optional[str] = Field(None, description="Optional repository context")
    existing_code: Optional[str] = Field(None, description="Optional existing code to modify")
    target_file_path: Optional[str] = Field(None, description="Optional target file path")
    provider_type: Optional[str] = Field(None, description="LLM provider type")
    temperature: Optional[float] = Field(None, description="Generation temperature", ge=0.0, le=2.0)
    max_tokens: Optional[int] = Field(None, description="Maximum tokens to generate", ge=1, le=100000)
    
    # Project integration fields
    project_id: Optional[str] = Field(None, description="Existing project ID for file storage")
    project_name: Optional[str] = Field(None, description="New project name for automatic project creation")
    project_description: Optional[str] = Field(None, description="Project description")
    save_to_project: bool = Field(True, description="Whether to save generated files to project storage")

    @validator('query')
    def validate_query(cls, v):
        if not v.strip():
            raise ValueError('Query cannot be empty or whitespace only')
        return v.strip()


class GenerateResponse(BaseModel):
    """Response model for code generation."""
    job_id: str = Field(..., description="Unique job identifier")
    status: str = Field(..., description="Job status")
    message: str = Field(..., description="Response message")


class JobStatusResponse(BaseModel):
    """Response model for job status."""
    job_id: str = Field(..., description="Job ID")
    status: JobStatus = Field(..., description="Current job status")
    created_at: datetime = Field(..., description="Job creation timestamp")
    started_at: Optional[datetime] = Field(None, description="Job start timestamp")
    completed_at: Optional[datetime] = Field(None, description="Job completion timestamp")
    progress: Dict[str, Any] = Field(default_factory=dict, description="Job progress information")
    error_message: Optional[str] = Field(None, description="Error message if failed")
    generated_code: Optional[str] = Field(None, description="Generated code if completed (legacy)")
    generated_files: Optional[Dict[str, str]] = Field(None, description="Generated files if completed")
    processing_time_ms: Optional[float] = Field(None, description="Processing time in milliseconds")
    success: Optional[bool] = Field(None, description="Whether the job was successful")


class JobResultResponse(BaseModel):
    """Response model for job result with diff."""
    job_id: str = Field(..., description="Job ID")
    status: JobStatus = Field(..., description="Job status")
    generated_code: Optional[str] = Field(None, description="Generated Terraform code (legacy)")
    generated_files: Optional[Dict[str, str]] = Field(None, description="Generated Terraform files")
    diff_content: Optional[str] = Field(None, description="Diff content if applicable")
    additions: Optional[int] = Field(None, description="Number of additions in diff")
    deletions: Optional[int] = Field(None, description="Number of deletions in diff")
    changes: Optional[int] = Field(None, description="Total changes in diff")
    processing_time_ms: Optional[float] = Field(None, description="Processing time")
    success: bool = Field(..., description="Whether generation was successful")
    error_message: Optional[str] = Field(None, description="Error message if failed")


class ValidateRequest(BaseModel):
    """Request model for code validation."""
    code: str = Field(..., description="Terraform code to validate", min_length=1)
    file_path: Optional[str] = Field(None, description="Optional file path for context")
    strict_mode: bool = Field(False, description="Enable strict validation rules")


class ValidationIssue(BaseModel):
    """Model for validation issues."""
    error_type: str = Field(..., description="Type of validation error")
    severity: str = Field(..., description="Severity level")
    message: str = Field(..., description="Error message")
    line_number: Optional[int] = Field(None, description="Line number where issue occurs")
    column_number: Optional[int] = Field(None, description="Column number where issue occurs")
    context: Optional[str] = Field(None, description="Context around the issue")
    suggestion: Optional[str] = Field(None, description="Suggested fix")
    rule_id: Optional[str] = Field(None, description="Validation rule identifier")


class ValidateResponse(BaseModel):
    """Response model for code validation."""
    is_valid: bool = Field(..., description="Whether the code is valid")
    issues: List[ValidationIssue] = Field(default_factory=list, description="List of validation issues")
    processing_time_ms: float = Field(..., description="Processing time in milliseconds")
    total_issues: int = Field(..., description="Total number of issues")
    errors_count: int = Field(..., description="Number of errors")
    warnings_count: int = Field(..., description="Number of warnings")
    info_count: int = Field(..., description="Number of info messages")


class DiffRequest(BaseModel):
    """Request model for diff generation."""
    source_content: str = Field(..., description="Source content for diff")
    target_content: str = Field(..., description="Target content for diff")
    source_name: str = Field("source", description="Name for source content")
    target_name: str = Field("target", description="Name for target content")
    context_lines: int = Field(3, description="Number of context lines", ge=0, le=10)
    ignore_whitespace: bool = Field(False, description="Ignore whitespace differences")
    terraform_aware: bool = Field(True, description="Use Terraform-aware diff formatting")


class DiffResponse(BaseModel):
    """Response model for diff generation."""
    diff_content: str = Field(..., description="Generated diff content")
    additions: int = Field(..., description="Number of additions")
    deletions: int = Field(..., description="Number of deletions")
    changes: int = Field(..., description="Total number of changes")
    has_changes: bool = Field(..., description="Whether there are any changes")
    source_hash: str = Field(..., description="Hash of source content")
    target_hash: str = Field(..., description="Hash of target content")
    processing_time_ms: float = Field(..., description="Processing time in milliseconds")


class HealthResponse(BaseModel):
    """Response model for health check."""
    status: str = Field(..., description="Overall health status")
    timestamp: datetime = Field(..., description="Health check timestamp")
    version: str = Field(..., description="API version")
    components: Dict[str, Any] = Field(..., description="Component health status")
    job_stats: Dict[str, Any] = Field(..., description="Job processing statistics")
    configuration: Dict[str, Any] = Field(..., description="Configuration status")


class MetricsResponse(BaseModel):
    """Response model for Prometheus metrics."""
    metrics: str = Field(..., description="Prometheus-formatted metrics")


class ErrorResponse(BaseModel):
    """Standard error response model."""
    error: str = Field(..., description="Error type or code")
    message: str = Field(..., description="Human-readable error message")
    details: Optional[Dict[str, Any]] = Field(None, description="Additional error details")
    timestamp: datetime = Field(default_factory=datetime.now, description="Error timestamp")


class CancelJobRequest(BaseModel):
    """Request model for job cancellation."""
    job_id: str = Field(..., description="Job ID to cancel")


class CancelJobResponse(BaseModel):
    """Response model for job cancellation."""
    job_id: str = Field(..., description="Job ID")
    cancelled: bool = Field(..., description="Whether the job was successfully cancelled")
    message: str = Field(..., description="Response message")