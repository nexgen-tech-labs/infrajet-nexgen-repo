"""
Real-time Enhanced Code Generation Orchestrator.

This module extends the existing CodeGenerationOrchestrator to include
real-time monitoring capabilities, providing WebSocket-based progress
updates, file creation notifications, and completion/failure events.
"""

import asyncio
import uuid
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, List
from dataclasses import dataclass, field
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.code_generation.orchestrator import (
    CodeGenerationOrchestrator,
    GenerationJob,
    OrchestratorConfig,
)
from app.services.code_generation.generation.prompt_engineer import GenerationScenario
from app.services.code_generation.generation.pipeline import (
    GenerationRequest,
    GenerationResult,
)
from app.services.realtime_service import realtime_service, GenerationStatus
from app.models.project import CodeGeneration, GenerationStatus as ModelGenerationStatus
from app.services.chat_service import ChatService
from app.models.chat import MessageType
from logconfig.logger import get_logger

logger = get_logger()


@dataclass
class RealtimeGenerationJob(GenerationJob):
    """
    Enhanced generation job with real-time monitoring capabilities.

    Extends the base GenerationJob to support real-time progress tracking,
    WebSocket notifications, and detailed progress reporting.
    """

    user_id: Optional[int] = None
    supabase_user_id: Optional[str] = None
    project_id: Optional[str] = None
    progress_percentage: int = 0
    current_step: str = "Initializing..."
    estimated_completion: Optional[datetime] = None
    files_generated: List[str] = field(default_factory=list)
    enable_realtime: bool = True


