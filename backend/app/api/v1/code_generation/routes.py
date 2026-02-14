"""
Code Generation API Routes.

This module implements RESTful endpoints for autonomous Terraform code generation,
including async job management, validation, diff generation, and monitoring.
"""

from typing import Dict, Any, Optional
from datetime import datetime
import asyncio
from fastapi import APIRouter, HTTPException, Depends, BackgroundTasks, status
from fastapi.responses import PlainTextResponse
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.services.code_generation.orchestrator import CodeGenerationOrchestrator
from app.services.code_generation.project_orchestrator import (
    ProjectIntegratedOrchestrator,
    get_project_integrated_orchestrator,
)
from app.services.code_generation.diff.generator import (
    TerraformDiffGenerator,
    StringDiffRequest,
)
from app.services.code_generation.generation.validator import TerraformValidator

# from app.services.code_generation.monitoring.service import CodeGenerationMonitoringService
from app.services.code_generation.best_practices.enforcer import (
    TerraformBestPracticesEnforcer,
)
from app.services.code_generation.config.settings import get_code_generation_settings
from app.dependencies.auth import get_current_user_id, get_current_user_id_optional
from app.models.user import User

from .models import (
    GenerateRequest as BaseGenerateRequest,
    GenerateResponse as BaseGenerateResponse,
    JobStatusResponse,
    JobResultResponse as BaseJobResultResponse,
    ValidateRequest,
    ValidateResponse,
    DiffRequest,
    DiffResponse,
    HealthResponse,
    MetricsResponse,
    ErrorResponse,
    CancelJobRequest,
    CancelJobResponse,
)

# Project integration imports moved to avoid circular imports - will import in functions where needed

from logconfig.logger import get_logger

logger = get_logger()
settings = get_code_generation_settings()

# Initialize services
# monitoring_service = CodeGenerationMonitoringService()
diff_generator = TerraformDiffGenerator()
validator = TerraformValidator()
best_practices_enforcer = TerraformBestPracticesEnforcer()

# Global orchestrator instances cache
_orchestrators: Dict[str, CodeGenerationOrchestrator] = {}
_project_orchestrators: Dict[str, ProjectIntegratedOrchestrator] = {}

router = APIRouter()


def get_orchestrator(db: AsyncSession) -> CodeGenerationOrchestrator:
    """Get or create orchestrator instance for the database session."""
    session_id = str(id(db))
    if session_id not in _orchestrators:
        _orchestrators[session_id] = CodeGenerationOrchestrator(db)
    return _orchestrators[session_id]


def get_project_orchestrator(db: AsyncSession) -> ProjectIntegratedOrchestrator:
    """Get or create project-integrated orchestrator instance for the database session."""
    session_id = str(id(db))
    if session_id not in _project_orchestrators:
        _project_orchestrators[session_id] = get_project_integrated_orchestrator(db)
    return _project_orchestrators[session_id]


# @router.on_event("startup")
# async def startup_event():
#     """Initialize services on startup."""
#     await monitoring_service.start_monitoring()
#     logger.info("Code generation API services initialized")


# @router.on_event("shutdown")
# async def shutdown_event():
#     """Cleanup services on shutdown."""
#     await monitoring_service.stop_monitoring()
#     logger.info("Code generation API services shut down")


