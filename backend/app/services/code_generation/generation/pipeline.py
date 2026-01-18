"""
Autonomous Generation Pipeline for Terraform code generation.

This module provides a complete pipeline that orchestrates the end-to-end
process of generating Terraform code from user queries, including context
retrieval, prompt engineering, LLM generation, and validation.
"""

import asyncio
import time
import re
import os
from pathlib import Path
from typing import Dict, Any, Optional, List
from dataclasses import dataclass, field
from enum import Enum
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.code_generation.rag.retriever import RAGRetriever, RetrievalContext, RetrievalResult
from app.services.code_generation.generation.prompt_engineer import PromptEngineer, PromptContext, EngineeredPrompt, GenerationScenario
from app.services.code_generation.llm_providers.provider_factory import ProviderFactory
from app.services.code_generation.llm_providers.base import LLMRequest, LLMResponse
from app.services.code_generation.config.settings import get_code_generation_settings
from app.services.code_generation.config.rate_limiter import RateLimiter
from app.services.code_generation.generation.validator import TerraformValidator, MultiFileValidationResult
from app.services.code_generation.generation.error_corrector import TerraformErrorCorrector, MultiFileCorrectionResult
from logconfig.logger import get_logger

logger = get_logger()
settings = get_code_generation_settings()


class PipelineStage(Enum):
    """Stages of the generation pipeline."""
    INITIALIZED = "initialized"
    CONTEXT_RETRIEVAL = "context_retrieval"
    PROMPT_ENGINEERING = "prompt_engineering"
    CODE_GENERATION = "code_generation"
    VALIDATION = "validation"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass
class GenerationRequest:
    """Request for code generation."""
    query: str
    scenario: GenerationScenario = GenerationScenario.NEW_RESOURCE
    repository_name: Optional[str] = None
    existing_code: Optional[str] = None
    target_file_path: Optional[str] = None
    max_context_documents: int = 5
    similarity_threshold: float = 0.7
    provider_type: str = "claude"
    temperature: Optional[float] = None
    max_tokens: Optional[int] = None
    cloud_provider: str = "AWS"  # Cloud provider for infrastructure generation


@dataclass
class GenerationResult:
    """Result of the generation pipeline."""
    request: GenerationRequest
    generated_code: str = ""  # Keep for backward compatibility
    generated_files: Dict[str, str] = field(default_factory=dict)  # New: multiple files
    pipeline_metadata: Dict[str, Any] = field(default_factory=dict)
    stage_results: Dict[str, Any] = field(default_factory=dict)
    errors: List[str] = field(default_factory=list)
    success: bool = False
    total_time_ms: float = 0.0


@dataclass
class PipelineMetrics:
    """Metrics collected during pipeline execution."""
    context_retrieval_time: float = 0.0
    prompt_engineering_time: float = 0.0
    code_generation_time: float = 0.0
    validation_time: float = 0.0
    total_time: float = 0.0
    documents_retrieved: int = 0
    tokens_used: int = 0
    rate_limit_hits: int = 0