class RealtimeCodeGenerationOrchestrator(CodeGenerationOrchestrator):
    """
    Enhanced orchestrator with real-time monitoring capabilities.

    This class extends the base CodeGenerationOrchestrator to provide:
    - Real-time progress updates via WebSocket
    - File creation notifications during generation
    - Generation completion and failure event handling
    - Progress percentage tracking with estimated completion times
    """

    def __init__(self, db_session: AsyncSession):
        """
        Initialize the real-time code generation orchestrator.

        Args:
            db_session: Database session for all operations
        """
        super().__init__(db_session)

        # Real-time service for WebSocket communication
        self.realtime_service = realtime_service

        # Progress tracking configuration
        self.progress_steps = [
            ("Initializing generation request", 5),
            ("Retrieving context from knowledge base", 15),
            ("Analyzing requirements and patterns", 25),
            ("Generating code with LLM", 60),
            ("Validating generated code", 75),
            ("Organizing and formatting files", 85),
            ("Saving files to storage", 95),
            ("Finalizing generation", 100),
        ]

        logger.info(
            "RealtimeCodeGenerationOrchestrator initialized with real-time monitoring"
        )

    async def generate_code_with_realtime_monitoring(
        self,
        query: str,
        user_id: int,
        project_id: Optional[str] = None,
        scenario: GenerationScenario = GenerationScenario.NEW_RESOURCE,
        enable_realtime: bool = True,
        supabase_user_id: Optional[str] = None,
        **kwargs,
    ) -> GenerationResult:
        """
        Generate code with real-time monitoring and progress updates.

        Args:
            query: User's code generation request
            user_id: User ID for real-time notifications
            project_id: Optional project ID for context
            scenario: Generation scenario
            enable_realtime: Whether to enable real-time updates
            **kwargs: Additional generation parameters

        Returns:
            GenerationResult with generated files and metadata
        """
        generation_id = str(uuid.uuid4())

        try:
            # Emit generation started event
            if enable_realtime:
                await self.realtime_service.emit_generation_started(
                    generation_id=generation_id,
                    project_id=project_id or "default",
                    user_id=user_id,
                    prompt=query,
                    estimated_duration=self._estimate_generation_duration(
                        query, scenario
                    ),
                )

            # Create generation request with monitoring
            request = GenerationRequest(
                query=query,
                scenario=scenario,
                repository_name=kwargs.get("repository_name"),
                existing_code=kwargs.get("existing_code"),
                target_file_path=kwargs.get("target_file_path"),
                provider_type=kwargs.get("provider_type", self.config.default_provider),
                temperature=kwargs.get("temperature"),
                max_tokens=kwargs.get("max_tokens"),
                max_context_documents=kwargs.get("max_context_documents", 5),
                similarity_threshold=kwargs.get("similarity_threshold", 0.7),
                cloud_provider=kwargs.get("cloud_provider", "AWS"),
            )
    
            # Add user and project context for autonomous interaction
            request.user_id = user_id
            request.project_id = project_id

            # Execute generation with progress monitoring
            result = await self._execute_generation_with_monitoring(
                request=request,
                generation_id=generation_id,
                user_id=user_id,
                project_id=project_id,
                enable_realtime=enable_realtime,
                supabase_user_id=supabase_user_id,
            )

            # Emit completion or failure event
            if enable_realtime:
                if result.success:
                    await self.realtime_service.emit_generation_completed(
                        generation_id=generation_id,
                        project_id=project_id or "default",
                        user_id=user_id,
                        files_generated=list(result.generated_files.keys()),
                        generation_summary=self._create_generation_summary(result),
                    )
                else:
                    await self.realtime_service.emit_generation_failed(
                        generation_id=generation_id,
                        project_id=project_id or "default",
                        user_id=user_id,
                        error_message=", ".join(result.errors),
                        error_details={"pipeline_metadata": result.pipeline_metadata},
                    )

            return result

        except Exception as e:
            logger.error(f"Real-time generation failed: {e}")

            # Emit failure event
            if enable_realtime:
                await self.realtime_service.emit_generation_failed(
                    generation_id=generation_id,
                    project_id=project_id or "default",
                    user_id=user_id,
                    error_message=str(e),
                    error_details={"exception_type": type(e).__name__},
                )

            raise

    async def generate_code_async_with_realtime_monitoring(
        self,
        query: str,
        user_id: int,
        project_id: Optional[str] = None,
        scenario: GenerationScenario = GenerationScenario.NEW_RESOURCE,
        enable_realtime: bool = True,
        supabase_user_id: Optional[str] = None,
        **kwargs,
    ) -> str:
        """
        Generate code asynchronously with real-time monitoring.

        Args:
            query: User's code generation request
            user_id: User ID for real-time notifications
            project_id: Optional project ID for context
            scenario: Generation scenario
            enable_realtime: Whether to enable real-time updates
            **kwargs: Additional generation parameters

        Returns:
            Job ID for tracking the async generation
        """
        job_id = str(uuid.uuid4())

        # Create generation request
        request = GenerationRequest(
            query=query,
            scenario=scenario,
            repository_name=kwargs.get("repository_name"),
            existing_code=kwargs.get("existing_code"),
            target_file_path=kwargs.get("target_file_path"),
            provider_type=kwargs.get("provider_type", self.config.default_provider),
            temperature=kwargs.get("temperature"),
            max_tokens=kwargs.get("max_tokens"),
            max_context_documents=kwargs.get("max_context_documents", 5),
            similarity_threshold=kwargs.get("similarity_threshold", 0.7),
            cloud_provider=kwargs.get("cloud_provider", "AWS"),
        )

        # Add user and project context for autonomous interaction
        request.user_id = user_id
        request.project_id = project_id

        # Create real-time job
        job = RealtimeGenerationJob(
            job_id=job_id,
            status="pending",
            request=request,
            created_at=datetime.now(),
            user_id=user_id,
            supabase_user_id=supabase_user_id,
            project_id=project_id,
            enable_realtime=enable_realtime,
        )

        self.active_jobs[job_id] = job

        # Start async generation with real-time monitoring
        asyncio.create_task(self._execute_realtime_generation_job(job))

        logger.info(f"Started real-time generation job: {job_id}")
        return job_id

    async def _execute_generation_with_monitoring(
        self,
        request: GenerationRequest,
        generation_id: str,
        user_id: int,
        project_id: Optional[str],
        enable_realtime: bool,
        supabase_user_id: Optional[str] = None,
    ) -> GenerationResult:
        """
        Execute generation with step-by-step progress monitoring.

        Args:
            request: Generation request
            generation_id: Generation ID for tracking
            user_id: User ID for notifications
            project_id: Optional project ID
            enable_realtime: Whether to emit real-time updates

        Returns:
            GenerationResult
        """
        current_step_index = 0

        try:
            # Step 1: Initialize generation
            await self._emit_progress_update(
                generation_id,
                project_id,
                user_id,
                enable_realtime,
                current_step_index,
                "Initializing generation request...",
            )
            current_step_index += 1

            # Step 2: Retrieve context
            await self._emit_progress_update(
                generation_id,
                project_id,
                user_id,
                enable_realtime,
                current_step_index,
                "Retrieving context from knowledge base...",
            )

            # Get RAG context if available
            retrieval_context = None
            if hasattr(self, "rag_retriever"):
                try:
                    from app.services.code_generation.rag.retriever import (
                        RetrievalContext,
                    )

                    retrieval_context = RetrievalContext(
                        query=request.query,
                        repository_name=request.repository_name,
                        max_results=request.max_context_documents,
                    )
                    await self.rag_retriever.retrieve_context(retrieval_context)
                except Exception as e:
                    logger.warning(f"Failed to retrieve RAG context: {e}")

            current_step_index += 1

            # Step 3: Analyze requirements
            await self._emit_progress_update(
                generation_id,
                project_id,
                user_id,
                enable_realtime,
                current_step_index,
                "Analyzing requirements and patterns...",
            )
            current_step_index += 1

            # Step 4: Generate code
            await self._emit_progress_update(
                generation_id,
                project_id,
                user_id,
                enable_realtime,
                current_step_index,
                "Generating code with LLM...",
            )

            # Execute the actual generation using the parent class
            result = await self.generation_pipeline.generate_code(request)
            current_step_index += 1

            # Step 5: Validate code
            await self._emit_progress_update(
                generation_id,
                project_id,
                user_id,
                enable_realtime,
                current_step_index,
                "Validating generated code...",
            )
            current_step_index += 1

            # Step 6: Organize files
            await self._emit_progress_update(
                generation_id,
                project_id,
                user_id,
                enable_realtime,
                current_step_index,
                "Organizing and formatting files...",
            )

            # Emit file creation notifications
            if enable_realtime and result.success:
                for filename in result.generated_files.keys():
                    await self.realtime_service.emit_file_created(
                        project_id=project_id or "default",
                        user_id=user_id,
                        file_path=filename,
                        file_size=len(result.generated_files[filename].encode("utf-8")),
                        generation_id=generation_id,
                    )

            current_step_index += 1

            # Step 7: Save files
            await self._emit_progress_update(
                generation_id,
                project_id,
                user_id,
                enable_realtime,
                current_step_index,
                "Saving files to storage...",
            )
            current_step_index += 1

            # Step 8: Finalize
            await self._emit_progress_update(
                generation_id,
                project_id,
                user_id,
                enable_realtime,
                current_step_index,
                "Finalizing generation...",
            )

            return result

        except Exception as e:
            logger.error(
                f"Generation monitoring failed at step {current_step_index}: {e}"
            )
            raise

    async def _execute_realtime_generation_job(self, job: RealtimeGenerationJob):
        """
        Execute a real-time generation job with progress monitoring.

        Args:
            job: Real-time generation job to execute
        """
        async with self.job_semaphore:
            try:
                # Update job status
                job.status = "running"
                job.started_at = datetime.now()
                job.estimated_completion = datetime.now() + timedelta(
                    seconds=self._estimate_generation_duration(
                        job.request.query, job.request.scenario
                    )
                )

                # Emit generation started event
                if job.enable_realtime:
                    await self.realtime_service.emit_generation_started(
                        generation_id=job.job_id,
                        project_id=job.project_id or "default",
                        user_id=job.user_id,
                        prompt=job.request.query,
                        estimated_duration=self._estimate_generation_duration(
                            job.request.query, job.request.scenario
                        ),
                    )

                # Execute generation with monitoring
                result = await self._execute_generation_with_monitoring(
                    request=job.request,
                    generation_id=job.job_id,
                    user_id=job.user_id,
                    project_id=job.project_id,
                    enable_realtime=job.enable_realtime,
                    supabase_user_id=job.supabase_user_id,
                )

                # Update job with result
                job.result = result
                job.completed_at = datetime.now()
                job.status = "completed" if result.success else "failed"
                job.progress_percentage = 100

                if not result.success:
                    job.error_message = ", ".join(result.errors)

                # Emit completion or failure event
                if job.enable_realtime:
                    if result.success:
                        generation_summary = self._create_generation_summary(result)
                        await self.realtime_service.emit_generation_completed(
                            generation_id=job.job_id,
                            project_id=job.project_id or "default",
                            user_id=job.user_id,
                            files_generated=list(result.generated_files.keys()),
                            generation_summary=generation_summary,
                        )

                        # Schedule chat message saving for after transaction completes
                        if job.request.project_id and job.supabase_user_id:
                            asyncio.create_task(self._save_generation_summary_to_chat(
                                project_id=job.request.project_id,
                                user_id=job.supabase_user_id,
                                generation_summary=generation_summary
                            ))
                    else:
                        await self.realtime_service.emit_generation_failed(
                            generation_id=job.job_id,
                            project_id=job.project_id or "default",
                            user_id=job.user_id,
                            error_message=job.error_message,
                            error_details={
                                "pipeline_metadata": result.pipeline_metadata
                            },
                        )

                logger.info(
                    f"Real-time generation job {job.job_id} completed: {job.status}"
                )

            except asyncio.TimeoutError:
                job.status = "failed"
                job.error_message = "Generation timed out"
                job.completed_at = datetime.now()

                if job.enable_realtime:
                    await self.realtime_service.emit_generation_failed(
                        generation_id=job.job_id,
                        project_id=job.project_id or "default",
                        user_id=job.user_id,
                        error_message="Generation timed out",
                        error_details={
                            "timeout_seconds": self.config.job_timeout_seconds
                        },
                    )

                logger.error(f"Real-time generation job {job.job_id} timed out")

            except Exception as e:
                job.status = "failed"
                job.error_message = str(e)
                job.completed_at = datetime.now()

                if job.enable_realtime:
                    await self.realtime_service.emit_generation_failed(
                        generation_id=job.job_id,
                        project_id=job.project_id or "default",
                        user_id=job.user_id,
                        error_message=str(e),
                        error_details={"exception_type": type(e).__name__},
                    )

                logger.error(f"Real-time generation job {job.job_id} failed: {e}")

            finally:
                # Move to completed jobs
                self.completed_jobs[job.job_id] = job
                self.active_jobs.pop(job.job_id, None)

    async def _emit_progress_update(
        self,
        generation_id: str,
        project_id: Optional[str],
        user_id: int,
        enable_realtime: bool,
        step_index: int,
        current_step: str,
    ):
        """
        Emit a progress update for the current generation step.

        Args:
            generation_id: Generation ID
            project_id: Optional project ID
            user_id: User ID
            enable_realtime: Whether to emit real-time updates
            step_index: Current step index
            current_step: Description of current step
        """
        if not enable_realtime:
            return

        # Calculate progress percentage based on step
        if step_index < len(self.progress_steps):
            progress_percentage = self.progress_steps[step_index][1]
        else:
            progress_percentage = 100

        # Calculate estimated completion
        estimated_completion = None
        if step_index < len(self.progress_steps) - 1:
            remaining_steps = len(self.progress_steps) - step_index
            estimated_seconds = remaining_steps * 10  # Rough estimate
            estimated_completion = datetime.now() + timedelta(seconds=estimated_seconds)

        await self.realtime_service.emit_generation_progress(
            generation_id=generation_id,
            project_id=project_id or "default",
            user_id=user_id,
            status=GenerationStatus.IN_PROGRESS,
            progress_percentage=progress_percentage,
            current_step=current_step,
            estimated_completion=estimated_completion,
        )

        logger.debug(f"Progress update: {progress_percentage}% - {current_step}")

    def _estimate_generation_duration(
        self, query: str, scenario: GenerationScenario
    ) -> int:
        """
        Estimate generation duration based on query complexity and scenario.

        Args:
            query: Generation query
            scenario: Generation scenario

        Returns:
            Estimated duration in seconds
        """
        base_duration = 30  # Base 30 seconds

        # Adjust based on query length
        query_length_factor = min(len(query) / 100, 2.0)  # Max 2x multiplier

        # Adjust based on scenario complexity
        scenario_multipliers = {
            GenerationScenario.NEW_RESOURCE: 1.0,
            GenerationScenario.MODIFY_RESOURCE: 1.2,
            GenerationScenario.COMPLETE_FILE: 2.0,
            GenerationScenario.NEW_MODULE: 1.5,
        }

        scenario_factor = scenario_multipliers.get(scenario, 1.0)

        estimated_duration = int(base_duration * query_length_factor * scenario_factor)
        return max(estimated_duration, 15)  # Minimum 15 seconds

    def _create_generation_summary(self, result: GenerationResult) -> str:
        """
        Create a summary of the generation result.

        Args:
            result: Generation result

        Returns:
            Summary string
        """
        if not result.success:
            return "Generation failed"

        file_count = len(result.generated_files)
        file_types = set()

        for filename in result.generated_files.keys():
            if "." in filename:
                file_types.add(filename.split(".")[-1])

        summary_parts = [f"Generated {file_count} file{'s' if file_count != 1 else ''}"]

        if file_types:
            types_str = ", ".join(sorted(file_types))
            summary_parts.append(f"Types: {types_str}")

        if result.total_time_ms:
            summary_parts.append(f"Completed in {result.total_time_ms}ms")

        return " | ".join(summary_parts)

    async def get_realtime_job_status(self, job_id: str) -> Optional[Dict[str, Any]]:
        """
        Get enhanced job status with real-time information.

        Args:
            job_id: Job ID to check

        Returns:
            Enhanced job status or None if not found
        """
        base_status = await self.get_job_status(job_id)

        if not base_status:
            return None

        # Add real-time specific information if it's a realtime job
        if job_id in self.active_jobs:
            job = self.active_jobs[job_id]
            if isinstance(job, RealtimeGenerationJob):
                base_status.update(
                    {
                        "progress_percentage": job.progress_percentage,
                        "current_step": job.current_step,
                        "estimated_completion": (
                            job.estimated_completion.isoformat()
                            if job.estimated_completion
                            else None
                        ),
                        "files_generated": job.files_generated,
                        "enable_realtime": job.enable_realtime,
                        "user_id": job.user_id,
                        "project_id": job.project_id,
                    }
                )

        return base_status

    async def _save_generation_summary_to_chat(
        self, project_id: str, user_id: str, generation_summary: str
    ):
        """
        Save generation summary to chat outside of transaction context.

        Args:
            project_id: Project ID
            user_id: Supabase user ID
            generation_summary: Generation summary text
        """
        try:
            # Create a new database session for this operation
            from app.db.session import get_async_db

            async for db in get_async_db():
                chat_service = ChatService(db)
                await chat_service.save_message(
                    project_id=project_id,
                    user_id=user_id,
                    message_content=f"Code generation completed successfully. {generation_summary}",
                    message_type=MessageType.SYSTEM
                )
                break  # Only use the first session

        except Exception as e:
            logger.error(f"Failed to save generation summary to chat: {e}")