@router.post("/generate", summary="Start autonomous code generation")
async def generate_code(
    request: BaseGenerateRequest,
    background_tasks: BackgroundTasks,
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    """
    Start autonomous Terraform code generation with hybrid architecture.

    This endpoint initiates an asynchronous code generation job based on the provided
    query and parameters. The generation runs in the background and can be monitored
    using the job status endpoint.

    Hybrid architecture features:
    - Extracts user_id (UUID) from Supabase JWT token
    - Validates user exists in Supabase users table using SERVICE_ROLE_KEY
    - Stores/updates project in Azure PostgreSQL using Supabase user UUID as user_id
    - Always saves generated files to Azure File Share with user-isolated directory structure
    - Conditionally creates GitHub repository and pushes files (only if project is linked to GitHub)
    - Returns Azure File Share paths and GitHub status in response
    """
    try:
        # Import required services and models
        from app.services.project_management_service import ProjectManagementService
        from app.services.azure_file_service import AzureFileService
        from app.services.github_app_service import GitHubAppService
        from app.schemas.project_integration import (
            ProjectIntegrationRequest,
            create_backward_compatible_response,
        )

        # Initialize services
        azure_file_service = AzureFileService()
        github_service = GitHubAppService()
        project_service = ProjectManagementService(
            db_session=db,
            azure_service=azure_file_service,
            github_service=github_service
        )

        # User ID is already extracted and validated by the Supabase dependency
        logger.info(f"Validated user {user_id} for code generation")

        # Parse request as project integration request for enhanced features
        if hasattr(request, "project_id") or hasattr(request, "project_name"):
            enhanced_request = request
        else:
            enhanced_request = ProjectIntegrationRequest(**request.dict())

        # Convert API scenario enum to service scenario enum
        from app.services.code_generation.generation.prompt_engineer import (
            GenerationScenario as ServiceGenerationScenario,
        )

        scenario_mapping = {
            "NEW_RESOURCE": ServiceGenerationScenario.NEW_RESOURCE,
            "MODIFY_RESOURCE": ServiceGenerationScenario.MODIFY_RESOURCE,
            "NEW_MODULE": ServiceGenerationScenario.NEW_MODULE,
            "NEW_VARIABLES": ServiceGenerationScenario.NEW_VARIABLES,
            "NEW_OUTPUTS": ServiceGenerationScenario.NEW_OUTPUTS,
        }

        scenario = scenario_mapping.get(
            enhanced_request.scenario.value, ServiceGenerationScenario.NEW_RESOURCE
        )

        # Always use project integration with hybrid architecture
        orchestrator = get_project_orchestrator(db)

        # Generate code with hybrid architecture
        job_id, project_info = await orchestrator.generate_code_async_with_hybrid_architecture(
            query=enhanced_request.query,
            user_id=user_id,  # Supabase user UUID
            project_id=getattr(enhanced_request, "project_id", None),
            project_name=getattr(enhanced_request, "project_name", None),
            project_description=getattr(enhanced_request, "project_description", None),
            save_to_project=getattr(enhanced_request, "save_to_project", True),
            scenario=scenario,
            repository_name=enhanced_request.repository_name,
            existing_code=enhanced_request.existing_code,
            target_file_path=enhanced_request.target_file_path,
            provider_type=enhanced_request.provider_type,
            temperature=enhanced_request.temperature,
            max_tokens=enhanced_request.max_tokens,
        )

        logger.info(f"Started hybrid architecture generation job {job_id} for Supabase user {user_id}")

        # Create response with project information and hybrid architecture details
        return create_backward_compatible_response(
            job_id=job_id,
            status="accepted",
            message="Code generation job started successfully with hybrid architecture",
            project_info=project_info,
        )

    except Exception as e:
        logger.error(f"Failed to start code generation with hybrid architecture: {e}")
        
        # Handle specific error types
        if "not found in Supabase" in str(e):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="User not found in Supabase users table",
            )
        elif "Invalid authorization header" in str(e) or "Missing JWT token" in str(e):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid or missing authorization token",
            )
        elif "Connection error to Supabase" in str(e):
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Unable to connect to Supabase for user validation",
            )
        else:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to start code generation: {str(e)}",
            )