class AutonomousGenerationPipeline:
    """
    Complete autonomous generation pipeline for Terraform code.

    This class orchestrates the entire code generation process from user query
    to validated Terraform code, with proper error handling and monitoring.
    """

    def __init__(self, db_session: AsyncSession):
        """
        Initialize the generation pipeline.

        Args:
            db_session: Database session for vector store operations
        """
        self.db = db_session

        # Initialize components
        self.rag_retriever = RAGRetriever(db_session)
        self.prompt_engineer = PromptEngineer()
        self.provider_factory = ProviderFactory()

        # Initialize enhanced validation and correction components
        self.validator = TerraformValidator()
        self.error_corrector = TerraformErrorCorrector()

        # Initialize rate limiter
        self.rate_limiter = RateLimiter(
            redis_url=settings.REDIS_URL,
            requests=settings.RATE_LIMIT_REQUESTS,
            window=settings.RATE_LIMIT_WINDOW,
            key_prefix="code_generation"
        )

        # Real-time service for user interaction
        try:
            from app.services.realtime_service import realtime_service
            self.realtime_service = realtime_service
        except ImportError:
            self.realtime_service = None
            logger.warning("Real-time service not available for autonomous interactions")

        # Pipeline configuration
        self.max_pipeline_time = 300  # 5 minutes timeout
        self.enable_validation = True
        self.enable_autonomous_interaction = True  # Enable autonomous user interaction

        logger.info("AutonomousGenerationPipeline initialized")

    async def generate_code(self, request: GenerationRequest) -> GenerationResult:
        """
        Execute the complete generation pipeline.

        Args:
            request: Generation request with query and parameters

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
            await self._update_pipeline_stage(result, PipelineStage.CONTEXT_RETRIEVAL)
            retrieval_result = await self._retrieve_context(request, metrics)
            result.stage_results["context_retrieval"] = {
                "documents_found": len(retrieval_result.documents),
                "processing_time_ms": retrieval_result.processing_time_ms
            }

            # Stage 2: Prompt Engineering
            await self._update_pipeline_stage(result, PipelineStage.PROMPT_ENGINEERING)
            engineered_prompt = await self._engineer_prompt(request, retrieval_result, metrics)
            result.stage_results["prompt_engineering"] = {
                "prompt_length": len(engineered_prompt.user_message),
                "context_documents_used": request.max_context_documents
            }

            # Stage 3: Code Generation
            await self._update_pipeline_stage(result, PipelineStage.CODE_GENERATION)
            generated_files = await self._generate_terraform_project(request, engineered_prompt, metrics)
            result.generated_files = generated_files

            # For backward compatibility, set generated_code to the main file content
            if "main.tf" in generated_files:
                result.generated_code = generated_files["main.tf"]
            elif generated_files:
                result.generated_code = list(generated_files.values())[0]

            result.stage_results["code_generation"] = {
                "files_generated": len(generated_files),
                "total_code_length": sum(len(content) for content in generated_files.values()),
                "generation_time_ms": metrics.code_generation_time
            }

            # Stage 4: Validation and Error Correction (if enabled)
            if self.enable_validation:
                await self._update_pipeline_stage(result, PipelineStage.VALIDATION)

                # Enhanced validation with error detection
                validation_result = await self._validate_and_correct_generated_files(
                    generated_files, request.target_file_path, metrics
                )
                result.stage_results["validation"] = validation_result

            # Mark as completed
            await self._update_pipeline_stage(result, PipelineStage.COMPLETED)
            result.success = True

            # Save generated files if target_file_path is specified
            if request.target_file_path:
                # Use corrected files if available from validation stage
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
                "final_stage": PipelineStage.COMPLETED.value
            }

            logger.info(
                f"Pipeline completed successfully for query '{request.query[:50]}...' "
                f"generated {len(generated_files)} files in {result.total_time_ms:.2f}ms"
            )

        except Exception as e:
            logger.error(f"Pipeline failed: {e}")
            result.errors.append(str(e))
            result.success = False
            result.total_time_ms = (time.time() - start_time) * 1000
            await self._update_pipeline_stage(result, PipelineStage.FAILED)

            # Rollback session on error to ensure clean state
            try:
                await self.db.rollback()
            except Exception as rollback_error:
                logger.warning(f"Failed to rollback session: {rollback_error}")

        return result

    async def _retrieve_context(
        self,
        request: GenerationRequest,
        metrics: PipelineMetrics
    ) -> RetrievalResult:
        """
        Retrieve relevant context for the generation request.

        Args:
            request: Generation request
            metrics: Pipeline metrics to update

        Returns:
            RetrievalResult with context documents
        """
        retrieval_context = RetrievalContext(
            query=request.query,
            repository_name=request.repository_name,
            max_results=request.max_context_documents,
            similarity_threshold=request.similarity_threshold
        )

        retrieval_result = await self.rag_retriever.retrieve_context(retrieval_context)

        # Update metrics
        metrics.context_retrieval_time = retrieval_result.processing_time_ms
        metrics.documents_retrieved = len(retrieval_result.documents)

        return retrieval_result

    async def _engineer_prompt(
        self,
        request: GenerationRequest,
        retrieval_result: RetrievalResult,
        metrics: PipelineMetrics
    ) -> EngineeredPrompt:
        """
        Engineer a prompt based on the request and retrieved context.

        Args:
            request: Generation request
            retrieval_result: Retrieved context
            metrics: Pipeline metrics to update

        Returns:
            EngineeredPrompt for code generation
        """
        start_time = time.time()

        prompt_context = PromptContext(
            user_query=request.query,
            retrieved_documents=retrieval_result.documents,
            scenario=request.scenario,
            existing_code=request.existing_code,
            target_file_path=request.target_file_path,
            cloud_provider=request.cloud_provider
        )

        engineered_prompt = await self.prompt_engineer.engineer_prompt(prompt_context)

        # Update metrics
        metrics.prompt_engineering_time = (time.time() - start_time) * 1000

        return engineered_prompt

    async def _generate_terraform_project(
        self,
        request: GenerationRequest,
        engineered_prompt: EngineeredPrompt,
        metrics: PipelineMetrics
    ) -> Dict[str, str]:
        """
        Generate a complete Terraform project with multiple files.

        Args:
            request: Generation request
            engineered_prompt: Engineered prompt
            metrics: Pipeline metrics to update

        Returns:
            Dictionary of filename to content for the Terraform project
        """
        start_time = time.time()

        try:
            # Check rate limits
            if not await self.rate_limiter.is_allowed("code_generation"):
                metrics.rate_limit_hits += 1
                raise Exception("Rate limit exceeded for code generation")

            # Determine required files based on scenario and query
            required_files = self._determine_required_files(request)

            # Create enhanced prompt for multi-file generation
            multi_file_prompt = self._create_multi_file_prompt(engineered_prompt, required_files)

            # Create LLM provider
            llm_config = settings.get_llm_config_dict()
            if request.temperature is not None:
                llm_config["temperature"] = request.temperature
            if request.max_tokens is not None:
                llm_config["max_tokens"] = request.max_tokens

            provider = self.provider_factory.create_from_config(llm_config)

            # Create LLM request
            llm_request = LLMRequest(
                prompt=multi_file_prompt.user_message,
                system_message=multi_file_prompt.system_message,
                config=provider.config
            )

            # Generate code
            response: LLMResponse = await provider.generate(llm_request)

            # Clean the LLM response to remove markdown and explanatory text
            response.content = self._clean_llm_response(response.content)

            # Check if autonomous interaction is enabled and LLM needs clarification
            if self.enable_autonomous_interaction and self.realtime_service:
                clarification_needed, question = self._detect_clarification_needed(response.content)
                if clarification_needed:
                    # Extract context for clarification
                    generation_id = request.__dict__.get("generation_id", str(uuid.uuid4()))
                    user_id = getattr(request, 'user_id', None)
                    project_id = getattr(request, 'project_id', None)

                    if user_id and project_id:
                        logger.info(f"LLM requested clarification for generation {generation_id}: {question}")

                        # Request clarification from user
                        await self.realtime_service.emit_user_clarification_request(
                            generation_id=generation_id,
                            project_id=project_id,
                            user_id=user_id,
                            question=question,
                            context={"original_query": request.query, "llm_response": response.content[:500]},
                            timeout_seconds=300,  # 5 minutes
                        )

                        # Wait for user response
                        user_response = await self.realtime_service.get_clarification_response(
                            generation_id, timeout_seconds=300
                        )

                        if user_response:
                            logger.info(f"Received clarification response for generation {generation_id}: {user_response[:100]}...")

                            # Continue generation with clarification
                            clarified_response = await self._continue_generation_with_clarification(
                                provider, request, response, user_response, required_files, metrics
                            )
                            response = clarified_response
                        else:
                            logger.warning(f"No clarification response received for generation {generation_id}, proceeding with original response")

            # Update metrics
            metrics.code_generation_time = (time.time() - start_time) * 1000
            metrics.tokens_used = response.usage.get("input_tokens", 0) + response.usage.get("output_tokens", 0)

            # Parse multi-file response
            generated_files = self._parse_multi_file_response(response.content, required_files)

            logger.info(
                f"Generated {len(generated_files)} files using {request.provider_type} provider, "
                f"tokens used: {metrics.tokens_used}"
            )

            return generated_files

        except Exception as e:
            metrics.code_generation_time = (time.time() - start_time) * 1000
            logger.error(f"Multi-file generation failed: {e}")
            raise

    def _determine_required_files(self, request: GenerationRequest) -> List[str]:
        """
        Determine which files are required based on the request scenario and query.

        Args:
            request: Generation request

        Returns:
            List of required filenames
        """
        base_files = ["main.tf"]

        # Add files based on scenario
        if request.scenario in [GenerationScenario.NEW_RESOURCE, GenerationScenario.NEW_MODULE]:
            base_files.extend(["variables.tf", "outputs.tf"])

        if request.scenario == GenerationScenario.NEW_VARIABLES:
            if "variables.tf" not in base_files:
                base_files.append("variables.tf")

        if request.scenario == GenerationScenario.NEW_OUTPUTS:
            if "outputs.tf" not in base_files:
                base_files.append("outputs.tf")

        # Check query for specific file mentions
        query_lower = request.query.lower()
        if "variable" in query_lower and "variables.tf" not in base_files:
            base_files.append("variables.tf")
        if "output" in query_lower and "outputs.tf" not in base_files:
            base_files.append("outputs.tf")
        if "terraform.tfvars" in query_lower or "tfvars" in query_lower:
            base_files.append("terraform.tfvars")
        if "provider" in query_lower and "providers.tf" not in base_files:
            base_files.append("providers.tf")

        return base_files

    def _create_multi_file_prompt(
        self,
        original_prompt: EngineeredPrompt,
        required_files: List[str]
    ) -> EngineeredPrompt:
        """
        Create an enhanced prompt for multi-file generation.

        Args:
            original_prompt: Original engineered prompt
            required_files: List of files to generate

        Returns:
            Enhanced prompt for multi-file generation
        """
        files_instruction = f"""
