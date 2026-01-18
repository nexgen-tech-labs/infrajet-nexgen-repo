"""
Main Orchestrator for Terraform Code Generation.

This module provides the high-level orchestration layer that coordinates
all components of the autonomous code generation system, including RAG,
prompt engineering, LLM generation, and knowledge base integration.
"""

import asyncio
import uuid
import os
from pathlib import Path
from typing import Dict, Any, Optional, List, Tuple
from dataclasses import dataclass, field
from datetime import datetime
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.code_generation.rag.retriever import RAGRetriever, RetrievalContext
from app.services.code_generation.generation.prompt_engineer import (
    PromptEngineer,
    PromptContext,
    GenerationScenario,
)
from app.services.code_generation.generation.pipeline import (
    AutonomousGenerationPipeline,
    GenerationRequest,
    GenerationResult,
)
from app.services.code_generation.rag.knowledge_base import (
    KnowledgeBase,
    KnowledgeBaseResult,
)
from app.services.code_generation.llm_providers.provider_factory import ProviderFactory
from app.services.code_generation.config.settings import get_code_generation_settings
from app.db.session import async_session_factory

# from app.services.code_generation.monitoring.service import CodeGenerationMonitoringService
from logconfig.logger import get_logger

logger = get_logger()
settings = get_code_generation_settings()


@dataclass
class GenerationJob:
    """Represents a code generation job."""

    job_id: str
    status: str  # "pending", "running", "completed", "failed", "cancelled"
    request: GenerationRequest
    created_at: datetime
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    result: Optional[GenerationResult] = None
    progress: Dict[str, Any] = field(default_factory=dict)
    error_message: Optional[str] = None


@dataclass
class OrchestratorConfig:
    """Configuration for the orchestrator."""

    max_concurrent_jobs: int = 5
    job_timeout_seconds: int = 300  # 5 minutes
    enable_knowledge_base: bool = True
    enable_monitoring: bool = True
    default_provider: str = "claude"
    fallback_providers: List[str] = field(default_factory=lambda: ["claude"])