@router.post(
    "/generate/realtime", summary="Start code generation with real-time monitoring"
)
async def generate_code_with_realtime(
    request: BaseGenerateRequest,
    background_tasks: BackgroundTasks,
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    """
    Start autonomous Terraform code generation with real-time progress monitoring and hybrid architecture.

    This endpoint initiates an asynchronous code generation job with WebSocket-based
    real-time updates for progress tracking, file creation notifications, and
    completion/failure events.

    Hybrid architecture features:
    - Real-time progress updates via WebSocket
    - File creation notifications during generation
    - Extracts user_id (UUID) from Supabase JWT token
    - Validates user exists in Supabase users table using SERVICE_ROLE_KEY
    - Always saves generated files to Azure File Share with user-isolated directory structure
    - Conditionally creates GitHub repository and pushes files (only if project is linked to GitHub)
    - Returns Azure File Share paths and GitHub status in response
    """

    try:
        # Import required services and models
        from app.schemas.project_integration import (
            ProjectIntegrationRequest,
            create_backward_compatible_response,
        )

        # User ID is already extracted and validated by the Supabase dependency
        logger.info(f"Validated user {user_id} for real-time code generation")

        # Parse request as project integration request for enhanced features
        if hasattr(request, "project_id") or hasattr(request, "project_name"):
            enhanced_request = request
        else:
            enhanced_request = ProjectIntegrationRequest(**request.dict())

        # Convert API scenario enum to service scenario enum
        from app.services.code_generation.generation.prompt_engineer import (
            GenerationScenario as ServiceGenerationScenario,
        )

        scenario_mapping = {
            "NEW_RESOURCE": ServiceGenerationScenario.NEW_RESOURCE,
            "MODIFY_RESOURCE": ServiceGenerationScenario.MODIFY_RESOURCE,
            "NEW_MODULE": ServiceGenerationScenario.NEW_MODULE,
            "NEW_VARIABLES": ServiceGenerationScenario.NEW_VARIABLES,
            "NEW_OUTPUTS": ServiceGenerationScenario.NEW_OUTPUTS,
        }

        scenario = scenario_mapping.get(
            enhanced_request.scenario.value, ServiceGenerationScenario.NEW_RESOURCE
        )

        # Always use hybrid architecture with real-time monitoring
        orchestrator = get_project_orchestrator(db)

        # Generate code with hybrid architecture and real-time monitoring
        job_id, project_info = await orchestrator.generate_code_async_with_hybrid_architecture(
            query=enhanced_request.query,
            user_id=user_id,  # Supabase user UUID
            project_id=getattr(enhanced_request, "project_id", None),
            project_name=getattr(enhanced_request, "project_name", None),
            project_description=getattr(enhanced_request, "project_description", None),
            save_to_project=getattr(enhanced_request, "save_to_project", True),
            scenario=scenario,
            repository_name=enhanced_request.repository_name,
            existing_code=enhanced_request.existing_code,
            target_file_path=enhanced_request.target_file_path,
            provider_type=enhanced_request.provider_type,
            temperature=enhanced_request.temperature,
            max_tokens=enhanced_request.max_tokens,
        )

        logger.info(f"Started real-time hybrid architecture generation job {job_id} for Supabase user {user_id}")

        # Create response with project information
        return create_backward_compatible_response(
            job_id=job_id,
            status="accepted",
            message="Real-time code generation job started successfully with hybrid architecture",
            project_info=project_info,
        )

    except Exception as e:
        logger.error(f"Failed to start real-time code generation with hybrid architecture: {e}")
        
        # Handle specific error types
        if "not found in Supabase" in str(e):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="User not found in Supabase users table",
            )
        elif "Invalid authorization header" in str(e) or "Missing JWT token" in str(e):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid or missing authorization token",
            )
        elif "Connection error to Supabase" in str(e):
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Unable to connect to Supabase for user validation",
            )
        else:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to start real-time code generation: {str(e)}",
            )