Generate a complete Terraform project with the following files: {', '.join(required_files)}

For each file, provide the complete content with proper Terraform syntax.

Format your response as:
## main.tf
[content of main.tf]

## variables.tf
[content of variables.tf]

## outputs.tf
[content of outputs.tf]

## [other files as needed]

Ensure each file contains only the appropriate Terraform constructs:
- main.tf: Resources, data sources, locals, modules
- variables.tf: Variable declarations
- outputs.tf: Output declarations
- providers.tf: Provider configurations
- terraform.tfvars: Variable values

{original_prompt.user_message}
"""

        return EngineeredPrompt(
            user_message=files_instruction,
            system_message=original_prompt.system_message
        )

    def _parse_multi_file_response(self, response_content: str, expected_files: List[str]) -> Dict[str, str]:
        """
        Parse the LLM response to extract multiple files with robust fallback mechanisms.

        Args:
            response_content: Raw LLM response
            expected_files: List of expected filenames

        Returns:
            Dictionary of filename to content
        """
        files = {}

        # Method 1: Try standard header-based parsing
        files = self._parse_with_headers(response_content, expected_files)

        # Method 2: If header parsing failed, try alternative patterns
        if not files or len(files) < len(expected_files):
            logger.debug("Header parsing incomplete, trying alternative patterns")
            alt_files = self._parse_with_alternative_patterns(response_content, expected_files)
            if alt_files and len(alt_files) > len(files):
                files = alt_files

        # Method 3: If still no files, try code block extraction
        if not files:
            logger.debug("No files parsed, trying code block extraction")
            files = self._parse_with_code_blocks(response_content, expected_files)

        # Method 4: Final fallback - single file
        if not files:
            logger.debug("All parsing methods failed, using single file fallback")
            files = self._parse_as_single_file(response_content, expected_files)

        # Ensure all expected files are present (even if empty)
        for expected_file in expected_files:
            if expected_file not in files:
                files[expected_file] = ""

        logger.debug(f"Parsed {len(files)} files from response: {list(files.keys())}")
        return files

    def _parse_with_headers(self, response_content: str, expected_files: List[str]) -> Dict[str, str]:
        """Parse using standard header patterns."""
        files = {}

        # Try multiple header patterns for robustness
        header_patterns = [
            r'^##\s+(.+\.tf(?:vars)?)$',  # ## main.tf
            r'^###\s+(.+\.tf(?:vars)?)$',  # ### main.tf
            r'^\*\*\s+(.+\.tf(?:vars)?)\s+\*\*$',  # **main.tf**
            r'^File:\s*(.+\.tf(?:vars)?)$',  # File: main.tf
            r'^(.+\.tf(?:vars)?):$',  # main.tf:
        ]

        for pattern in header_patterns:
            file_sections = re.split(pattern, response_content, flags=re.MULTILINE | re.IGNORECASE)
            if len(file_sections) > 1:
                break

        current_file = None
        current_content = []

        for section in file_sections:
            section = section.strip()
            if not section:
                continue

            # Check if this is a filename (case-insensitive matching)
            section_lower = section.lower()
            matched_file = None

            for expected_file in expected_files:
                if expected_file.lower() == section_lower or expected_file.lower().replace('.tf', '') == section_lower.replace('.tf', ''):
                    matched_file = expected_file
                    break

            if matched_file:
                if current_file and current_content:
                    files[current_file] = '\n'.join(current_content).strip()
                current_file = matched_file
                current_content = []
            else:
                if current_file:
                    current_content.append(section)

        # Add the last file
        if current_file and current_content:
            files[current_file] = '\n'.join(current_content).strip()

        return files

    def _parse_with_alternative_patterns(self, response_content: str, expected_files: List[str]) -> Dict[str, str]:
        """Parse using alternative patterns when header parsing fails."""
        files = {}

        # Look for file content patterns
        lines = response_content.split('\n')
        current_file = None
        current_content = []

        for line in lines:
            line = line.strip()

            # Check for file indicators
            for expected_file in expected_files:
                file_indicators = [
                    f"## {expected_file}",
                    f"### {expected_file}",
                    f"**{expected_file}**",
                    f"File: {expected_file}",
                    f"{expected_file}:",
                    expected_file
                ]

                if any(indicator.lower() in line.lower() for indicator in file_indicators):
                    if current_file and current_content:
                        files[current_file] = '\n'.join(current_content).strip()
                    current_file = expected_file
                    current_content = []
                    break
            else:
                if current_file and line:
                    current_content.append(line)

        # Add the last file
        if current_file and current_content:
            files[current_file] = '\n'.join(current_content).strip()

        return files

    def _parse_with_code_blocks(self, response_content: str, expected_files: List[str]) -> Dict[str, str]:
        """Parse by extracting code blocks and assigning to files."""
        files = {}

        # Extract all code blocks
        code_block_pattern = r'```(?:hcl|terraform|tf)?\n?(.*?)\n?```'
        code_blocks = re.findall(code_block_pattern, response_content, re.DOTALL | re.IGNORECASE)

        if code_blocks:
            # Assign code blocks to expected files in order
            for i, code_block in enumerate(code_blocks):
                if i < len(expected_files):
                    files[expected_files[i]] = code_block.strip()

        return files

    def _parse_as_single_file(self, response_content: str, expected_files: List[str]) -> Dict[str, str]:
        """Fallback: treat entire response as a single file."""
        files = {}

        # Clean the response and put it in the first expected file
        cleaned_content = response_content.strip()
        if expected_files:
            files[expected_files[0]] = cleaned_content
        else:
            files["main.tf"] = cleaned_content

        return files

    async def _generate_code(
        self,
        request: GenerationRequest,
        engineered_prompt: EngineeredPrompt,
        metrics: PipelineMetrics
    ) -> str:
        """
        Generate code using the LLM provider (legacy single-file method).

        Args:
            request: Generation request
            engineered_prompt: Engineered prompt
            metrics: Pipeline metrics to update

        Returns:
            Generated Terraform code
        """
        # For backward compatibility, generate single file
        files = await self._generate_terraform_project(request, engineered_prompt, metrics)
        return files.get("main.tf", "") if files else ""

    async def _validate_and_correct_generated_files(
        self,
        generated_files: Dict[str, str],
        target_directory: Optional[str],
        metrics: PipelineMetrics
    ) -> Dict[str, Any]:
        """
        Validate and automatically correct the generated Terraform files using enhanced system.

        Args:
            generated_files: Dictionary of filename to content
            target_directory: Directory where files will be saved (for correction context)
            metrics: Pipeline metrics to update

        Returns:
            Enhanced validation and correction results
        """
        start_time = time.time()

        result = {
            "is_valid": True,
            "files_validated": len(generated_files),
            "files_corrected": 0,
            "validation_result": None,
            "correction_result": None,
            "final_files": generated_files.copy(),
            "total_errors_before": 0,
            "total_errors_after": 0,
            "correction_successful": False,
            "autonomous_correction_performed": False
        }

        try:
            # Create temporary files for validation if target directory is provided
            temp_files_created = []
            validation_file_paths = []

            if target_directory:
                # Save files temporarily for validation
                temp_dir = Path(target_directory)
                temp_dir.mkdir(parents=True, exist_ok=True)

                for filename, content in generated_files.items():
                    if content.strip():  # Only save non-empty files
                        file_path = temp_dir / filename
                        with open(file_path, 'w', encoding='utf-8') as f:
                            f.write(content)
                        temp_files_created.append(file_path)
                        validation_file_paths.append(str(file_path))

            # If no target directory, validate in-memory content
            if not validation_file_paths:
                # Create temporary validation for in-memory files
                import tempfile
                with tempfile.TemporaryDirectory() as temp_dir:
                    for filename, content in generated_files.items():
                        if content.strip():
                            file_path = Path(temp_dir) / filename
                            with open(file_path, 'w', encoding='utf-8') as f:
                                f.write(content)
                            validation_file_paths.append(str(file_path))

                    # Perform enhanced validation
                    validation_result = await self.validator.validate_files(validation_file_paths)
            else:
                # Validate existing files
                validation_result = await self.validator.validate_files(validation_file_paths)

            result["validation_result"] = validation_result.__dict__
            result["total_errors_before"] = validation_result.total_errors

            # Check if correction is needed
            if validation_result.total_errors > 0:
                logger.info(f"Found {validation_result.total_errors} errors, attempting autonomous correction")

                # Perform autonomous correction
                correction_cycles = await self.error_corrector.autonomous_correction_cycle(
                    directory_path=target_directory or str(Path(tempfile.gettempdir()) / "terraform_validation"),
                    max_cycles=3,
                    max_iterations_per_file=3,
                    use_llm=True,
                    create_backups=False  # Disabled by default to avoid creating backup files
                )

                result["autonomous_correction_performed"] = True
                result["correction_cycles"] = len(correction_cycles)

                if correction_cycles:
                    final_cycle = correction_cycles[-1]
                    result["correction_result"] = self.error_corrector.generate_correction_report(final_cycle)
                    result["files_corrected"] = final_cycle.files_corrected

                    # Re-validate after correction
                    if target_directory:
                        final_validation = await self.validator.scan_and_validate_directory(target_directory)
                        result["total_errors_after"] = final_validation.total_errors
                        result["correction_successful"] = final_validation.total_errors == 0

                        # Update final files with corrected content
                        for filename in generated_files.keys():
                            file_path = Path(target_directory) / filename
                            if file_path.exists():
                                with open(file_path, 'r', encoding='utf-8') as f:
                                    result["final_files"][filename] = f.read()

            else:
                result["correction_successful"] = True
                result["total_errors_after"] = 0

            result["is_valid"] = result["total_errors_after"] == 0

        except Exception as e:
            logger.error(f"Enhanced validation and correction failed: {e}")
            result["error"] = str(e)
            result["is_valid"] = False

        # Update metrics
        metrics.validation_time = (time.time() - start_time) * 1000

        return result

    async def _validate_generated_code(
        self,
        generated_code: str,
        metrics: PipelineMetrics
    ) -> Dict[str, Any]:
        """
        Validate the generated Terraform code (legacy single-file method).

        Args:
            generated_code: Generated code to validate
            metrics: Pipeline metrics to update

        Returns:
            Validation results
        """
        # For backward compatibility
        files = {"main.tf": generated_code}
        return await self._validate_generated_files(files, metrics)

    async def _save_generated_files_to_directory(
        self,
        generated_files: Dict[str, str],
        target_directory: str,
        result: GenerationResult
    ) -> Dict[str, Any]:
        """
        Save generated files to the specified directory.

        Args:
            generated_files: Dictionary of filename to content
            target_directory: Directory where to save the files
            result: GenerationResult to update with feedback

        Returns:
            Dictionary with save operation results
        """
        save_result = {
            "files_saved": 0,
            "total_files": len(generated_files),
            "target_directory": target_directory,
            "bytes_written": 0,
            "errors": [],
            "file_results": {}
        }

        try:
            # Convert to Path object for better handling
            dir_path = Path(target_directory)

            # Create directory if it doesn't exist
            dir_path.mkdir(parents=True, exist_ok=True)

            # Analyze existing files in the directory
            existing_files = await self._analyze_target_directory(dir_path)

            for filename, content in generated_files.items():
                file_result = {
                    "saved": False,
                    "file_path": str(dir_path / filename),
                    "bytes_written": 0,
                    "action": "created",
                    "error": None
                }

                try:
                    file_path = dir_path / filename

                    # Check if file exists and handle dependencies
                    if file_path.exists():
                        file_result["action"] = "updated"
                        # Read existing content for merging if needed
                        existing_content = file_path.read_text(encoding='utf-8')
                        if existing_content.strip():
                            # Merge with existing content
                            content = self._merge_file_content(filename, existing_content, content)

                    # Write the file
                    with open(file_path, 'w', encoding='utf-8') as f:
                        f.write(content)

                    file_result["saved"] = True
                    file_result["bytes_written"] = len(content.encode('utf-8'))
                    save_result["files_saved"] += 1
                    save_result["bytes_written"] += file_result["bytes_written"]

                    logger.info(f"File {filename} {file_result['action']} at {file_path}")

                except Exception as e:
                    error_msg = f"Failed to save {filename}: {str(e)}"
                    logger.error(error_msg)
                    file_result["error"] = error_msg
                    save_result["errors"].append(error_msg)
                    result.errors.append(error_msg)

                save_result["file_results"][filename] = file_result

            logger.info(f"Saved {save_result['files_saved']}/{save_result['total_files']} files to {target_directory}")

        except Exception as e:
            error_msg = f"Failed to save files to directory {target_directory}: {str(e)}"
            logger.error(error_msg)
            save_result["errors"].append(error_msg)
            result.errors.append(error_msg)

        return save_result

    async def _analyze_target_directory(self, dir_path: Path) -> Dict[str, Any]:
        """
        Analyze the target directory for existing files and structure.

        Args:
            dir_path: Path to the directory to analyze

        Returns:
            Analysis results
        """
        analysis = {
            "exists": dir_path.exists(),
            "existing_files": [],
            "terraform_files": [],
            "has_git": (dir_path / ".git").exists(),
            "has_terraform": False
        }

        if dir_path.exists():
            for file_path in dir_path.iterdir():
                if file_path.is_file():
                    analysis["existing_files"].append(file_path.name)
                    if file_path.suffix in ['.tf', '.tfvars']:
                        analysis["terraform_files"].append(file_path.name)
                        analysis["has_terraform"] = True

        return analysis

    def _merge_file_content(self, filename: str, existing_content: str, new_content: str) -> str:
        """
        Merge new content with existing file content based on file type.

        Args:
            filename: Name of the file
            existing_content: Existing file content
            new_content: New content to merge

        Returns:
            Merged content
        """
        if filename == "variables.tf":
            # For variables.tf, append new variables if they don't exist
            return self._merge_variables(existing_content, new_content)
        elif filename == "outputs.tf":
            # For outputs.tf, append new outputs if they don't exist
            return self._merge_outputs(existing_content, new_content)
        elif filename == "main.tf":
            # For main.tf, append new resources
            return self._merge_resources(existing_content, new_content)
        else:
            # For other files, replace entirely
            return new_content

    def _merge_variables(self, existing: str, new: str) -> str:
        """Merge variable declarations."""
        # Simple append for now - could be enhanced with deduplication
        if existing.strip() and new.strip():
            return existing.rstrip() + "\n\n" + new.lstrip()
        return existing or new

    def _merge_outputs(self, existing: str, new: str) -> str:
        """Merge output declarations."""
        # Simple append for now
        if existing.strip() and new.strip():
            return existing.rstrip() + "\n\n" + new.lstrip()
        return existing or new

    def _merge_resources(self, existing: str, new: str) -> str:
        """Merge resource declarations."""
        # Simple append for now
        if existing.strip() and new.strip():
            return existing.rstrip() + "\n\n" + new.lstrip()
        return existing or new

    async def _save_generated_code_to_file(
        self,
        generated_code: str,
        target_file_path: str,
        result: GenerationResult
    ) -> Dict[str, Any]:
        """
        Save generated code to the specified file path (legacy single-file method).

        Args:
            generated_code: The code to save
            target_file_path: Path where to save the file
            result: GenerationResult to update with feedback

        Returns:
            Dictionary with save operation results
        """
        # For backward compatibility
        files = {"main.tf": generated_code}
        return await self._save_generated_files_to_directory(files, str(Path(target_file_path).parent), result)

    def _clean_llm_response(self, response_content: str) -> str:
        """
        Clean LLM response by stripping markdown code blocks, headers, and explanatory text.

        Args:
            response_content: Raw LLM response

        Returns:
            Cleaned response with pure HCL code
        """
        import re

        # Remove markdown code block markers
        # Pattern matches ```hcl, ```terraform, or just ```
        code_block_pattern = r'```\w*\n?'
        response_content = re.sub(code_block_pattern, '', response_content)

        # PRESERVE file headers like ## main.tf, ## variables.tf, etc.
        # Only remove other types of headers that are not file names
        # Remove headers that are NOT file headers (don't match .tf or .tfvars pattern)
        header_pattern = r'^##\s+(?!.*\.(tf|tfvars)$).*?$'
        response_content = re.sub(header_pattern, '', response_content, flags=re.MULTILINE)

        # Remove common explanatory text patterns
        explanatory_patterns = [
            r'Here is the.*?:',
            r'Below is.*?:',
            r'The following.*?:',
            r'Generated.*?:',
            r'Please find.*?:',
            r'This will create.*?',
            r'To use this.*?',
            r'Note:.*?',
            r'Important:.*?',
            r'Warning:.*?',
        ]

        for pattern in explanatory_patterns:
            response_content = re.sub(pattern, '', response_content, flags=re.IGNORECASE | re.MULTILINE)

        # Clean up extra whitespace and empty lines
        # Remove multiple consecutive empty lines
        response_content = re.sub(r'\n\s*\n\s*\n+', '\n\n', response_content)

        # Remove leading/trailing whitespace from each line
        lines = [line.strip() for line in response_content.split('\n')]
        response_content = '\n'.join(lines)

        # Remove leading/trailing whitespace
        response_content = response_content.strip()

        return response_content

    def _extract_code_from_response(self, response_content: str) -> str:
        """
        Extract Terraform code from LLM response.

        Args:
            response_content: Raw LLM response

        Returns:
            Extracted Terraform code
        """
        # Look for code blocks in the response
        import re

        # Find HCL/Terraform code blocks
        code_block_pattern = r'```(?:hcl|terraform)?\n?(.*?)\n?```'
        matches = re.findall(code_block_pattern, response_content, re.DOTALL)

        if matches:
            # Return the first code block
            return matches[0].strip()

        # If no code blocks found, return the entire response
        return response_content.strip()

    def _validate_terraform_syntax(self, code: str) -> bool:
        """
        Perform basic Terraform syntax validation.

        Args:
            code: Terraform code to validate

        Returns:
            True if syntax appears valid
        """
        # Basic checks for common syntax issues
        checks = [
            # Check for balanced braces
            code.count('{') == code.count('}'),
            # Check for balanced brackets
            code.count('[') == code.count(']'),
            # Check for balanced parentheses
            code.count('(') == code.count(')'),
            # Check for required quotes around strings
            not re.search(r'=\s*[a-zA-Z_][a-zA-Z0-9_]*\s*[^"\s]', code),  # Unquoted strings
        ]

        return all(checks)

    def _validate_terraform_structure(self, code: str) -> bool:
        """
        Perform basic Terraform structure validation.

        Args:
            code: Terraform code to validate

        Returns:
            True if structure appears valid
        """
        # Check for basic Terraform structure elements
        has_resource = 'resource' in code
        has_provider = 'provider' in code or 'terraform' in code

        # For resource creation, we expect at least a resource block
        if 'resource "' in code:
            return has_resource
        elif 'module "' in code:
            return 'module' in code
        elif 'variable "' in code:
            return 'variable' in code
        elif 'output "' in code:
            return 'output' in code

        # If it's a general code block, basic syntax check is sufficient
        return True

    async def _update_pipeline_stage(self, result: GenerationResult, stage: PipelineStage):
        """
        Update the current pipeline stage in the result.

        Args:
            result: Generation result to update
            stage: New pipeline stage
        """
        result.pipeline_metadata["current_stage"] = stage.value
        logger.debug(f"Pipeline stage updated to: {stage.value}")

    async def get_pipeline_health(self) -> Dict[str, Any]:
        """
        Get health status of the generation pipeline.

        Returns:
            Health status dictionary
        """
        try:
            # Check component health
            retriever_stats = await self.rag_retriever.get_retrieval_stats()

            # Check rate limiter status
            remaining_requests = await self.rate_limiter.get_remaining_requests("health_check")

            return {
                "status": "healthy",
                "components": {
                    "rag_retriever": "operational",
                    "prompt_engineer": "operational",
                    "llm_provider": "operational",
                    "rate_limiter": "operational"
                },
                "retriever_stats": retriever_stats,
                "rate_limiter": {
                    "remaining_requests": remaining_requests,
                    "window_seconds": settings.RATE_LIMIT_WINDOW
                },
                "configuration": {
                    "max_pipeline_time": self.max_pipeline_time,
                    "enable_validation": self.enable_validation
                }
            }

        except Exception as e:
            logger.error(f"Health check failed: {e}")
            return {
                "status": "unhealthy",
                "error": str(e)
            }

    async def generate_with_fallback(
        self,
        request: GenerationRequest,
        fallback_providers: Optional[List[str]] = None
    ) -> GenerationResult:
        """
        Generate code with fallback to alternative providers if primary fails.

        Args:
            request: Generation request
            fallback_providers: List of fallback provider types

        Returns:
            GenerationResult from successful generation or last failure
        """
        if fallback_providers is None:
            fallback_providers = ["claude"]  # Default fallback

        last_result = None

        for provider in [request.provider_type] + fallback_providers:
            try:
                request.provider_type = provider
                result = await self.generate_code(request)

                if result.success:
                    return result

                last_result = result

            except Exception as e:
                logger.warning(f"Generation failed with provider {provider}: {e}")
                if last_result is None:
                    last_result = GenerationResult(request=request, errors=[str(e)])

        # Return the last failed result if all providers failed
        return last_result

    def _detect_clarification_needed(self, llm_response: str) -> tuple[bool, str]:
        """
        Detect if the LLM response indicates that clarification is needed from the user.

        Args:
            llm_response: The raw LLM response content

        Returns:
            Tuple of (needs_clarification, question_to_ask)
        """
        response_lower = llm_response.lower()

        # Common patterns that indicate clarification is needed
        clarification_indicators = [
            "could you please clarify",
            "can you specify",
            "i need more information",
            "please provide",
            "what do you mean by",
            "could you elaborate",
            "can you tell me more about",
            "i need clarification on",
            "please specify",
            "what is the",
            "how would you like",
            "do you want",
            "should i",
            "would you prefer",
        ]

        for indicator in clarification_indicators:
            if indicator in response_lower:
                # Extract the question or clarification request
                lines = llm_response.split('\n')
                for line in lines:
                    line_lower = line.lower()
                    if any(indicator in line_lower for indicator in clarification_indicators):
                        # Clean up the question
                        question = line.strip()
                        # Remove common prefixes
                        question = re.sub(r'^(i need|could you|can you|please)\s+', '', question, flags=re.IGNORECASE)
                        question = question.strip()
                        if question:
                            return True, question

        return False, ""

    async def _continue_generation_with_clarification(
        self,
        provider: Any,
        original_request: GenerationRequest,
        original_response: LLMResponse,
        user_clarification: str,
        required_files: List[str],
        metrics: PipelineMetrics
    ) -> LLMResponse:
        """
        Continue code generation with user clarification.

        Args:
            provider: LLM provider instance
            original_request: Original generation request
            original_response: Original LLM response
            user_clarification: User's clarification response
            required_files: Required files for generation
            metrics: Pipeline metrics

        Returns:
            Updated LLM response with clarification incorporated
        """
        try:
            # Create a follow-up prompt that includes the clarification
            clarification_prompt = f"""
    Based on the user's clarification: "{user_clarification}"

    Please continue generating the Terraform code with this additional information.
    Original request: {original_request.query}

    Previous response context: {original_response.content[:1000]}...

    Generate the complete Terraform project with the following files: {', '.join(required_files)}

    Format your response as:
    ## main.tf
    [content of main.tf]

    ## variables.tf
    [content of variables.tf]

    ## outputs.tf
    [content of outputs.tf]

    ## [other files as needed]
    """

            # Create LLM request with clarification
            llm_config = settings.get_llm_config_dict()
            if original_request.temperature is not None:
                llm_config["temperature"] = original_request.temperature
            if original_request.max_tokens is not None:
                llm_config["max_tokens"] = original_request.max_tokens

            clarified_llm_request = LLMRequest(
                prompt=clarification_prompt,
                system_message="You are an expert Terraform developer. Generate complete, accurate Terraform code based on the user's requirements and clarification.",
                config=provider.config
            )

            # Generate with clarification
            clarified_response = await provider.generate(clarified_llm_request)

            # Update metrics
            metrics.tokens_used += clarified_response.usage.get("input_tokens", 0) + clarified_response.usage.get("output_tokens", 0)

            # Clean the response
            clarified_response.content = self._clean_llm_response(clarified_response.content)

            logger.info("Successfully continued generation with user clarification")
            return clarified_response

        except Exception as e:
            logger.error(f"Failed to continue generation with clarification: {e}")
            # Return original response if clarification fails
            return original_response

    async def correct_existing_terraform_files(
        self,
        directory_path: str,
        max_cycles: int = 3,
        create_backups: bool = True
    ) -> Dict[str, Any]:
        """
        Correct errors in existing Terraform files in a directory.

        Args:
            directory_path: Path to directory containing Terraform files
            max_cycles: Maximum autonomous correction cycles
            create_backups: Whether to create backup files

        Returns:
            Correction results and reports
        """
        start_time = time.time()

        result = {
            "directory_path": directory_path,
            "correction_performed": False,
            "validation_report": None,
            "correction_report": None,
            "final_validation_report": None,
            "processing_time_ms": 0,
            "success": False
        }

        try:
            # First, validate the directory
            logger.info(f"Validating Terraform files in {directory_path}")
            initial_validation = await self.validator.scan_and_validate_directory(directory_path)
            result["validation_report"] = self.validator.generate_validation_report(initial_validation)

            if initial_validation.total_errors == 0:
                logger.info("No errors found in Terraform files")
                result["success"] = True
                result["processing_time_ms"] = (time.time() - start_time) * 1000
                return result
        

            # Perform autonomous correction
            logger.info(f"Starting autonomous correction for {initial_validation.total_errors} errors")
            correction_cycles = await self.error_corrector.autonomous_correction_cycle(
                directory_path=directory_path,
                max_cycles=max_cycles,
                max_iterations_per_file=3,
                use_llm=True,
                create_backups=create_backups
            )

            result["correction_performed"] = True

            if correction_cycles:
                final_cycle = correction_cycles[-1]
                result["correction_report"] = self.error_corrector.generate_correction_report(final_cycle)

                # Final validation
                final_validation = await self.validator.scan_and_validate_directory(directory_path)
                result["final_validation_report"] = self.validator.generate_validation_report(final_validation)

                result["success"] = final_validation.total_errors == 0
                logger.info(f"Correction completed. Errors before: {initial_validation.total_errors}, after: {final_validation.total_errors}")
            else:
                result["success"] = False
                logger.warning("No correction cycles were performed")

        except Exception as e:
            logger.error(f"Error correction failed: {e}")
            result["error"] = str(e)
            result["success"] = False

        result["processing_time_ms"] = (time.time() - start_time) * 1000
        return result