class CodeGenerationOrchestrator:
    """
    Main orchestrator for autonomous Terraform code generation.

    This class coordinates all components of the code generation system,
    manages async jobs, and provides monitoring and logging integration.
    """

    def __init__(self, db_session: AsyncSession):
        """
        Initialize the code generation orchestrator.

        Args:
            db_session: Database session for all operations
        """
        self.db = db_session

        # Initialize components
        self.rag_retriever = RAGRetriever(db_session)
        self.prompt_engineer = PromptEngineer()
        self.generation_pipeline = AutonomousGenerationPipeline(db_session)

        # Initialize real-time pipeline for enhanced monitoring
        try:
            from app.services.code_generation.generation.realtime_pipeline import (
                RealtimeGenerationPipeline,
            )

            self.realtime_pipeline = RealtimeGenerationPipeline(db_session)
            logger.info("Real-time pipeline initialized successfully")
        except ImportError as e:
            logger.warning(f"Real-time pipeline not available: {e}")
            self.realtime_pipeline = None

        self.knowledge_base = KnowledgeBase(db_session)
        self.provider_factory = ProviderFactory()

        # Job management
        self.active_jobs: Dict[str, GenerationJob] = {}
        self.completed_jobs: Dict[str, GenerationJob] = {}
        self.job_semaphore = asyncio.Semaphore(5)  # Max concurrent jobs

        # Monitoring
        # self.monitoring_service = CodeGenerationMonitoringService()

        # Configuration
        self.config = OrchestratorConfig()

        logger.info("CodeGenerationOrchestrator initialized")

    async def generate_code(
        self,
        query: str,
        scenario: GenerationScenario = GenerationScenario.NEW_RESOURCE,
        repository_name: Optional[str] = None,
        existing_code: Optional[str] = None,
        target_file_path: Optional[str] = None,
        **kwargs,
    ) -> GenerationResult:
        """
        Generate Terraform code using the complete pipeline with file validation and indexing.

        Args:
            query: User's code generation request
            scenario: Type of generation scenario
            repository_name: Optional repository context
            existing_code: Optional existing code to modify
            target_file_path: Optional target file path
            **kwargs: Additional parameters

        Returns:
            GenerationResult with generated files and metadata
        """
        # Validate file paths if target_file_path is provided
        if target_file_path:
            validation_result = await self.validate_file_paths([target_file_path])
            if validation_result["nonexistent_paths"]:
                logger.info(
                    f"Target path {target_file_path} does not exist, will create during generation"
                )

        # Create generation request
        request = GenerationRequest(
            query=query,
            scenario=scenario,
            repository_name=repository_name,
            existing_code=existing_code,
            target_file_path=target_file_path,
            provider_type=kwargs.get("provider_type", self.config.default_provider),
            temperature=kwargs.get("temperature"),
            max_tokens=kwargs.get("max_tokens"),
            max_context_documents=kwargs.get("max_context_documents", 5),
            similarity_threshold=kwargs.get("similarity_threshold", 0.7),
        )

        # Execute generation
        result = await self.generation_pipeline.generate_code(request)

        if result.success:
            logger.info(
                f"Code generation completed successfully for query: {query[:50]}... Generated {len(result.generated_files)} files"
            )

            # Index generated files if target_file_path was provided
            if target_file_path and result.generated_files:
                try:
                    # Determine repository name for indexing
                    repo_name = repository_name or "generated"
                    target_dir = (
                        str(Path(target_file_path).parent)
                        if Path(target_file_path).is_file()
                        else target_file_path
                    )

                    indexing_result = await self.index_generated_files(
                        result.generated_files, repo_name, target_dir
                    )

                    # Add indexing metadata to result
                    result.pipeline_metadata["indexing"] = indexing_result
                    logger.info(
                        f"Indexed {indexing_result['files_indexed']} generated files"
                    )

                except Exception as e:
                    logger.warning(f"Failed to index generated files: {e}")
                    result.pipeline_metadata["indexing_error"] = str(e)

            return result
        else:
            error_msg = f"Code generation failed: {', '.join(result.errors)}"
            logger.error(error_msg)
            raise Exception(error_msg)

    async def generate_code_async(
        self,
        query: str,
        scenario: GenerationScenario = GenerationScenario.NEW_RESOURCE,
        repository_name: Optional[str] = None,
        existing_code: Optional[str] = None,
        target_file_path: Optional[str] = None,
        **kwargs,
    ) -> str:
        """
        Generate Terraform code asynchronously with job management.

        Args:
            query: User's code generation request
            scenario: Type of generation scenario
            repository_name: Optional repository context
            existing_code: Optional existing code to modify
            target_file_path: Optional target file path
            **kwargs: Additional parameters

        Returns:
            Job ID for tracking the async generation
        """
        job_id = str(uuid.uuid4())

        # Create generation request
        request = GenerationRequest(
            query=query,
            scenario=scenario,
            repository_name=repository_name,
            existing_code=existing_code,
            target_file_path=target_file_path,
            provider_type=kwargs.get("provider_type", self.config.default_provider),
            temperature=kwargs.get("temperature"),
            max_tokens=kwargs.get("max_tokens"),
            max_context_documents=kwargs.get("max_context_documents", 5),
            similarity_threshold=kwargs.get("similarity_threshold", 0.7),
        )

        # Create job
        job = GenerationJob(
            job_id=job_id, status="pending", request=request, created_at=datetime.now()
        )

        self.active_jobs[job_id] = job

        # Start async generation - session will be created in the background task
        asyncio.create_task(self._execute_generation_job(job))

        logger.info(f"Started async code generation job: {job_id}")
        return job_id

    async def generate_code_with_realtime_monitoring(
        self,
        query: str,
        user_id: int,
        project_id: Optional[str] = None,
        scenario: GenerationScenario = GenerationScenario.NEW_RESOURCE,
        repository_name: Optional[str] = None,
        existing_code: Optional[str] = None,
        target_file_path: Optional[str] = None,
        **kwargs,
    ) -> GenerationResult:
        """
        Generate Terraform code with real-time monitoring and progress updates.

        Args:
            query: User's code generation request
            user_id: User ID for real-time notifications
            project_id: Optional project ID for context
            scenario: Type of generation scenario
            repository_name: Optional repository context
            existing_code: Optional existing code to modify
            target_file_path: Optional target file path
            **kwargs: Additional parameters

        Returns:
            GenerationResult with generated files and metadata
        """
        if not self.realtime_pipeline:
            logger.warning(
                "Real-time pipeline not available, falling back to standard generation"
            )
            return await self.generate_code(
                query=query,
                scenario=scenario,
                repository_name=repository_name,
                existing_code=existing_code,
                target_file_path=target_file_path,
                **kwargs,
            )

        # Validate file paths if target_file_path is provided
        if target_file_path:
            validation_result = await self.validate_file_paths([target_file_path])
            if validation_result["nonexistent_paths"]:
                logger.info(
                    f"Target path {target_file_path} does not exist, will create during generation"
                )

        # Create generation request
        request = GenerationRequest(
            query=query,
            scenario=scenario,
            repository_name=repository_name,
            existing_code=existing_code,
            target_file_path=target_file_path,
            provider_type=kwargs.get("provider_type", self.config.default_provider),
            temperature=kwargs.get("temperature"),
            max_tokens=kwargs.get("max_tokens"),
            max_context_documents=kwargs.get("max_context_documents", 5),
            similarity_threshold=kwargs.get("similarity_threshold", 0.7),
        )

        # Generate unique generation ID
        generation_id = str(uuid.uuid4())

        # Execute generation with real-time monitoring
        result = await self.realtime_pipeline.generate_code_with_realtime(
            request=request,
            generation_id=generation_id,
            project_id=project_id,
            user_id=user_id,
        )

        if result.success:
            logger.info(
                f"Real-time generation completed successfully for query: {query[:50]}... Generated {len(result.generated_files)} files"
            )

            # Index generated files if target_file_path was provided
            if target_file_path and result.generated_files:
                try:
                    # Determine repository name for indexing
                    repo_name = repository_name or "generated"
                    target_dir = (
                        str(Path(target_file_path).parent)
                        if Path(target_file_path).is_file()
                        else target_file_path
                    )

                    indexing_result = await self.index_generated_files(
                        result.generated_files, repo_name, target_dir
                    )

                    # Add indexing metadata to result
                    result.pipeline_metadata["indexing"] = indexing_result
                    logger.info(
                        f"Indexed {indexing_result['files_indexed']} generated files"
                    )

                except Exception as e:
                    logger.warning(f"Failed to index generated files: {e}")
                    result.pipeline_metadata["indexing_error"] = str(e)

            return result
        else:
            error_msg = f"Real-time code generation failed: {', '.join(result.errors)}"
            logger.error(error_msg)
            raise Exception(error_msg)

    async def generate_code_async_with_realtime_monitoring(
        self,
        query: str,
        user_id: int,
        project_id: Optional[str] = None,
        scenario: GenerationScenario = GenerationScenario.NEW_RESOURCE,
        repository_name: Optional[str] = None,
        existing_code: Optional[str] = None,
        target_file_path: Optional[str] = None,
        **kwargs,
    ) -> str:
        """
        Generate Terraform code asynchronously with real-time monitoring.

        Args:
            query: User's code generation request
            user_id: User ID for real-time notifications
            project_id: Optional project ID for context
            scenario: Type of generation scenario
            repository_name: Optional repository context
            existing_code: Optional existing code to modify
            target_file_path: Optional target file path
            **kwargs: Additional parameters

        Returns:
            Job ID for tracking the async generation
        """
        if not self.realtime_pipeline:
            logger.warning(
                "Real-time pipeline not available, falling back to standard async generation"
            )
            return await self.generate_code_async(
                query=query,
                scenario=scenario,
                repository_name=repository_name,
                existing_code=existing_code,
                target_file_path=target_file_path,
                **kwargs,
            )

        job_id = str(uuid.uuid4())

        # Create generation request
        request = GenerationRequest(
            query=query,
            scenario=scenario,
            repository_name=repository_name,
            existing_code=existing_code,
            target_file_path=target_file_path,
            provider_type=kwargs.get("provider_type", self.config.default_provider),
            temperature=kwargs.get("temperature"),
            max_tokens=kwargs.get("max_tokens"),
            max_context_documents=kwargs.get("max_context_documents", 5),
            similarity_threshold=kwargs.get("similarity_threshold", 0.7),
        )

        # Create enhanced job with real-time information
        from app.services.code_generation.realtime_orchestrator import (
            RealtimeGenerationJob,
        )

        job = RealtimeGenerationJob(
            job_id=job_id,
            status="pending",
            request=request,
            created_at=datetime.now(),
            user_id=user_id,
            project_id=project_id,
            enable_realtime=True,
        )

        self.active_jobs[job_id] = job

        # Start async generation with real-time monitoring
        asyncio.create_task(self._execute_realtime_generation_job(job))

        logger.info(f"Started real-time async generation job: {job_id}")
        return job_id

    async def _execute_generation_job(self, job: GenerationJob):
        """
        Execute a generation job asynchronously with its own database session.

        Args:
            job: The generation job to execute
        """
        async with self.job_semaphore:
            try:
                # Create a new session for this background task to avoid session conflicts
                async with async_session_factory() as background_session:
                    # Update job status
                    job.status = "running"
                    job.started_at = datetime.now()

                    # Record job start
                    # if self.config.enable_monitoring:
                    #     self.monitoring_service.record_job_start(job.job_id, job.request.__dict__)

                    # Create a new pipeline with the background session to avoid session conflicts
                    background_pipeline = AutonomousGenerationPipeline(
                        background_session
                    )

                    # Validate file paths if target_file_path is provided
                    if job.request.target_file_path:
                        validation_result = await self.validate_file_paths(
                            [job.request.target_file_path]
                        )
                        if validation_result["nonexistent_paths"]:
                            logger.info(
                                f"Target path {job.request.target_file_path} does not exist, will create during generation"
                            )

                    # Execute generation with timeout using the background pipeline
                    result = await asyncio.wait_for(
                        background_pipeline.generate_code(job.request),
                        timeout=self.config.job_timeout_seconds,
                    )

                    # Index generated files if target_file_path was provided and generation was successful
                    if (
                        result.success
                        and job.request.target_file_path
                        and result.generated_files
                    ):
                        try:
                            # Determine repository name for indexing
                            repo_name = job.request.repository_name or "generated"
                            target_dir = (
                                str(Path(job.request.target_file_path).parent)
                                if Path(job.request.target_file_path).is_file()
                                else job.request.target_file_path
                            )

                            indexing_result = await self.index_generated_files(
                                result.generated_files, repo_name, target_dir
                            )

                            # Add indexing metadata to result
                            result.pipeline_metadata["indexing"] = indexing_result
                            logger.info(
                                f"Indexed {indexing_result['files_indexed']} generated files for job {job.job_id}"
                            )

                        except Exception as e:
                            logger.warning(
                                f"Failed to index generated files for job {job.job_id}: {e}"
                            )
                            result.pipeline_metadata["indexing_error"] = str(e)

                    # Update job with result
                    job.result = result
                    job.completed_at = datetime.now()
                    job.status = "completed" if result.success else "failed"

                    if not result.success:
                        job.error_message = ", ".join(result.errors)

                    # Record job completion
                    # if self.config.enable_monitoring:
                    #     self.monitoring_service.record_job_end(
                    #         job.job_id,
                    #         success=result.success,
                    #         metrics=result.pipeline_metadata.get("metrics", {})
                    #     )

                    logger.info(f"Completed generation job {job.job_id}: {job.status}")

            except asyncio.TimeoutError:
                job.status = "failed"
                job.error_message = "Generation timed out"
                job.completed_at = datetime.now()
                logger.error(f"Generation job {job.job_id} timed out")

            except Exception as e:
                job.status = "failed"
                job.error_message = str(e)
                job.completed_at = datetime.now()
                logger.error(f"Generation job {job.job_id} failed: {e}")

            finally:
                # Move to completed jobs
                self.completed_jobs[job.job_id] = job
                self.active_jobs.pop(job.job_id, None)

    async def _execute_realtime_generation_job(self, job):
        """
        Execute a real-time generation job with progress monitoring.

        Args:
            job: Real-time generation job to execute
        """
        async with self.job_semaphore:
            try:
                # Create a new session for this background task to avoid session conflicts
                async with async_session_factory() as background_session:
                    # Update job status
                    job.status = "running"
                    job.started_at = datetime.now()

                    # Create a new real-time pipeline with the background session
                    from app.services.code_generation.generation.realtime_pipeline import (
                        RealtimeGenerationPipeline,
                    )

                    background_realtime_pipeline = RealtimeGenerationPipeline(
                        background_session
                    )

                    # Validate file paths if target_file_path is provided
                    if job.request.target_file_path:
                        validation_result = await self.validate_file_paths(
                            [job.request.target_file_path]
                        )
                        if validation_result["nonexistent_paths"]:
                            logger.info(
                                f"Target path {job.request.target_file_path} does not exist, will create during generation"
                            )

                    # Execute generation with real-time monitoring and timeout
                    result = await asyncio.wait_for(
                        background_realtime_pipeline.generate_code_with_realtime(
                            request=job.request,
                            generation_id=job.job_id,
                            project_id=job.project_id,
                            user_id=job.user_id,
                        ),
                        timeout=self.config.job_timeout_seconds,
                    )

                    # Index generated files if target_file_path was provided and generation was successful
                    if (
                        result.success
                        and job.request.target_file_path
                        and result.generated_files
                    ):
                        try:
                            # Determine repository name for indexing
                            repo_name = job.request.repository_name or "generated"
                            target_dir = (
                                str(Path(job.request.target_file_path).parent)
                                if Path(job.request.target_file_path).is_file()
                                else job.request.target_file_path
                            )

                            indexing_result = await self.index_generated_files(
                                result.generated_files, repo_name, target_dir
                            )

                            # Add indexing metadata to result
                            result.pipeline_metadata["indexing"] = indexing_result
                            logger.info(
                                f"Indexed {indexing_result['files_indexed']} generated files for real-time job {job.job_id}"
                            )

                        except Exception as e:
                            logger.warning(
                                f"Failed to index generated files for real-time job {job.job_id}: {e}"
                            )
                            result.pipeline_metadata["indexing_error"] = str(e)

                    # Update job with result
                    job.result = result
                    job.completed_at = datetime.now()
                    job.status = "completed" if result.success else "failed"
                    job.progress_percentage = 100

                    if not result.success:
                        job.error_message = ", ".join(result.errors)

                    logger.info(
                        f"Completed real-time generation job {job.job_id}: {job.status}"
                    )

            except asyncio.TimeoutError:
                job.status = "failed"
                job.error_message = "Real-time generation timed out"
                job.completed_at = datetime.now()
                logger.error(f"Real-time generation job {job.job_id} timed out")

            except Exception as e:
                job.status = "failed"
                job.error_message = str(e)
                job.completed_at = datetime.now()
                logger.error(f"Real-time generation job {job.job_id} failed: {e}")

            finally:
                # Move to completed jobs
                self.completed_jobs[job.job_id] = job
                self.active_jobs.pop(job.job_id, None)

    async def get_job_status(self, job_id: str) -> Optional[Dict[str, Any]]:
        """
        Get the status of a generation job.

        Args:
            job_id: The job ID to check

        Returns:
            Job status information or None if job not found
        """
        # Check active jobs
        if job_id in self.active_jobs:
            job = self.active_jobs[job_id]
            return {
                "job_id": job.job_id,
                "status": job.status,
                "created_at": job.created_at.isoformat(),
                "started_at": job.started_at.isoformat() if job.started_at else None,
                "progress": job.progress,
            }

        # Check completed jobs
        if job_id in self.completed_jobs:
            job = self.completed_jobs[job_id]
            result = {
                "job_id": job.job_id,
                "status": job.status,
                "created_at": job.created_at.isoformat(),
                "started_at": job.started_at.isoformat() if job.started_at else None,
                "completed_at": (
                    job.completed_at.isoformat() if job.completed_at else None
                ),
                "error_message": job.error_message,
            }

            if job.result:
                result["generated_code"] = (
                    job.result.generated_code
                )  # Legacy compatibility
                result["generated_files"] = job.result.generated_files
                result["processing_time_ms"] = job.result.total_time_ms
                result["success"] = job.result.success

            return result

        return None

    async def cancel_job(self, job_id: str) -> bool:
        """
        Cancel a running generation job.

        Args:
            job_id: The job ID to cancel

        Returns:
            True if job was cancelled, False otherwise
        """
        if job_id in self.active_jobs:
            job = self.active_jobs[job_id]
            job.status = "cancelled"
            job.completed_at = datetime.now()
            job.error_message = "Job cancelled by user"

            # Move to completed jobs
            self.completed_jobs[job_id] = job
            self.active_jobs.pop(job_id, None)

            logger.info(f"Cancelled generation job: {job_id}")
            return True

        return False

    async def validate_file_paths(self, file_paths: List[str]) -> Dict[str, Any]:
        """
        Validate if file paths exist and return detailed information.

        Args:
            file_paths: List of file paths to validate

        Returns:
            Dictionary with validation results for each path
        """
        validation_results = {
            "total_paths": len(file_paths),
            "existing_files": [],
            "existing_directories": [],
            "nonexistent_paths": [],
            "validation_summary": {},
        }

        for file_path in file_paths:
            try:
                path_obj = Path(file_path)

                if path_obj.exists():
                    if path_obj.is_file():
                        validation_results["existing_files"].append(str(file_path))
                    elif path_obj.is_dir():
                        validation_results["existing_directories"].append(
                            str(file_path)
                        )
                else:
                    validation_results["nonexistent_paths"].append(str(file_path))

            except Exception as e:
                logger.warning(f"Error validating path {file_path}: {e}")
                validation_results["nonexistent_paths"].append(str(file_path))

        # Create summary
        validation_results["validation_summary"] = {
            "existing_count": len(validation_results["existing_files"])
            + len(validation_results["existing_directories"]),
            "nonexistent_count": len(validation_results["nonexistent_paths"]),
            "needs_indexing": validation_results["nonexistent_paths"],
        }

        logger.info(
            f"Validated {len(file_paths)} file paths: {len(validation_results['existing_files'])} files, "
            f"{len(validation_results['existing_directories'])} directories, "
            f"{len(validation_results['nonexistent_paths'])} nonexistent"
        )

        return validation_results

    async def index_generated_files(
        self,
        generated_files: Dict[str, str],
        repository_name: str,
        target_directory: str,
    ) -> Dict[str, Any]:
        """
        Index newly generated files in the knowledge base and vector store.

        Args:
            generated_files: Dictionary of filename to content
            repository_name: Name of the repository
            target_directory: Directory where files were saved

        Returns:
            Dictionary with indexing results
        """
        indexing_results = {
            "files_indexed": 0,
            "patterns_extracted": 0,
            "vector_store_indexed": 0,
            "errors": [],
            "file_results": {},
        }

        try:
            # Index each generated file
            for filename, content in generated_files.items():
                file_result = {
                    "indexed": False,
                    "patterns_extracted": 0,
                    "vector_indexed": False,
                    "error": None,
                }

                try:
                    file_path = os.path.join(target_directory, filename)

                    # Extract patterns from the generated file
                    patterns = await self._extract_patterns_from_generated_file(
                        content, filename, repository_name, file_path
                    )

                    if patterns:
                        # Store patterns in knowledge base
                        stored_count = await self.knowledge_base._store_patterns(
                            patterns
                        )
                        indexing_results["patterns_extracted"] += stored_count
                        file_result["patterns_extracted"] = stored_count

                        # Update pattern index
                        await self.knowledge_base._update_pattern_index(patterns)

                    # Index in vector store for retrieval
                    vector_result = await self._index_file_in_vector_store(
                        content, filename, repository_name, file_path
                    )

                    if vector_result["success"]:
                        indexing_results["vector_store_indexed"] += 1
                        file_result["vector_indexed"] = True

                    file_result["indexed"] = True
                    indexing_results["files_indexed"] += 1

                except Exception as e:
                    error_msg = f"Failed to index {filename}: {str(e)}"
                    logger.error(error_msg)
                    file_result["error"] = error_msg
                    indexing_results["errors"].append(error_msg)

                indexing_results["file_results"][filename] = file_result

            logger.info(
                f"Indexed {indexing_results['files_indexed']} generated files: "
                f"{indexing_results['patterns_extracted']} patterns extracted, "
                f"{indexing_results['vector_store_indexed']} vector indexed"
            )

        except Exception as e:
            logger.error(f"Error during file indexing: {e}")
            indexing_results["errors"].append(str(e))

        return indexing_results

    async def _extract_patterns_from_generated_file(
        self, content: str, filename: str, repository_name: str, file_path: str
    ) -> List[Any]:
        """
        Extract patterns from a generated file content.

        Args:
            content: File content
            filename: Name of the file
            repository_name: Repository name
            file_path: Full path to the file

        Returns:
            List of extracted patterns
        """
        patterns = []

        try:
            # Use TreeSitter to parse the content
            parse_result = await self.knowledge_base.tree_sitter_service.parse_file(
                file_path
            )

            if not parse_result.success or not parse_result.content:
                # Fallback: basic pattern extraction from content
                return await self._extract_basic_patterns(
                    content, filename, repository_name, file_path
                )

            parsed_content = parse_result.content

            # Extract patterns based on file type
            if filename.endswith(".tf"):
                patterns.extend(
                    await self.knowledge_base._extract_resource_patterns(
                        parsed_content.get("resources", []), repository_name, file_path
                    )
                )
                patterns.extend(
                    await self.knowledge_base._extract_module_patterns(
                        parsed_content.get("modules", []), repository_name, file_path
                    )
                )
                patterns.extend(
                    await self.knowledge_base._extract_data_source_patterns(
                        parsed_content.get("data_sources", []),
                        repository_name,
                        file_path,
                    )
                )
                patterns.extend(
                    await self.knowledge_base._extract_variable_patterns(
                        parsed_content.get("variables", []), repository_name, file_path
                    )
                )

        except Exception as e:
            logger.warning(f"Failed to extract patterns from {filename}: {e}")
            # Fallback to basic pattern extraction
            patterns = await self._extract_basic_patterns(
                content, filename, repository_name, file_path
            )

        return patterns

    async def _extract_basic_patterns(
        self, content: str, filename: str, repository_name: str, file_path: str
    ) -> List[Any]:
        """
        Basic pattern extraction when TreeSitter parsing fails.

        Args:
            content: File content
            filename: File name
            repository_name: Repository name
            file_path: File path

        Returns:
            List of basic patterns
        """
        from app.services.code_generation.rag.knowledge_base import TerraformPattern

        patterns = []

        # Simple regex-based pattern extraction
        import re

        # Extract resource patterns
        resource_matches = re.findall(r'resource\s+"([^"]+)"\s+"([^"]+)"', content)
        for resource_type, resource_name in resource_matches:
            pattern_id = self.knowledge_base._generate_pattern_id(
                "resource", resource_type, resource_name, file_path
            )

            pattern = TerraformPattern(
                pattern_id=pattern_id,
                pattern_type="resource",
                resource_type=resource_type,
                code_snippet=f'resource "{resource_type}" "{resource_name}" {{...}}',
                metadata={
                    "resource_type": resource_type,
                    "resource_name": resource_name,
                    "file_path": file_path,
                    "repository": repository_name,
                },
                tags=[
                    "resource",
                    (
                        resource_type.split("_")[0]
                        if "_" in resource_type
                        else resource_type
                    ),
                ],
                confidence_score=0.7,
            )
            patterns.append(pattern)

        # Extract variable patterns
        variable_matches = re.findall(r'variable\s+"([^"]+)"', content)
        for var_name in variable_matches:
            pattern_id = self.knowledge_base._generate_pattern_id(
                "variable", var_name, "string", file_path
            )

            pattern = TerraformPattern(
                pattern_id=pattern_id,
                pattern_type="variable",
                code_snippet=f'variable "{var_name}" {{...}}',
                metadata={
                    "variable_name": var_name,
                    "file_path": file_path,
                    "repository": repository_name,
                },
                tags=["variable"],
                confidence_score=0.6,
            )
            patterns.append(pattern)

        return patterns

    async def _index_file_in_vector_store(
        self, content: str, filename: str, repository_name: str, file_path: str
    ) -> Dict[str, Any]:
        """
        Index a file in the vector store for retrieval.

        Args:
            content: File content
            filename: File name
            repository_name: Repository name
            file_path: File path

        Returns:
            Dictionary with indexing result
        """
        result = {"success": False, "error": None}

        try:
            # Generate embedding for the file content
            embedding = await self.rag_retriever._generate_query_embedding(content)

            if embedding:
                # Prepare data for vector store
                vectors = [embedding]
                content_chunks = [content]

                # Create file metadata
                file_metadata = {
                    "size": len(content.encode("utf-8")),
                    "language": "hcl" if filename.endswith(".tf") else "text",
                    "tokens_count": len(content.split()),  # Rough token count
                    "chunk_strategy": "single_chunk",
                }

                # Store in vector store using upsert_file_embedding
                await self.rag_retriever.vector_store.upsert_file_embedding(
                    repository_name=repository_name,
                    file_path=file_path,
                    vectors=vectors,
                    content_chunks=content_chunks,
                    file_metadata=file_metadata,
                    embedding_type="generated_code",
                )

                result["success"] = True
                logger.debug(f"Indexed {filename} in vector store")
            else:
                result["error"] = "Failed to generate embedding"

        except Exception as e:
            result["error"] = str(e)
            logger.error(f"Failed to index {filename} in vector store: {e}")

        return result

    async def get_similar_patterns(
        self,
        query: str,
        pattern_types: Optional[List[str]] = None,
        max_results: int = 5,
    ) -> KnowledgeBaseResult:
        """
        Get similar patterns from the knowledge base.

        Args:
            query: Search query for patterns
            pattern_types: Optional filter by pattern types
            max_results: Maximum number of results

        Returns:
            Knowledge base search results
        """
        if not self.config.enable_knowledge_base:
            return KnowledgeBaseResult(query=query)

        return await self.knowledge_base.find_matching_patterns(
            query=query, pattern_types=pattern_types, max_results=max_results
        )

    async def extract_patterns_from_repository(
        self, repository_name: str, repository_path: str
    ) -> Dict[str, int]:
        """
        Extract patterns from a repository for the knowledge base.

        Args:
            repository_name: Name of the repository
            repository_path: Path to the repository

        Returns:
            Extraction statistics
        """
        if not self.config.enable_knowledge_base:
            return {"error": "Knowledge base disabled"}

        return await self.knowledge_base.extract_patterns_from_repository(
            repository_name=repository_name, repository_path=repository_path
        )

    async def get_context_recommendations(
        self, query: str, repository_name: Optional[str] = None, max_documents: int = 5
    ) -> Dict[str, Any]:
        """
        Get context recommendations for a query.

        Args:
            query: The query to get recommendations for
            repository_name: Optional repository filter
            max_documents: Maximum documents to retrieve

        Returns:
            Dictionary with context recommendations
        """
        try:
            # Get RAG context
            retrieval_context = RetrievalContext(
                query=query, repository_name=repository_name, max_results=max_documents
            )

            retrieval_result = await self.rag_retriever.retrieve_context(
                retrieval_context
            )

            # Get knowledge base patterns
            kb_result = KnowledgeBaseResult(query=query)
            if self.config.enable_knowledge_base:
                kb_result = await self.knowledge_base.find_matching_patterns(
                    query=query, max_results=max_documents
                )

            return {
                "query": query,
                "retrieved_documents": len(retrieval_result.documents),
                "matched_patterns": len(kb_result.matched_patterns),
                "total_context_items": len(retrieval_result.documents)
                + len(kb_result.matched_patterns),
                "processing_time_ms": retrieval_result.processing_time_ms
                + kb_result.processing_time_ms,
                "recommendations": {
                    "use_repository_context": repository_name is not None,
                    "context_relevance": self._calculate_context_relevance(
                        retrieval_result, kb_result
                    ),
                    "suggested_scenario": self._suggest_generation_scenario(
                        query, retrieval_result
                    ),
                },
            }

        except Exception as e:
            logger.error(f"Failed to get context recommendations: {e}")
            return {"error": str(e)}

    def _calculate_context_relevance(
        self, retrieval_result: Any, kb_result: KnowledgeBaseResult
    ) -> float:
        """Calculate overall context relevance score."""
        rag_score = sum(
            doc.similarity_score for doc in retrieval_result.documents
        ) / max(len(retrieval_result.documents), 1)
        kb_score = sum(
            match.similarity_score for match in kb_result.matched_patterns
        ) / max(len(kb_result.matched_patterns), 1)

        # Weighted average
        return rag_score * 0.7 + kb_score * 0.3

    def _suggest_generation_scenario(self, query: str, retrieval_result: Any) -> str:
        """Suggest the most appropriate generation scenario based on query and context."""
        query_lower = query.lower()

        # Check for modification keywords
        if any(
            word in query_lower
            for word in ["modify", "update", "change", "edit", "fix"]
        ):
            return "MODIFY_RESOURCE"

        # Check for module keywords
        if "module" in query_lower:
            return "NEW_MODULE"

        # Check for variable keywords
        if "variable" in query_lower:
            return "NEW_VARIABLES"

        # Check for output keywords
        if "output" in query_lower:
            return "NEW_OUTPUTS"

        # Default to new resource
        return "NEW_RESOURCE"

    async def get_orchestrator_health(self) -> Dict[str, Any]:
        """
        Get health status of the orchestrator and all components.

        Returns:
            Health status dictionary
        """
        try:
            # Get component health
            pipeline_health = await self.generation_pipeline.get_pipeline_health()
            kb_stats = {}
            if self.config.enable_knowledge_base:
                kb_stats = await self.knowledge_base.get_knowledge_base_stats()

            # Get job statistics
            active_job_count = len(self.active_jobs)
            completed_job_count = len(self.completed_jobs)

            # Calculate success rate
            successful_jobs = sum(
                1 for job in self.completed_jobs.values() if job.status == "completed"
            )
            total_completed = len(self.completed_jobs)
            success_rate = (
                successful_jobs / total_completed if total_completed > 0 else 0.0
            )

            return {
                "status": "healthy",
                "timestamp": datetime.now().isoformat(),
                "components": {
                    "pipeline": pipeline_health,
                    "knowledge_base": kb_stats,
                    "rag_retriever": "operational",
                    "prompt_engineer": "operational",
                },
                "job_stats": {
                    "active_jobs": active_job_count,
                    "completed_jobs": completed_job_count,
                    "success_rate": success_rate,
                    "max_concurrent_jobs": self.config.max_concurrent_jobs,
                },
                "configuration": {
                    "enable_knowledge_base": self.config.enable_knowledge_base,
                    "enable_monitoring": self.config.enable_monitoring,
                    "default_provider": self.config.default_provider,
                    "job_timeout_seconds": self.config.job_timeout_seconds,
                },
            }

        except Exception as e:
            logger.error(f"Health check failed: {e}")
            return {
                "status": "unhealthy",
                "error": str(e),
                "timestamp": datetime.now().isoformat(),
            }

    async def cleanup_completed_jobs(self, max_age_hours: int = 24):
        """
        Clean up old completed jobs to free memory.

        Args:
            max_age_hours: Maximum age of jobs to keep (in hours)
        """
        try:
            cutoff_time = datetime.now().replace(
                hour=datetime.now().hour - max_age_hours
            )

            jobs_to_remove = []
            for job_id, job in self.completed_jobs.items():
                if job.completed_at and job.completed_at < cutoff_time:
                    jobs_to_remove.append(job_id)

            for job_id in jobs_to_remove:
                del self.completed_jobs[job_id]

            logger.info(f"Cleaned up {len(jobs_to_remove)} old jobs")

        except Exception as e:
            logger.error(f"Failed to cleanup jobs: {e}")

    async def get_generation_history(
        self, limit: int = 10, status_filter: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Get generation job history.

        Args:
            limit: Maximum number of jobs to return
            status_filter: Optional filter by job status

        Returns:
            List of job history records
        """
        try:
            jobs = list(self.completed_jobs.values())

            # Apply status filter
            if status_filter:
                jobs = [job for job in jobs if job.status == status_filter]

            # Sort by completion time (most recent first)
            jobs.sort(key=lambda x: x.completed_at or x.created_at, reverse=True)

            # Limit results
            jobs = jobs[:limit]

            # Convert to dictionaries
            history = []
            for job in jobs:
                record = {
                    "job_id": job.job_id,
                    "status": job.status,
                    "created_at": job.created_at.isoformat(),
                    "completed_at": (
                        job.completed_at.isoformat() if job.completed_at else None
                    ),
                    "query": (
                        job.request.query[:100] + "..."
                        if len(job.request.query) > 100
                        else job.request.query
                    ),
                    "scenario": job.request.scenario.value,
                    "repository": job.request.repository_name,
                    "error_message": job.error_message,
                }

                if job.result:
                    record["processing_time_ms"] = job.result.total_time_ms
                    record["code_length"] = len(job.result.generated_code)

                history.append(record)

            return history

        except Exception as e:
            logger.error(f"Failed to get generation history: {e}")
            return []