@router.post(
    "/generate/sync/realtime",
    summary="Generate code synchronously with real-time monitoring",
)
async def generate_code_sync_with_realtime(
    request: BaseGenerateRequest,
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    """
    Generate Terraform code synchronously with real-time progress monitoring and hybrid architecture.

    This endpoint generates code synchronously while still providing real-time
    WebSocket updates for progress tracking. Useful for smaller generations
    where immediate results are needed.

    Hybrid architecture features:
    - Synchronous response with generated code
    - Real-time progress updates via WebSocket during generation
    - Extracts user_id (UUID) from Supabase JWT token
    - Validates user exists in Supabase users table using SERVICE_ROLE_KEY
    - Always saves generated files to Azure File Share with user-isolated directory structure
    - Conditionally creates GitHub repository and pushes files (only if project is linked to GitHub)
    - Returns Azure File Share paths and GitHub status in response
    """

    try:
        # Import project integration models
        from app.schemas.project_integration import (
            ProjectIntegrationRequest,
            create_backward_compatible_response,
        )

        # Parse request as project integration request for enhanced features
        if hasattr(request, "project_id") or hasattr(request, "project_name"):
            enhanced_request = request
        else:
            enhanced_request = ProjectIntegrationRequest(**request.dict())

        # Convert API scenario enum to service scenario enum
        from app.services.code_generation.generation.prompt_engineer import (
            GenerationScenario as ServiceGenerationScenario,
        )

        scenario_mapping = {
            "NEW_RESOURCE": ServiceGenerationScenario.NEW_RESOURCE,
            "MODIFY_RESOURCE": ServiceGenerationScenario.MODIFY_RESOURCE,
            "NEW_MODULE": ServiceGenerationScenario.NEW_MODULE,
            "NEW_VARIABLES": ServiceGenerationScenario.NEW_VARIABLES,
            "NEW_OUTPUTS": ServiceGenerationScenario.NEW_OUTPUTS,
        }

        scenario = scenario_mapping.get(
            enhanced_request.scenario.value, ServiceGenerationScenario.NEW_RESOURCE
        )

        # Determine if project integration should be used
        use_project_integration = getattr(
            enhanced_request, "save_to_project", True
        ) and (
            getattr(enhanced_request, "project_id", None)
            or getattr(enhanced_request, "project_name", None)
        )

        if use_project_integration:
            # Use project-integrated orchestrator with real-time monitoring
            orchestrator = get_project_orchestrator(db)

            result, project_info = (
                await orchestrator.generate_code_with_project_integration_and_realtime(
                    query=enhanced_request.query,
                    user_id=user_id,
                    project_id=getattr(enhanced_request, "project_id", None),
                    project_name=getattr(enhanced_request, "project_name", None),
                    project_description=getattr(
                        enhanced_request, "project_description", None
                    ),
                    save_to_project=getattr(enhanced_request, "save_to_project", True),
                    scenario=scenario,
                    repository_name=enhanced_request.repository_name,
                    existing_code=enhanced_request.existing_code,
                    target_file_path=enhanced_request.target_file_path,
                    provider_type=enhanced_request.provider_type,
                    temperature=enhanced_request.temperature,
                    max_tokens=enhanced_request.max_tokens,
                )
            )

            logger.info(
                f"Completed real-time project-integrated generation for user {user_id}"
            )

            # Create response with project information and results
            response_data = {
                "status": "completed" if result.success else "failed",
                "message": "Real-time code generation completed with project integration",
                "generated_code": result.generated_code,
                "generated_files": result.generated_files,
                "processing_time_ms": result.total_time_ms,
                "success": result.success,
                "errors": result.errors,
                "pipeline_metadata": result.pipeline_metadata,
            }

            return create_backward_compatible_response(
                **response_data, project_info=project_info
            )

        else:
            # Use regular orchestrator with real-time monitoring
            orchestrator = get_orchestrator(db)

            result = await orchestrator.generate_code_with_realtime_monitoring(
                query=enhanced_request.query,
                user_id=user_id,
                scenario=scenario,
                repository_name=enhanced_request.repository_name,
                existing_code=enhanced_request.existing_code,
                target_file_path=enhanced_request.target_file_path,
                provider_type=enhanced_request.provider_type,
                temperature=enhanced_request.temperature,
                max_tokens=enhanced_request.max_tokens,
            )

            logger.info(
                f"Completed real-time code generation for user {user_id}"
            )

            # Create response without project info
            return create_backward_compatible_response(
                status="completed" if result.success else "failed",
                message="Real-time code generation completed",
                generated_code=result.generated_code,
                generated_files=result.generated_files,
                processing_time_ms=result.total_time_ms,
                success=result.success,
                errors=result.errors,
                pipeline_metadata=result.pipeline_metadata,
            )

    except Exception as e:
        logger.error(f"Failed to complete real-time code generation: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to complete real-time code generation: {str(e)}",
        )


@router.get(
    "/jobs/{job_id}",
    response_model=JobStatusResponse,
    summary="Get generation job status",
)
async def get_job_status(
    job_id: str,
    db: AsyncSession = Depends(get_db),
    user_id: Optional[str] = Depends(get_current_user_id_optional),
) -> JobStatusResponse:
    """
    Get the status of a code generation job.

    Returns detailed information about the job including current status,
    progress, and results if completed.
    """
    try:
        orchestrator = get_orchestrator(db)
        job_status = await orchestrator.get_job_status(job_id)

        if job_status is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail=f"Job {job_id} not found"
            )

        # Convert to response model
        response = JobStatusResponse(**job_status)

        logger.info(f"Retrieved status for job {job_id}: {response.status}")

        return response

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get job status for {job_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get job status: {str(e)}",
        )


