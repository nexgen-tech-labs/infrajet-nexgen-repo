"""
Debug Information Collector for Terraform Code Generation.

This module collects comprehensive debugging information during the code generation
process, including error contexts, performance metrics, and generation metadata.
"""

import asyncio
import time
import json
from typing import Dict, List, Any, Optional, Union
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
import uuid

from logconfig.logger import get_logger
from .validator import ValidationIssue, ValidationResult
from .error_corrector import CorrectionAttempt, CorrectionResult

logger = get_logger()


@dataclass
class ErrorContext:
    """Context information for an error or issue."""
    line_number: Optional[int] = None
    column_number: Optional[int] = None
    surrounding_lines: List[str] = field(default_factory=list)
    error_message: str = ""
    stack_trace: Optional[str] = None
    context_window: int = 3  # Lines before and after the error


@dataclass
class GenerationMetadata:
    """Metadata about the code generation process."""
    generation_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    timestamp: datetime = field(default_factory=datetime.now)
    user_query: str = ""
    scenario: str = ""
    provider_type: str = ""
    model_used: str = ""
    temperature: Optional[float] = None
    max_tokens: Optional[int] = None
    prompts_used: List[Dict[str, Any]] = field(default_factory=list)
    context_documents: List[Dict[str, Any]] = field(default_factory=list)
    llm_responses: List[Dict[str, Any]] = field(default_factory=list)


@dataclass
class PerformanceMetrics:
    """Performance metrics for the generation process."""
    total_generation_time_ms: float = 0.0
    context_retrieval_time_ms: float = 0.0
    prompt_engineering_time_ms: float = 0.0
    llm_generation_time_ms: float = 0.0
    validation_time_ms: float = 0.0
    correction_time_ms: float = 0.0
    tokens_used: int = 0
    input_tokens: int = 0
    output_tokens: int = 0
    rate_limit_hits: int = 0
    retries_attempted: int = 0


@dataclass
class DebugSession:
    """A complete debugging session with all collected information."""
    session_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    start_time: datetime = field(default_factory=datetime.now)
    end_time: Optional[datetime] = None
    generation_metadata: GenerationMetadata = field(default_factory=GenerationMetadata)
    performance_metrics: PerformanceMetrics = field(default_factory=PerformanceMetrics)
    validation_results: List[ValidationResult] = field(default_factory=list)
    correction_results: List[CorrectionResult] = field(default_factory=list)
    error_contexts: List[ErrorContext] = field(default_factory=list)
    custom_logs: List[Dict[str, Any]] = field(default_factory=list)
    success: bool = False
    final_code: Optional[str] = None

    @property
    def duration_ms(self) -> float:
        """Calculate session duration in milliseconds."""
        if self.end_time:
            return (self.end_time - self.start_time).total_seconds() * 1000
        return (datetime.now() - self.start_time).total_seconds() * 1000


