"""
Real-time Enhanced Generation Pipeline for Terraform code generation.

This module extends the existing AutonomousGenerationPipeline to include
real-time progress monitoring and WebSocket notifications for generation
status changes, file creation events, and completion/failure handling.
"""

import asyncio
import time
import uuid
from typing import Dict, Any, Optional, List
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.code_generation.generation.pipeline import (
    AutonomousGenerationPipeline,
    GenerationRequest,
    GenerationResult,
    PipelineStage,
    PipelineMetrics,
)
from app.services.realtime_service import realtime_service, GenerationStatus
from app.services.code_generation.generation.prompt_engineer import GenerationScenario
from logconfig.logger import get_logger

logger = get_logger()


@dataclass
class RealtimeGenerationContext:
    """Context for real-time generation monitoring."""

    generation_id: str
    project_id: Optional[str] = None
    user_id: Optional[int] = None
    start_time: datetime = field(default_factory=datetime.utcnow)
    estimated_duration: Optional[int] = None  # seconds
    current_stage: str = "initializing"
    progress_percentage: int = 0
    files_generated: List[str] = field(default_factory=list)


class RealtimeGenerationPipeline(AutonomousGenerationPipeline):
    """
    Enhanced generation pipeline with real-time monitoring capabilities.

    This class extends the base AutonomousGenerationPipeline to emit
    real-time events during code generation, providing progress updates,
    file creation notifications, and completion/failure events.
    """

    def __init__(self, db_session: AsyncSession):
        """
        Initialize the real-time generation pipeline.

        Args:
            db_session: Database session for vector store operations
        """
        super().__init__(db_session)
        self.realtime_service = realtime_service

        # Stage progress weights for calculating overall progress
        self.stage_weights = {
            PipelineStage.INITIALIZED: 0,
            PipelineStage.CONTEXT_RETRIEVAL: 15,
            PipelineStage.PROMPT_ENGINEERING: 25,
            PipelineStage.CODE_GENERATION: 70,
            PipelineStage.VALIDATION: 90,
            PipelineStage.COMPLETED: 100,
            PipelineStage.FAILED: 0,
        }

        logger.info("RealtimeGenerationPipeline initialized with real-time monitoring")

    async def generate_code_with_realtime(
        self,
        request: GenerationRequest,
        generation_id: Optional[str] = None,
        project_id: Optional[str] = None,
        user_id: Optional[int] = None,
    ) -> GenerationResult:
        """
        Execute the complete generation pipeline with real-time monitoring.

        Args:
            request: Generation request with query and parameters
            generation_id: Unique generation identifier for tracking
            project_id: Project identifier for notifications
            user_id: User identifier for notifications

        Returns:
            GenerationResult with generated code and metadata
        """
        # Create generation context for real-time tracking
        if not generation_id:
            generation_id = str(uuid.uuid4())

        context = RealtimeGenerationContext(
            generation_id=generation_id,
            project_id=project_id,
            user_id=user_id,
            estimated_duration=self._estimate_generation_duration(request),
        )

        try:
            # Emit generation started event
            await self._emit_generation_started(context, request)

            # Execute the generation pipeline with real-time updates
            result = await self._execute_pipeline_with_monitoring(request, context)

            if result.success:
                # Emit generation completed event
                await self._emit_generation_completed(context, result)
            else:
                # Emit generation failed event
                await self._emit_generation_failed(context, result)

            return result

        except Exception as e:
            logger.error(f"Real-time generation failed: {e}")
            await self._emit_generation_failed(context, None, str(e))
            raise

    async def _execute_pipeline_with_monitoring(
        self, request: GenerationRequest, context: RealtimeGenerationContext
    ) -> GenerationResult:
        """
        Execute the generation pipeline with real-time progress monitoring.

        Args:
            request: Generation request
            context: Real-time generation context

        Returns:
            GenerationResult with generated code and metadata
        """
        start_time = time.time()
        result = GenerationResult(request=request)
        metrics = PipelineMetrics()

        try:
            # Ensure session is in a clean state
            await self.db.rollback()

            # Stage 1: Context Retrieval
            await self._update_stage_with_realtime(
                context,
                PipelineStage.CONTEXT_RETRIEVAL,
                "Retrieving relevant context...",
            )

            retrieval_result = await self._retrieve_context(request, metrics)
            result.stage_results["context_retrieval"] = {
                "documents_found": len(retrieval_result.documents),
                "processing_time_ms": retrieval_result.processing_time_ms,
            }

            # Stage 2: Prompt Engineering
            await self._update_stage_with_realtime(
                context,
                PipelineStage.PROMPT_ENGINEERING,
                "Engineering optimal prompt...",
            )

            engineered_prompt = await self._engineer_prompt(
                request, retrieval_result, metrics
            )
            result.stage_results["prompt_engineering"] = {
                "prompt_length": len(engineered_prompt.user_message),
                "context_documents_used": request.max_context_documents,
            }

            # Stage 3: Code Generation
            await self._update_stage_with_realtime(
                context, PipelineStage.CODE_GENERATION, "Generating Terraform code..."
            )

            generated_files = await self._generate_terraform_project_with_monitoring(
                request, engineered_prompt, metrics, context
            )
            result.generated_files = generated_files

            # For backward compatibility, set generated_code to the main file content
            if "main.tf" in generated_files:
                result.generated_code = generated_files["main.tf"]
            elif generated_files:
                result.generated_code = list(generated_files.values())[0]

            result.stage_results["code_generation"] = {
                "files_generated": len(generated_files),
                "total_code_length": sum(
                    len(content) for content in generated_files.values()
                ),
                "generation_time_ms": metrics.code_generation_time,
            }

            # Stage 4: Validation and Error Correction (if enabled)
            if self.enable_validation:
                await self._update_stage_with_realtime(
                    context,
                    PipelineStage.VALIDATION,
                    "Validating and correcting generated code...",
                )

                validation_result = await self._validate_and_correct_generated_files(
                    generated_files, request.target_file_path, metrics
                )
                result.stage_results["validation"] = validation_result

            # Mark as completed
            await self._update_stage_with_realtime(
                context, PipelineStage.COMPLETED, "Generation completed successfully!"
            )
            result.success = True

            # Save generated files if target_file_path is specified
            if request.target_file_path:
                files_to_save = result.generated_files
                if "validation" in result.stage_results:
                    validation_data = result.stage_results["validation"]
                    if "final_files" in validation_data:
                        files_to_save = validation_data["final_files"]
                        logger.info("Using corrected files for saving")

                save_result = await self._save_generated_files_to_directory(
                    files_to_save, request.target_file_path, result
                )
                result.stage_results["file_save"] = save_result

            # Update metrics
            result.total_time_ms = (time.time() - start_time) * 1000
            result.pipeline_metadata = {
                "metrics": metrics.__dict__,
                "stages_completed": len(result.stage_results),
                "final_stage": PipelineStage.COMPLETED.value,
                "realtime_context": {
                    "generation_id": context.generation_id,
                    "files_generated": context.files_generated,
                    "total_progress": context.progress_percentage,
                },
            }

            logger.info(
                f"Real-time pipeline completed successfully for generation {context.generation_id} "
                f"generated {len(generated_files)} files in {result.total_time_ms:.2f}ms"
            )

        except Exception as e:
            logger.error(f"Real-time pipeline failed: {e}")
            result.errors.append(str(e))
            result.success = False
            result.total_time_ms = (time.time() - start_time) * 1000
            await self._update_stage_with_realtime(
                context, PipelineStage.FAILED, f"Generation failed: {str(e)}"
            )

            # Rollback session on error to ensure clean state
            try:
                await self.db.rollback()
            except Exception as rollback_error:
                logger.warning(f"Failed to rollback session: {rollback_error}")

        return result

    async def _generate_terraform_project_with_monitoring(
        self,
        request: GenerationRequest,
        engineered_prompt,
        metrics: PipelineMetrics,
        context: RealtimeGenerationContext,
    ) -> Dict[str, str]:
        """
        Generate Terraform project with real-time file creation monitoring.

        Args:
            request: Generation request
            engineered_prompt: Engineered prompt for generation
            metrics: Pipeline metrics to update
            context: Real-time generation context

        Returns:
            Dictionary of filename to content
        """
        start_time = time.time()

        try:
            # Get LLM provider
            provider = self.provider_factory.get_provider(request.provider_type)

            # Create LLM request
            llm_request = self._create_llm_request(request, engineered_prompt)

            # Update progress for generation start
            await self._emit_progress_update(
                context,
                current_step="Sending request to LLM provider...",
                progress_percentage=self.stage_weights[PipelineStage.CODE_GENERATION]
                - 20,
            )

            # Generate code
            llm_response = await provider.generate(llm_request)

            if not llm_response.success:
                raise Exception(f"LLM generation failed: {llm_response.error}")

            # Update progress for parsing response
            await self._emit_progress_update(
                context,
                current_step="Parsing generated code into files...",
                progress_percentage=self.stage_weights[PipelineStage.CODE_GENERATION]
                - 10,
            )

            # Parse the response into multiple files
            generated_files = await self._parse_llm_response_to_files(
                llm_response.content, context
            )

            # Update metrics
            metrics.code_generation_time = (time.time() - start_time) * 1000
            metrics.tokens_used = llm_response.tokens_used or 0

            # Update context with generated files
            context.files_generated = list(generated_files.keys())

            # Emit file creation notifications for each generated file
            for filename in generated_files.keys():
                await self._emit_file_created(
                    context, filename, len(generated_files[filename])
                )

            logger.info(
                f"Generated {len(generated_files)} files for generation {context.generation_id}"
            )

            return generated_files

        except Exception as e:
            logger.error(f"Code generation with monitoring failed: {e}")
            raise

    async def _parse_llm_response_to_files(
        self, llm_content: str, context: RealtimeGenerationContext
    ) -> Dict[str, str]:
        """
        Parse LLM response into multiple Terraform files with real-time notifications.

        Args:
            llm_content: Raw content from LLM
            context: Real-time generation context

        Returns:
            Dictionary of filename to content
        """
        files = {}

        # Try to parse structured response first (if LLM returns JSON or structured format)
        try:
            import json
            import re

            # Look for JSON structure in the response
            json_match = re.search(r"\{.*\}", llm_content, re.DOTALL)
            if json_match:
                try:
                    parsed_json = json.loads(json_match.group())
                    if isinstance(parsed_json, dict) and any(
                        key.endswith(".tf") or key.endswith(".tfvars")
                        for key in parsed_json.keys()
                    ):
                        # This looks like a structured file response
                        for filename, content in parsed_json.items():
                            if isinstance(content, str) and content.strip():
                                files[filename] = content.strip()
                                await self._emit_progress_update(
                                    context,
                                    current_step=f"Parsed file: {filename}",
                                    progress_percentage=self.stage_weights[
                                        PipelineStage.CODE_GENERATION
                                    ]
                                    - 5,
                                )

                        if files:
                            return files
                except json.JSONDecodeError:
                    pass

            # Look for file blocks in the response
            file_blocks = re.findall(
                r"(?:```(?:hcl|terraform)?\s*)?(?:# |// )?(?:File: |Filename: )?([^\n]*\.(?:tf|tfvars))\s*\n(.*?)(?:```|(?=\n(?:# |// )?(?:File: |Filename: )[^\n]*\.(?:tf|tfvars))|\Z)",
                llm_content,
                re.DOTALL | re.IGNORECASE,
            )

            if file_blocks:
                for filename, content in file_blocks:
                    filename = filename.strip()
                    content = content.strip()
                    if filename and content:
                        files[filename] = content
                        await self._emit_progress_update(
                            context,
                            current_step=f"Parsed file: {filename}",
                            progress_percentage=self.stage_weights[
                                PipelineStage.CODE_GENERATION
                            ]
                            - 5,
                        )

                if files:
                    return files

            # Fallback: treat entire content as main.tf
            if llm_content.strip():
                files["main.tf"] = llm_content.strip()
                await self._emit_progress_update(
                    context,
                    current_step="Created main.tf file",
                    progress_percentage=self.stage_weights[
                        PipelineStage.CODE_GENERATION
                    ]
                    - 5,
                )

        except Exception as e:
            logger.warning(f"Error parsing LLM response to files: {e}")
            # Fallback to single file
            if llm_content.strip():
                files["main.tf"] = llm_content.strip()

        return files

    def _create_llm_request(self, request: GenerationRequest, engineered_prompt):
        """Create LLM request from generation request and engineered prompt."""
        from app.services.code_generation.llm_providers.base import LLMRequest

        return LLMRequest(
            system_message=engineered_prompt.system_message,
            user_message=engineered_prompt.user_message,
            temperature=request.temperature,
            max_tokens=request.max_tokens,
            metadata={
                "scenario": request.scenario.value,
                "query": request.query[:100],  # Truncated for metadata
                "repository": request.repository_name,
            },
        )

    async def _update_stage_with_realtime(
        self,
        context: RealtimeGenerationContext,
        stage: PipelineStage,
        step_description: str,
    ):
        """
        Update pipeline stage with real-time progress notification.

        Args:
            context: Real-time generation context
            stage: Current pipeline stage
            step_description: Description of current step
        """
        context.current_stage = stage.value
        context.progress_percentage = self.stage_weights.get(stage, 0)

        await self._emit_progress_update(
            context,
            current_step=step_description,
            progress_percentage=context.progress_percentage,
        )

    async def _emit_generation_started(
        self, context: RealtimeGenerationContext, request: GenerationRequest
    ):
        """
        Emit generation started event.

        Args:
            context: Real-time generation context
            request: Generation request
        """
        if context.user_id:
            await self.realtime_service.emit_generation_started(
                generation_id=context.generation_id,
                project_id=context.project_id or "unknown",
                user_id=context.user_id,
                prompt=request.query,
                estimated_duration=context.estimated_duration,
            )

    async def _emit_generation_completed(
        self, context: RealtimeGenerationContext, result: GenerationResult
    ):
        """
        Emit generation completed event.

        Args:
            context: Real-time generation context
            result: Generation result
        """
        if context.user_id:
            # Create generation summary
            summary = self._create_generation_summary(result)

            await self.realtime_service.emit_generation_completed(
                generation_id=context.generation_id,
                project_id=context.project_id or "unknown",
                user_id=context.user_id,
                files_generated=context.files_generated,
                generation_summary=summary,
            )

    async def _emit_generation_failed(
        self,
        context: RealtimeGenerationContext,
        result: Optional[GenerationResult],
        error_message: Optional[str] = None,
    ):
        """
        Emit generation failed event.

        Args:
            context: Real-time generation context
            result: Generation result (may be None)
            error_message: Optional error message override
        """
        if context.user_id:
            error_msg = error_message
            if not error_msg and result and result.errors:
                error_msg = "; ".join(result.errors)
            if not error_msg:
                error_msg = "Unknown generation error"

            await self.realtime_service.emit_generation_failed(
                generation_id=context.generation_id,
                project_id=context.project_id or "unknown",
                user_id=context.user_id,
                error_message=error_msg,
                error_details={
                    "stage": context.current_stage,
                    "progress": context.progress_percentage,
                    "files_generated": context.files_generated,
                },
            )

    async def _emit_progress_update(
        self,
        context: RealtimeGenerationContext,
        current_step: str,
        progress_percentage: int,
    ):
        """
        Emit progress update event.

        Args:
            context: Real-time generation context
            current_step: Description of current step
            progress_percentage: Progress percentage (0-100)
        """
        if context.user_id:
            # Calculate estimated completion time
            estimated_completion = None
            if context.estimated_duration and progress_percentage > 0:
                elapsed_seconds = (
                    datetime.utcnow() - context.start_time
                ).total_seconds()
                if progress_percentage > 5:  # Avoid division by very small numbers
                    total_estimated = (elapsed_seconds / progress_percentage) * 100
                    remaining_seconds = max(0, total_estimated - elapsed_seconds)
                    estimated_completion = datetime.utcnow() + timedelta(
                        seconds=remaining_seconds
                    )

            await self.realtime_service.emit_generation_progress(
                generation_id=context.generation_id,
                project_id=context.project_id or "unknown",
                user_id=context.user_id,
                status=GenerationStatus.IN_PROGRESS,
                progress_percentage=min(progress_percentage, 100),
                current_step=current_step,
                estimated_completion=estimated_completion,
                files_generated=context.files_generated,
            )

    async def _emit_file_created(
        self, context: RealtimeGenerationContext, filename: str, file_size: int
    ):
        """
        Emit file created event.

        Args:
            context: Real-time generation context
            filename: Name of created file
            file_size: Size of created file in bytes
        """
        if context.user_id and context.project_id:
            await self.realtime_service.emit_file_created(
                project_id=context.project_id,
                user_id=context.user_id,
                file_path=filename,
                file_size=file_size,
                generation_id=context.generation_id,
            )

    def _estimate_generation_duration(self, request: GenerationRequest) -> int:
        """
        Estimate generation duration based on request complexity.

        Args:
            request: Generation request

        Returns:
            Estimated duration in seconds
        """
        base_duration = 30  # Base 30 seconds

        # Add time based on query complexity
        query_length_factor = min(len(request.query) / 100, 3)  # Max 3x multiplier

        # Add time based on scenario complexity
        scenario_multipliers = {
            GenerationScenario.NEW_RESOURCE: 1.0,
            GenerationScenario.MODIFY_RESOURCE: 1.2,
            GenerationScenario.NEW_MODULE: 1.5,
            GenerationScenario.NEW_VARIABLES: 0.8,
            GenerationScenario.NEW_OUTPUTS: 0.8,
        }

        scenario_factor = scenario_multipliers.get(request.scenario, 1.0)

        # Add time if existing code needs to be processed
        existing_code_factor = 1.3 if request.existing_code else 1.0

        # Add time for context retrieval
        context_factor = 1 + (request.max_context_documents / 10)

        estimated = int(
            base_duration
            * query_length_factor
            * scenario_factor
            * existing_code_factor
            * context_factor
        )

        return min(estimated, 300)  # Cap at 5 minutes

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
        total_lines = sum(
            len(content.split("\n")) for content in result.generated_files.values()
        )

        file_types = set()
        for filename in result.generated_files.keys():
            if "." in filename:
                file_types.add(filename.split(".")[-1])

        summary_parts = [
            f"Generated {file_count} file{'s' if file_count != 1 else ''}",
            f"{total_lines} total lines of code",
        ]

        if file_types:
            summary_parts.append(f"File types: {', '.join(sorted(file_types))}")

        return "; ".join(summary_parts)