@router.get("/jobs/{job_id}/result", summary="Get generation job result with diff")
async def get_job_result(
    job_id: str,
    db: AsyncSession = Depends(get_db),
    user_id: Optional[str] = Depends(get_current_user_id_optional),
):
    """
    Get the result of a completed code generation job with diff information.

    Returns the generated code along with diff statistics if the job has completed.
    Enhanced to include project information and Azure File Share paths when available.
    """
    try:
        # Import project integration models
        from app.schemas.project_integration import (
            ProjectInfo,
            FileInfo,
            create_backward_compatible_job_result,
        )

        # Try project orchestrator first (for jobs with project integration)
        project_orchestrator = get_project_orchestrator(db)
        job_status = await project_orchestrator.get_job_status(job_id)

        # Fallback to regular orchestrator if not found
        if job_status is None:
            orchestrator = get_orchestrator(db)
            job_status = await orchestrator.get_job_status(job_id)

        if job_status is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail=f"Job {job_id} not found"
            )

        if job_status.get("status") not in ["completed", "failed"]:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Job {job_id} is not completed yet. Current status: {job_status.get('status')}",
            )

        # Generate diff if we have both original and generated code
        diff_content = None
        additions = None
        deletions = None
        changes = None

        if job_status.get("generated_code") and job_status.get("request", {}).get(
            "existing_code"
        ):
            try:
                diff_request = StringDiffRequest(
                    source_content=job_status["request"]["existing_code"],
                    target_content=job_status["generated_code"],
                    source_name="original",
                    target_name="generated",
                )
                diff_result = await diff_generator.generate_string_diff(diff_request)
                diff_content = diff_result.diff_content
                additions = diff_result.additions
                deletions = diff_result.deletions
                changes = diff_result.changes
            except Exception as e:
                logger.warning(f"Failed to generate diff for job {job_id}: {e}")

        # Extract project integration metadata if available
        project_info = None
        generated_file_info = None
        generation_folder_path = None

        pipeline_metadata = job_status.get("pipeline_metadata", {})
        project_integration = pipeline_metadata.get("project_integration", {})

        if project_integration:
            # Try to get project information from the job
            try:
                from app.services.projects.crud_service import ProjectCRUDService

                project_crud = ProjectCRUDService(db)

                project_id = project_integration.get("project_id")
                if project_id and user_id:
                    project = await project_crud.get_project(
                        project_id, user_id
                    )
                    project_info = ProjectInfo(
                        project_id=project.id,
                        project_name=project.name,
                        project_description=project.description,
                        azure_folder_path=project.azure_folder_path,
                        is_new_project=False,  # Existing job, so not new
                    )

                    # Get generation folder path
                    generation_folder_path = project_integration.get("azure_folder")

                    # Create file info for generated files
                    if job_status.get("generated_files"):
                        generated_file_info = []
                        for filename, content in job_status["generated_files"].items():
                            file_info = FileInfo(
                                file_path=filename,
                                azure_path=(
                                    f"{generation_folder_path}/{filename}"
                                    if generation_folder_path
                                    else filename
                                ),
                                file_type=(
                                    f".{filename.split('.')[-1]}"
                                    if "." in filename
                                    else ""
                                ),
                                size_bytes=len(content.encode("utf-8")),
                                content_hash="",  # Would need to calculate if needed
                            )
                            generated_file_info.append(file_info)

            except Exception as e:
                logger.warning(
                    f"Failed to get project information for job {job_id}: {e}"
                )

        # Extract hybrid architecture information
        azure_paths = None
        github_status = None
        
        pipeline_metadata = job_status.get("pipeline_metadata", {})
        hybrid_arch_data = pipeline_metadata.get("hybrid_architecture", {})
        
        if hybrid_arch_data:
            azure_paths = hybrid_arch_data.get("azure_paths", [])
            github_status_data = hybrid_arch_data.get("github_status", {})
            
            if github_status_data:
                from app.schemas.project_integration import GitHubStatus
                github_status = GitHubStatus(
                    pushed=github_status_data.get("pushed", False),
                    repo_url=github_status_data.get("repo_url"),
                    commit_sha=github_status_data.get("commit_sha"),
                    error=github_status_data.get("error")
                )

        # Create enhanced response with project information and hybrid architecture data
        response = create_backward_compatible_job_result(
            job_id=job_id,
            status=job_status.get("status"),
            success=job_status.get("success", False),
            generated_code=job_status.get("generated_code"),  # Legacy compatibility
            generated_files=job_status.get("generated_files"),
            project_info=project_info,
            generated_file_info=generated_file_info,
            generation_folder_path=generation_folder_path,
            azure_paths=azure_paths,
            github_status=github_status,
            diff_content=diff_content,
            additions=additions,
            deletions=deletions,
            changes=changes,
            processing_time_ms=job_status.get("processing_time_ms"),
            error_message=job_status.get("error_message"),
        )

        logger.info(f"Retrieved result for job {job_id}")

        return response

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get job result for {job_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get job result: {str(e)}",
        )