class DebugCollector:
    """
    Collector for comprehensive debugging information during Terraform code generation.

    This collector gathers error contexts, performance metrics, generation metadata,
    and other debugging information to help troubleshoot and improve the generation process.
    """

    def __init__(self, enable_persistence: bool = True, debug_dir: Optional[str] = None):
        """
        Initialize the debug collector.

        Args:
            enable_persistence: Whether to save debug sessions to disk
            debug_dir: Directory to save debug sessions (defaults to logs/debug_sessions)
        """
        self.enable_persistence = enable_persistence
        self.debug_dir = Path(debug_dir) if debug_dir else Path("logs/debug_sessions")
        self.current_session: Optional[DebugSession] = None
        self.session_history: List[DebugSession] = []

        if self.enable_persistence:
            self.debug_dir.mkdir(parents=True, exist_ok=True)

        logger.info("DebugCollector initialized")

    async def start_session(
        self,
        user_query: str,
        scenario: str = "",
        provider_type: str = "",
        **kwargs
    ) -> str:
        """
        Start a new debug session.

        Args:
            user_query: The user's generation query
            scenario: Generation scenario
            provider_type: LLM provider type
            **kwargs: Additional metadata

        Returns:
            Session ID for the new session
        """
        self.current_session = DebugSession()
        self.current_session.generation_metadata.user_query = user_query
        self.current_session.generation_metadata.scenario = scenario
        self.current_session.generation_metadata.provider_type = provider_type

        # Add any additional metadata
        for key, value in kwargs.items():
            if hasattr(self.current_session.generation_metadata, key):
                setattr(self.current_session.generation_metadata, key, value)

        logger.info(f"Started debug session: {self.current_session.session_id}")
        return self.current_session.session_id

    async def end_session(self, success: bool = False, final_code: Optional[str] = None):
        """
        End the current debug session.

        Args:
            success: Whether the generation was successful
            final_code: The final generated code
        """
        if not self.current_session:
            logger.warning("No active debug session to end")
            return

        self.current_session.end_time = datetime.now()
        self.current_session.success = success
        self.current_session.final_code = final_code

        # Calculate total time
        self.current_session.performance_metrics.total_generation_time_ms = self.current_session.duration_ms

        # Add to history
        self.session_history.append(self.current_session)

        # Persist if enabled
        if self.enable_persistence:
            await self._persist_session(self.current_session)

        logger.info(
            f"Ended debug session: {self.current_session.session_id} "
            f"(success: {success}, duration: {self.current_session.duration_ms:.2f}ms)"
        )

        self.current_session = None

    async def record_validation_result(self, validation_result: ValidationResult):
        """
        Record a validation result in the current session.

        Args:
            validation_result: Validation result to record
        """
        if not self.current_session:
            return

        self.current_session.validation_results.append(validation_result)

        # Extract error contexts from validation issues
        for issue in validation_result.issues:
            if issue.severity.name == "ERROR":
                error_context = await self._extract_error_context(
                    issue, self.current_session.final_code or ""
                )
                if error_context:
                    self.current_session.error_contexts.append(error_context)

        logger.debug(f"Recorded validation result with {len(validation_result.issues)} issues")

    async def record_correction_result(self, correction_result: CorrectionResult):
        """
        Record a correction result in the current session.

        Args:
            correction_result: Correction result to record
        """
        if not self.current_session:
            return

        self.current_session.correction_results.append(correction_result)
        self.current_session.performance_metrics.correction_time_ms += correction_result.processing_time_ms

        logger.debug(f"Recorded correction result with {correction_result.total_attempts} attempts")

    async def record_prompt(self, prompt_type: str, prompt_content: str, **metadata):
        """
        Record a prompt used in generation.

        Args:
            prompt_type: Type of prompt (system, user, etc.)
            prompt_content: The prompt content
            **metadata: Additional prompt metadata
        """
        if not self.current_session:
            return

        prompt_record = {
            "type": prompt_type,
            "content": prompt_content,
            "timestamp": datetime.now().isoformat(),
            **metadata
        }

        self.current_session.generation_metadata.prompts_used.append(prompt_record)

    async def record_llm_response(
        self,
        response_content: str,
        usage: Optional[Dict[str, Any]] = None,
        **metadata
    ):
        """
        Record an LLM response.

        Args:
            response_content: The response content
            usage: Token usage information
            **metadata: Additional response metadata
        """
        if not self.current_session:
            return

        response_record = {
            "content": response_content,
            "timestamp": datetime.now().isoformat(),
            "usage": usage or {},
            **metadata
        }

        self.current_session.generation_metadata.llm_responses.append(response_record)

        # Update performance metrics
        if usage:
            self.current_session.performance_metrics.input_tokens += usage.get("input_tokens", 0)
            self.current_session.performance_metrics.output_tokens += usage.get("output_tokens", 0)
            self.current_session.performance_metrics.tokens_used += (
                usage.get("input_tokens", 0) + usage.get("output_tokens", 0)
            )

    async def record_context_documents(self, documents: List[Dict[str, Any]]):
        """
        Record context documents used in generation.

        Args:
            documents: List of context documents
        """
        if not self.current_session:
            return

        self.current_session.generation_metadata.context_documents.extend(documents)

    async def record_performance_metric(self, metric_name: str, value: Union[int, float]):
        """
        Record a performance metric.

        Args:
            metric_name: Name of the metric
            value: Metric value
        """
        if not self.current_session:
            return

        # Map common metric names to performance metrics fields
        metric_mapping = {
            "context_retrieval_time": "context_retrieval_time_ms",
            "prompt_engineering_time": "prompt_engineering_time_ms",
            "llm_generation_time": "llm_generation_time_ms",
            "validation_time": "validation_time_ms",
            "rate_limit_hits": "rate_limit_hits",
            "retries_attempted": "retries_attempted"
        }

        if metric_name in metric_mapping:
            field_name = metric_mapping[metric_name]
            current_value = getattr(self.current_session.performance_metrics, field_name)
            setattr(self.current_session.performance_metrics, field_name, current_value + value)

    async def record_error_context(
        self,
        error_message: str,
        line_number: Optional[int] = None,
        stack_trace: Optional[str] = None,
        code_context: Optional[str] = None
    ):
        """
        Record an error context.

        Args:
            error_message: The error message
            line_number: Line number where error occurred
            stack_trace: Stack trace if available
            code_context: Surrounding code context
        """
        if not self.current_session:
            return

        error_context = ErrorContext(
            line_number=line_number,
            error_message=error_message,
            stack_trace=stack_trace
        )

        if code_context:
            error_context.surrounding_lines = code_context.split('\n')

        self.current_session.error_contexts.append(error_context)

    async def add_custom_log(self, level: str, message: str, **kwargs):
        """
        Add a custom log entry to the debug session.

        Args:
            level: Log level (info, warning, error, etc.)
            message: Log message
            **kwargs: Additional log data
        """
        if not self.current_session:
            return

        log_entry = {
            "timestamp": datetime.now().isoformat(),
            "level": level,
            "message": message,
            **kwargs
        }

        self.current_session.custom_logs.append(log_entry)

    async def _extract_error_context(
        self,
        issue: ValidationIssue,
        code: str
    ) -> Optional[ErrorContext]:
        """
        Extract error context from a validation issue.

        Args:
            issue: Validation issue
            code: The code being validated

        Returns:
            ErrorContext if context can be extracted
        """
        if not code or issue.line_number is None:
            return None

        lines = code.split('\n')
        if issue.line_number < 1 or issue.line_number > len(lines):
            return None

        # Get surrounding lines
        start_line = max(0, issue.line_number - issue.context_window - 1)
        end_line = min(len(lines), issue.line_number + issue.context_window)

        surrounding_lines = []
        for i in range(start_line, end_line):
            marker = ">>> " if i + 1 == issue.line_number else "    "
            surrounding_lines.append(f"{marker}{i + 1:4d}: {lines[i]}")

        return ErrorContext(
            line_number=issue.line_number,
            column_number=issue.column_number,
            surrounding_lines=surrounding_lines,
            error_message=issue.message
        )

    async def _persist_session(self, session: DebugSession):
        """
        Persist a debug session to disk.

        Args:
            session: Session to persist
        """
        try:
            session_file = self.debug_dir / f"debug_session_{session.session_id}.json"

            # Convert session to dictionary
            session_dict = {
                "session_id": session.session_id,
                "start_time": session.start_time.isoformat(),
                "end_time": session.end_time.isoformat() if session.end_time else None,
                "duration_ms": session.duration_ms,
                "success": session.success,
                "generation_metadata": {
                    "generation_id": session.generation_metadata.generation_id,
                    "timestamp": session.generation_metadata.timestamp.isoformat(),
                    "user_query": session.generation_metadata.user_query,
                    "scenario": session.generation_metadata.scenario,
                    "provider_type": session.generation_metadata.provider_type,
                    "model_used": session.generation_metadata.model_used,
                    "temperature": session.generation_metadata.temperature,
                    "max_tokens": session.generation_metadata.max_tokens,
                    "prompts_used": session.generation_metadata.prompts_used,
                    "context_documents": session.generation_metadata.context_documents,
                    "llm_responses": session.generation_metadata.llm_responses
                },
                "performance_metrics": {
                    "total_generation_time_ms": session.performance_metrics.total_generation_time_ms,
                    "context_retrieval_time_ms": session.performance_metrics.context_retrieval_time_ms,
                    "prompt_engineering_time_ms": session.performance_metrics.prompt_engineering_time_ms,
                    "llm_generation_time_ms": session.performance_metrics.llm_generation_time_ms,
                    "validation_time_ms": session.performance_metrics.validation_time_ms,
                    "correction_time_ms": session.performance_metrics.correction_time_ms,
                    "tokens_used": session.performance_metrics.tokens_used,
                    "input_tokens": session.performance_metrics.input_tokens,
                    "output_tokens": session.performance_metrics.output_tokens,
                    "rate_limit_hits": session.performance_metrics.rate_limit_hits,
                    "retries_attempted": session.performance_metrics.retries_attempted
                },
                "validation_results": [
                    {
                        "is_valid": vr.is_valid,
                        "issues": [
                            {
                                "error_type": issue.error_type.value,
                                "severity": issue.severity.value,
                                "message": issue.message,
                                "line_number": issue.line_number,
                                "rule_id": issue.rule_id
                            }
                            for issue in vr.issues
                        ],
                        "processing_time_ms": vr.processing_time_ms,
                        "total_issues": vr.total_issues,
                        "errors_count": vr.errors_count,
                        "warnings_count": vr.warnings_count
                    }
                    for vr in session.validation_results
                ],
                "correction_results": [
                    {
                        "success": cr.success,
                        "total_attempts": cr.total_attempts,
                        "successful_corrections": cr.successful_corrections,
                        "processing_time_ms": cr.processing_time_ms
                    }
                    for cr in session.correction_results
                ],
                "error_contexts": [
                    {
                        "line_number": ec.line_number,
                        "error_message": ec.error_message,
                        "surrounding_lines": ec.surrounding_lines,
                        "stack_trace": ec.stack_trace
                    }
                    for ec in session.error_contexts
                ],
                "custom_logs": session.custom_logs,
                "final_code_length": len(session.final_code) if session.final_code else 0
            }

            # Write to file
            with open(session_file, 'w', encoding='utf-8') as f:
                json.dump(session_dict, f, indent=2, ensure_ascii=False)

            logger.debug(f"Persisted debug session to {session_file}")

        except Exception as e:
            logger.error(f"Failed to persist debug session: {e}")

    async def get_session_summary(self, session_id: Optional[str] = None) -> Dict[str, Any]:
        """
        Get a summary of a debug session or the current session.

        Args:
            session_id: Specific session ID, or None for current session

        Returns:
            Session summary dictionary
        """
        session = self.current_session
        if session_id:
            session = next((s for s in self.session_history if s.session_id == session_id), None)

        if not session:
            return {"error": "Session not found"}

        return {
            "session_id": session.session_id,
            "duration_ms": session.duration_ms,
            "success": session.success,
            "user_query": session.generation_metadata.user_query,
            "scenario": session.generation_metadata.scenario,
            "total_validation_issues": sum(len(vr.issues) for vr in session.validation_results),
            "total_correction_attempts": sum(cr.total_attempts for cr in session.correction_results),
            "successful_corrections": sum(cr.successful_corrections for cr in session.correction_results),
            "tokens_used": session.performance_metrics.tokens_used,
            "error_count": len(session.error_contexts)
        }

    async def get_debug_stats(self) -> Dict[str, Any]:
        """
        Get overall debug statistics.

        Returns:
            Dictionary with debug statistics
        """
        total_sessions = len(self.session_history)
        successful_sessions = sum(1 for s in self.session_history if s.success)
        total_tokens = sum(s.performance_metrics.tokens_used for s in self.session_history)
        total_errors = sum(len(s.error_contexts) for s in self.session_history)

        return {
            "collector_status": "operational",
            "total_sessions": total_sessions,
            "successful_sessions": successful_sessions,
            "success_rate": successful_sessions / total_sessions if total_sessions > 0 else 0,
            "total_tokens_used": total_tokens,
            "total_errors_recorded": total_errors,
            "persistence_enabled": self.enable_persistence,
            "debug_directory": str(self.debug_dir) if self.enable_persistence else None,
            "current_session_active": self.current_session is not None
        }