@router.post(
    "/validate", response_model=ValidateResponse, summary="Validate Terraform code"
)
async def validate_code(
    request: ValidateRequest,
    user_id: Optional[str] = Depends(get_current_user_id_optional),
) -> ValidateResponse:
    """
    Validate Terraform code for syntax, semantic, and best practices issues.

    Performs comprehensive validation including syntax checking, semantic analysis,
    style validation, and security checks.
    """
    start_time = asyncio.get_event_loop().time()

    try:
        validation_result = await validator.validate_code(
            code=request.code,
            file_path=request.file_path,
            strict_mode=request.strict_mode,
        )

        processing_time = (asyncio.get_event_loop().time() - start_time) * 1000

        # Record monitoring
        # monitoring_service.record_validation_request(
        #     success=validation_result.is_valid,
        #     duration_ms=processing_time
        # )

        # Convert to response model
        response = ValidateResponse(
            is_valid=validation_result.is_valid,
            issues=[
                {
                    "error_type": (
                        issue.error_type.value
                        if hasattr(issue, "error_type")
                        else str(issue.get("error_type", ""))
                    ),
                    "severity": (
                        issue.severity.value
                        if hasattr(issue, "severity")
                        else str(issue.get("severity", ""))
                    ),
                    "message": issue.message,
                    "line_number": issue.line_number,
                    "column_number": issue.column_number,
                    "context": issue.context,
                    "suggestion": issue.suggestion,
                    "rule_id": issue.rule_id,
                }
                for issue in validation_result.issues
            ],
            processing_time_ms=processing_time,
            total_issues=validation_result.total_issues,
            errors_count=validation_result.errors_count,
            warnings_count=validation_result.warnings_count,
            info_count=validation_result.info_count,
        )

        logger.info(f"Validated code: {response.total_issues} issues found")

        return response

    except Exception as e:
        processing_time = (asyncio.get_event_loop().time() - start_time) * 1000
        # monitoring_service.record_validation_request(success=False, duration_ms=processing_time)

        logger.error(f"Validation failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Validation failed: {str(e)}",
        )


@router.post(
    "/diff", response_model=DiffResponse, summary="Generate diff between code versions"
)
async def generate_diff(
    request: DiffRequest,
    user_id: Optional[str] = Depends(get_current_user_id_optional),
) -> DiffResponse:
    """
    Generate a diff between two versions of Terraform code.

    Creates a unified diff showing the differences between source and target content,
    with Terraform-aware formatting and change statistics.
    """
    start_time = asyncio.get_event_loop().time()

    try:
        diff_request = StringDiffRequest(
            source_content=request.source_content,
            target_content=request.target_content,
            source_name=request.source_name,
            target_name=request.target_name,
        )

        # Apply options
        diff_request.options.context_lines = request.context_lines
        diff_request.options.ignore_whitespace = request.ignore_whitespace
        diff_request.options.terraform_aware = request.terraform_aware

        diff_result = await diff_generator.generate_string_diff(diff_request)

        processing_time = (asyncio.get_event_loop().time() - start_time) * 1000

        # Record monitoring
        # monitoring_service.record_diff_request(
        #     success=True,
        #     duration_ms=processing_time
        # )

        response = DiffResponse(
            diff_content=diff_result.diff_content,
            additions=diff_result.additions,
            deletions=diff_result.deletions,
            changes=diff_result.changes,
            has_changes=diff_result.has_changes,
            source_hash=diff_result.source_hash,
            target_hash=diff_result.target_hash,
            processing_time_ms=processing_time,
        )

        logger.info(
            f"Generated diff: {response.changes} changes, {response.additions} additions, {response.deletions} deletions"
        )

        return response

    except Exception as e:
        processing_time = (asyncio.get_event_loop().time() - start_time) * 1000
        # monitoring_service.record_diff_request(success=False, duration_ms=processing_time)

        logger.error(f"Diff generation failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Diff generation failed: {str(e)}",
        )


@router.post("/best-practices", summary="Analyze Terraform code for best practices")
async def analyze_best_practices(
    code: str,
    strict_mode: bool = False,
    user_id: Optional[str] = Depends(get_current_user_id_optional),
) -> Dict[str, Any]:
    """
    Analyze Terraform code for best practices violations and recommendations.

    Performs comprehensive analysis of naming conventions, organization,
    security practices, performance optimization, and maintainability.
    """
    try:
        report = best_practices_enforcer.analyze_code(code, strict_mode)

        # Convert violations to dict format
        violations = []
        for violation in report.violations:
            violations.append(
                {
                    "category": violation.category.value,
                    "severity": violation.severity.value,
                    "rule": violation.rule,
                    "message": violation.message,
                    "suggestion": violation.suggestion,
                    "line_number": violation.line_number,
                    "context": violation.context,
                }
            )

        response = {
            "score": report.score,
            "total_violations": report.total_violations,
            "errors_count": report.errors_count,
            "warnings_count": report.warnings_count,
            "info_count": report.info_count,
            "violations": violations,
        }

        logger.info(
            f"Best practices analysis completed: score {report.score:.1f}, {len(violations)} violations"
        )

        return response

    except Exception as e:
        logger.error(f"Best practices analysis failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Best practices analysis failed: {str(e)}",
        )


@router.get("/health", response_model=HealthResponse, summary="System health check")
async def get_health(
    db: AsyncSession = Depends(get_db),
    user_id: Optional[str] = Depends(get_current_user_id_optional),
) -> HealthResponse:
    """
    Get comprehensive health status of the code generation system.

    Returns health information about all components, job statistics,
    and system configuration.
    """
    try:
        orchestrator = get_orchestrator(db)
        orchestrator_health = await orchestrator.get_orchestrator_health()

        # Get monitoring health
        monitoring_health = {
            "status": "disabled",
            "message": "Monitoring temporarily disabled",
        }

        # Combine health information
        overall_status = "healthy"
        if (
            orchestrator_health.get("status") == "unhealthy"
            or monitoring_health.get("status") == "critical"
        ):
            overall_status = "unhealthy"
        elif (
            orchestrator_health.get("status") == "warning"
            or monitoring_health.get("status") == "warning"
        ):
            overall_status = "warning"

        response = HealthResponse(
            status=overall_status,
            timestamp=datetime.now(),
            version="1.0.0",
            components={
                "orchestrator": orchestrator_health,
                "monitoring": monitoring_health,
                "diff_generator": {"status": "operational"},
                "validator": {"status": "operational"},
            },
            job_stats=orchestrator_health.get("job_stats", {}),
            configuration={
                "max_concurrent_jobs": orchestrator_health.get("configuration", {}).get(
                    "max_concurrent_jobs", 5
                ),
                "job_timeout_seconds": orchestrator_health.get("configuration", {}).get(
                    "job_timeout_seconds", 300
                ),
                "enable_monitoring": orchestrator_health.get("configuration", {}).get(
                    "enable_monitoring", True
                ),
            },
        )

        logger.info(f"Health check completed: {overall_status}")

        return response

    except Exception as e:
        logger.error(f"Health check failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Health check failed: {str(e)}",
        )


@router.get(
    "/metrics", response_class=PlainTextResponse, summary="Prometheus metrics endpoint"
)
async def get_metrics(
    user_id: Optional[str] = Depends(get_current_user_id_optional),
) -> str:
    """
    Get Prometheus-formatted metrics for monitoring.

    Returns metrics in Prometheus exposition format for scraping by monitoring systems.
    """
    try:
        metrics = "# Monitoring temporarily disabled"
        return metrics

    except Exception as e:
        logger.error(f"Failed to get metrics: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get metrics: {str(e)}",
        )


@router.delete(
    "/jobs/{job_id}",
    response_model=CancelJobResponse,
    summary="Cancel a generation job",
)
async def cancel_job(
    job_id: str,
    db: AsyncSession = Depends(get_db),
    user_id: Optional[str] = Depends(get_current_user_id_optional),
) -> CancelJobResponse:
    """
    Cancel a running code generation job.

    Attempts to cancel the specified job if it's currently running.
    """
    try:
        orchestrator = get_orchestrator(db)
        cancelled = await orchestrator.cancel_job(job_id)

        if not cancelled:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Job {job_id} not found or already completed",
            )

        response = CancelJobResponse(
            job_id=job_id, cancelled=True, message="Job cancelled successfully"
        )

        logger.info(f"Cancelled job {job_id}")

        return response

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to cancel job {job_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to cancel job: {str(e)}",
        )


@router.get("/jobs", summary="List recent generation jobs")
async def list_jobs(
    limit: int = 10,
    status_filter: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
    user_id: Optional[str] = Depends(get_current_user_id_optional),
):
    """
    List recent code generation jobs.

    Returns a list of recent jobs with optional status filtering.
    """
    try:
        orchestrator = get_orchestrator(db)
        jobs = await orchestrator.get_generation_history(
            limit=limit, status_filter=status_filter
        )

        return {"jobs": jobs, "total": len(jobs)}

    except Exception as e:
        logger.error(f"Failed to list jobs: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to list jobs: {str(e)}",
        )
