"""
Terraform Error Corrector with LLM Integration.

This module provides automatic error correction capabilities for generated Terraform code,
using both pattern-based fixes and LLM-powered intelligent corrections.
"""

import asyncio
import time
import re
import os
from pathlib import Path
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass, field
from enum import Enum

from logconfig.logger import get_logger
from app.services.code_generation.llm_providers.provider_factory import ProviderFactory
from app.services.code_generation.llm_providers.base import LLMRequest, LLMResponse
from app.services.code_generation.config.settings import get_code_generation_settings
from .validator import (
    TerraformValidator, ValidationIssue, ValidationErrorType, ValidationSeverity,
    MultiFileValidationResult, FileValidationResult
)

logger = get_logger()
settings = get_code_generation_settings()


class CorrectionType(Enum):
    """Types of corrections that can be applied."""
    PATTERN_BASED = "pattern_based"
    LLM_POWERED = "llm_powered"
    MANUAL = "manual"


class CorrectionStatus(Enum):
    """Status of a correction attempt."""
    SUCCESS = "success"
    FAILED = "failed"
    PARTIAL = "partial"
    NO_CHANGE = "no_change"


@dataclass
class CorrectionAttempt:
    """Represents a single correction attempt."""
    correction_type: CorrectionType
    status: CorrectionStatus
    original_issue: ValidationIssue
    corrected_code: Optional[str] = None
    applied_fix: Optional[str] = None
    confidence_score: float = 0.0
    processing_time_ms: float = 0.0
    error_message: Optional[str] = None


@dataclass
class CorrectionResult:
    """Result of an error correction operation."""
    original_code: str
    corrected_code: str
    attempts: List[CorrectionAttempt] = field(default_factory=list)
    success: bool = False
    total_attempts: int = 0
    successful_corrections: int = 0
    processing_time_ms: float = 0.0

    def __post_init__(self):
        self.total_attempts = len(self.attempts)
        self.successful_corrections = sum(
            1 for attempt in self.attempts
            if attempt.status == CorrectionStatus.SUCCESS
        )


@dataclass
class FileCorrectionResult:
    """Result of correcting a single file."""
    file_path: str
    file_name: str
    original_content: str
    corrected_content: str
    correction_result: CorrectionResult
    was_modified: bool = False
    backup_created: bool = False
    backup_path: Optional[str] = None


@dataclass
class MultiFileCorrectionResult:
    """Result of correcting multiple files."""
    total_files_processed: int = 0
    files_corrected: int = 0
    files_with_errors: int = 0
    files_unchanged: int = 0
    file_results: List[FileCorrectionResult] = field(default_factory=list)
    total_corrections_attempted: int = 0
    total_corrections_successful: int = 0
    processing_time_ms: float = 0.0
    processed_directory: Optional[str] = None

    def __post_init__(self):
        self.total_files_processed = len(self.file_results)
        self.files_corrected = sum(1 for result in self.file_results if result.was_modified)
        self.files_with_errors = sum(
            1 for result in self.file_results
            if not result.correction_result.success and result.was_modified
        )
        self.files_unchanged = self.total_files_processed - self.files_corrected
        self.total_corrections_attempted = sum(
            result.correction_result.total_attempts for result in self.file_results
        )
        self.total_corrections_successful = sum(
            result.correction_result.successful_corrections for result in self.file_results
        )


class TerraformErrorCorrector:
    """
    Automatic error corrector for Terraform code using pattern-based and LLM-powered fixes.

    This corrector can automatically fix common Terraform syntax errors and use
    Claude for intelligent corrections of complex issues.
    """

    def __init__(self):
        """Initialize the error corrector."""
        self.validator = TerraformValidator()
        self.provider_factory = ProviderFactory()
        self.correction_history = []

        # Pattern-based correction rules
        self.pattern_fixes = self._initialize_pattern_fixes()

        logger.info("TerraformErrorCorrector initialized")

    async def correct_errors(
        self,
        code: str,
        validation_issues: Optional[List[ValidationIssue]] = None,
        max_iterations: int = 3,
        use_llm: bool = True
    ) -> CorrectionResult:
        """
        Correct errors in Terraform code using iterative approach.

        Args:
            code: Terraform code with errors
            validation_issues: Pre-computed validation issues (optional)
            max_iterations: Maximum correction iterations
            use_llm: Whether to use LLM for complex corrections

        Returns:
            CorrectionResult with corrected code and attempt history
        """
        start_time = time.time()
        original_code = code
        current_code = code
        attempts = []

        try:
            # Get validation issues if not provided
            if validation_issues is None:
                validation_result = await self.validator.validate_code(code)
                validation_issues = validation_result.issues

            # Filter issues that can be corrected
            correctable_issues = [
                issue for issue in validation_issues
                if self._is_issue_correctable(issue)
            ]

            if not correctable_issues:
                logger.info("No correctable issues found")
                return CorrectionResult(
                    original_code=original_code,
                    corrected_code=current_code,
                    attempts=attempts,
                    success=True,
                    processing_time_ms=(time.time() - start_time) * 1000
                )

            # Iterative correction
            for iteration in range(max_iterations):
                logger.info(f"Starting correction iteration {iteration + 1}/{max_iterations}")

                iteration_attempts = await self._correct_iteration(
                    current_code, correctable_issues, use_llm
                )
                attempts.extend(iteration_attempts)

                # Update current code with successful corrections
                for attempt in iteration_attempts:
                    if attempt.status == CorrectionStatus.SUCCESS and attempt.corrected_code:
                        current_code = attempt.corrected_code

                # Re-validate to check if issues are resolved
                validation_result = await self.validator.validate_code(current_code)
                remaining_issues = [
                    issue for issue in validation_result.issues
                    if self._is_issue_correctable(issue)
                ]

                if not remaining_issues:
                    logger.info("All correctable issues resolved")
                    break

                correctable_issues = remaining_issues

            # Final validation
            final_validation = await self.validator.validate_code(current_code)
            success = len([
                issue for issue in final_validation.issues
                if issue.severity == ValidationSeverity.ERROR
            ]) == 0

            processing_time = (time.time() - start_time) * 1000

            result = CorrectionResult(
                original_code=original_code,
                corrected_code=current_code,
                attempts=attempts,
                success=success,
                processing_time_ms=processing_time
            )

            # Store in correction history
            self.correction_history.append({
                "timestamp": time.time(),
                "result": result,
                "final_validation": final_validation
            })

            logger.info(
                f"Error correction completed: {result.successful_corrections}/{result.total_attempts} "
                f"successful corrections in {processing_time:.2f}ms"
            )

            return result

        except Exception as e:
            logger.error(f"Error correction failed: {e}", exc_info=True)
            processing_time = (time.time() - start_time) * 1000

            return CorrectionResult(
                original_code=original_code,
                corrected_code=current_code,
                attempts=attempts,
                success=False,
                processing_time_ms=processing_time
            )

    async def _correct_iteration(
        self,
        code: str,
        issues: List[ValidationIssue],
        use_llm: bool
    ) -> List[CorrectionAttempt]:
        """
        Perform one iteration of error correction.

        Args:
            code: Current code state
            issues: Issues to correct
            use_llm: Whether to use LLM corrections

        Returns:
            List of correction attempts for this iteration
        """
        attempts = []

        for issue in issues:
            attempt_start = time.time()

            try:
                # Try pattern-based correction first
                pattern_attempt = await self._apply_pattern_fix(code, issue)
                if pattern_attempt and pattern_attempt.status == CorrectionStatus.SUCCESS:
                    attempts.append(pattern_attempt)
                    continue

                # If pattern fix failed and LLM is enabled, try LLM correction
                if use_llm:
                    llm_attempt = await self._apply_llm_fix(code, issue)
                    attempts.append(llm_attempt)
                else:
                    # Create failed attempt for pattern fix
                    if not pattern_attempt:
                        pattern_attempt = CorrectionAttempt(
                            correction_type=CorrectionType.PATTERN_BASED,
                            status=CorrectionStatus.FAILED,
                            original_issue=issue,
                            processing_time_ms=(time.time() - attempt_start) * 1000,
                            error_message="No pattern fix available"
                        )
                    attempts.append(pattern_attempt)

            except Exception as e:
                logger.error(f"Correction attempt failed for issue {issue.rule_id}: {e}")
                failed_attempt = CorrectionAttempt(
                    correction_type=CorrectionType.PATTERN_BASED,
                    status=CorrectionStatus.FAILED,
                    original_issue=issue,
                    processing_time_ms=(time.time() - attempt_start) * 1000,
                    error_message=str(e)
                )
                attempts.append(failed_attempt)

        return attempts

    async def _apply_pattern_fix(
        self,
        code: str,
        issue: ValidationIssue
    ) -> Optional[CorrectionAttempt]:
        """
        Apply pattern-based fixes for known issues.

        Args:
            code: Code to fix
            issue: Validation issue to fix

        Returns:
            CorrectionAttempt if fix was attempted, None otherwise
        """
        start_time = time.time()

        # Find applicable pattern fix
        fix_rule = None
        for rule in self.pattern_fixes:
            if rule["rule_id"] == issue.rule_id:
                fix_rule = rule
                break

        if not fix_rule:
            return None

        try:
            # Apply the fix
            fixed_code = fix_rule["fix_function"](code, issue)

            # Validate the fix
            validation_result = await self.validator.validate_code(fixed_code)
            has_same_issue = any(
                i.rule_id == issue.rule_id for i in validation_result.issues
            )

            status = CorrectionStatus.SUCCESS if not has_same_issue else CorrectionStatus.FAILED

            return CorrectionAttempt(
                correction_type=CorrectionType.PATTERN_BASED,
                status=status,
                original_issue=issue,
                corrected_code=fixed_code if status == CorrectionStatus.SUCCESS else None,
                applied_fix=fix_rule["name"],
                confidence_score=fix_rule.get("confidence", 0.8),
                processing_time_ms=(time.time() - start_time) * 1000
            )

        except Exception as e:
            logger.error(f"Pattern fix failed: {e}")
            return CorrectionAttempt(
                correction_type=CorrectionType.PATTERN_BASED,
                status=CorrectionStatus.FAILED,
                original_issue=issue,
                processing_time_ms=(time.time() - start_time) * 1000,
                error_message=str(e)
            )

    async def _apply_llm_fix(
        self,
        code: str,
        issue: ValidationIssue
    ) -> CorrectionAttempt:
        """
        Apply LLM-powered fix for complex issues.

        Args:
            code: Code to fix
            issue: Validation issue to fix

        Returns:
            CorrectionAttempt with LLM correction result
        """
        start_time = time.time()

        try:
            # Create LLM provider
            llm_config = settings.get_llm_config_dict()
            provider = self.provider_factory.create_from_config(llm_config)

            # Create correction prompt
            prompt = self._create_correction_prompt(code, issue)

            # Create LLM request
            llm_request = LLMRequest(
                prompt=prompt,
                system_message=self._get_correction_system_message(),
                config=provider.config
            )

            # Get correction from LLM
            response: LLMResponse = await provider.generate(llm_request)

            # Extract corrected code from response
            corrected_code = self._extract_corrected_code_from_response(response.content)

            if corrected_code:
                # Validate the correction
                validation_result = await self.validator.validate_code(corrected_code)
                has_same_issue = any(
                    i.rule_id == issue.rule_id for i in validation_result.issues
                )

                status = CorrectionStatus.SUCCESS if not has_same_issue else CorrectionStatus.PARTIAL

                return CorrectionAttempt(
                    correction_type=CorrectionType.LLM_POWERED,
                    status=status,
                    original_issue=issue,
                    corrected_code=corrected_code,
                    applied_fix="LLM-powered correction",
                    confidence_score=0.7,  # LLM corrections have moderate confidence
                    processing_time_ms=(time.time() - start_time) * 1000
                )
            else:
                return CorrectionAttempt(
                    correction_type=CorrectionType.LLM_POWERED,
                    status=CorrectionStatus.FAILED,
                    original_issue=issue,
                    processing_time_ms=(time.time() - start_time) * 1000,
                    error_message="Failed to extract corrected code from LLM response"
                )

        except Exception as e:
            logger.error(f"LLM correction failed: {e}")
            return CorrectionAttempt(
                correction_type=CorrectionType.LLM_POWERED,
                status=CorrectionStatus.FAILED,
                original_issue=issue,
                processing_time_ms=(time.time() - start_time) * 1000,
                error_message=str(e)
            )

    def _initialize_pattern_fixes(self) -> List[Dict[str, Any]]:
        """Initialize pattern-based correction rules."""
        return [
            {
                "rule_id": "unbalanced_braces",
                "name": "Fix unbalanced braces",
                "confidence": 0.9,
                "fix_function": self._fix_unbalanced_braces
            },
            {
                "rule_id": "unbalanced_brackets",
                "name": "Fix unbalanced brackets",
                "confidence": 0.9,
                "fix_function": self._fix_unbalanced_brackets
            },
            {
                "rule_id": "unbalanced_parentheses",
                "name": "Fix unbalanced parentheses",
                "confidence": 0.9,
                "fix_function": self._fix_unbalanced_parentheses
            },
            {
                "rule_id": "missing_depends_on",
                "name": "Add depends_on block",
                "confidence": 0.6,
                "fix_function": self._fix_missing_depends_on
            },
            {
                "rule_id": "module_without_source",
                "name": "Add source to module",
                "confidence": 0.8,
                "fix_function": self._fix_module_without_source
            },
            {
                "rule_id": "undeclared_variable",
                "name": "Add variable declaration",
                "confidence": 0.7,
                "fix_function": self._fix_undeclared_variable
            },
            {
                "rule_id": "hardcoded_secret",
                "name": "Replace hardcoded secret with variable",
                "confidence": 0.8,
                "fix_function": self._fix_hardcoded_secret
            }
        ]

    def _fix_unbalanced_braces(self, code: str, issue: ValidationIssue) -> str:
        """Fix unbalanced braces by adding missing ones."""
        # Simple heuristic: add closing braces at the end if needed
        open_count = code.count('{')
        close_count = code.count('}')

        if open_count > close_count:
            missing = open_count - close_count
            return code + ('\n}' * missing)
        elif close_count > open_count:
            missing = close_count - open_count
            return ('{\n' * missing) + code

        return code

    def _fix_unbalanced_brackets(self, code: str, issue: ValidationIssue) -> str:
        """Fix unbalanced brackets."""
        open_count = code.count('[')
        close_count = code.count(']')

        if open_count > close_count:
            missing = open_count - close_count
            return code + (']' * missing)
        elif close_count > open_count:
            missing = close_count - open_count
            return ('[' * missing) + code

        return code

    def _fix_unbalanced_parentheses(self, code: str, issue: ValidationIssue) -> str:
        """Fix unbalanced parentheses."""
        open_count = code.count('(')
        close_count = code.count(')')

        if open_count > close_count:
            missing = open_count - close_count
            return code + (')' * missing)
        elif close_count > open_count:
            missing = close_count - open_count
            return ('(' * missing) + code

        return code

    def _fix_missing_depends_on(self, code: str, issue: ValidationIssue) -> str:
        """Add depends_on block to resources."""
        # This is a complex fix that would require AST analysis
        # For now, add a comment suggesting manual addition
        return code + "\n\n# TODO: Add depends_on blocks for resource dependencies"

    def _fix_module_without_source(self, code: str, issue: ValidationIssue) -> str:
        """Add source parameter to module."""
        # Find module blocks without source
        lines = code.split('\n')
        for i, line in enumerate(lines):
            if 'module "' in line and '{' in line:
                # Insert source line after module declaration
                lines.insert(i + 1, '  source = "git::https://example.com/module.git" # TODO: Update source URL')
                break

        return '\n'.join(lines)

    def _fix_undeclared_variable(self, code: str, issue: ValidationIssue) -> str:
        """Add variable declaration for undeclared variables."""
        # Extract variable name from issue message
        var_match = re.search(r"Variable '(\w+)' is used but not declared", issue.message)
        if var_match:
            var_name = var_match.group(1)
            var_declaration = f'\nvariable "{var_name}" {{\n  description = "TODO: Add description"\n  type        = string\n  default     = ""\n}}\n'
            return var_declaration + code

        return code

    def _fix_hardcoded_secret(self, code: str, issue: ValidationIssue) -> str:
        """Replace hardcoded secrets with variables."""
        # This is a basic implementation - in practice, would need more sophisticated pattern matching
        secret_patterns = [
            (r'password\s*=\s*["\']([^"\']+)["\']', 'password'),
            (r'secret\s*=\s*["\']([^"\']+)["\']', 'secret'),
            (r'key\s*=\s*["\']([^"\']+)["\']', 'key'),
            (r'token\s*=\s*["\']([^"\']+)["\']', 'token')
        ]

        for pattern, var_type in secret_patterns:
            def replace_secret(match):
                value = match.group(1)
                var_name = f"{var_type}_value"
                return f'{var_type} = var.{var_name}'

            code = re.sub(pattern, replace_secret, code, flags=re.IGNORECASE)

        return code

    def _create_correction_prompt(self, code: str, issue: ValidationIssue) -> str:
        """Create a prompt for LLM-powered correction."""
        return f"""
Please fix the following Terraform code issue:

ISSUE TYPE: {issue.error_type.value}
SEVERITY: {issue.severity.value}
MESSAGE: {issue.message}
{"SUGGESTION: " + issue.suggestion if issue.suggestion else ""}

ORIGINAL CODE:
```hcl
{code}
```

Please provide the corrected Terraform code that addresses this issue. Return only the corrected code block without any explanation.
"""

    def _get_correction_system_message(self) -> str:
        """Get system message for LLM corrections."""
        return """
You are an expert Terraform developer. Your task is to fix Terraform code issues while maintaining the original intent and following Terraform best practices.

Guidelines:
- Fix only the specific issue mentioned
- Maintain the original code structure and logic
- Follow Terraform naming conventions and best practices
- Ensure the corrected code is syntactically valid
- Add appropriate comments if complex changes are made
- Return only the corrected code, no explanations

Focus on:
- Syntax errors and corrections
- Best practice violations
- Security improvements
- Code clarity and maintainability
"""

    def _extract_corrected_code_from_response(self, response_content: str) -> Optional[str]:
        """Extract corrected code from LLM response."""
        # Look for code blocks in the response
        code_block_pattern = r'```(?:hcl|terraform)?\n?(.*?)\n?```'
        matches = re.findall(code_block_pattern, response_content, re.DOTALL)

        if matches:
            return matches[0].strip()

        # If no code blocks, return the entire response
        return response_content.strip()

    def _is_issue_correctable(self, issue: ValidationIssue) -> bool:
        """Determine if a validation issue can be automatically corrected."""
        # Define which issues can be corrected
        correctable_rules = {
            "unbalanced_braces",
            "unbalanced_brackets",
            "unbalanced_parentheses",
            "missing_depends_on",
            "module_without_source",
            "undeclared_variable",
            "hardcoded_secret",
            "resource_name_underscores",
            "long_line"
        }

        return (
            issue.rule_id in correctable_rules and
            issue.severity in [ValidationSeverity.ERROR, ValidationSeverity.WARNING]
        )

    async def correct_files(
        self,
        file_paths: List[str],
        max_iterations: int = 3,
        use_llm: bool = True,
        create_backups: bool = True,
        backup_suffix: str = ".backup"
    ) -> MultiFileCorrectionResult:
        """
        Correct errors in multiple Terraform files.

        Args:
            file_paths: List of file paths to correct
            max_iterations: Maximum correction iterations per file
            use_llm: Whether to use LLM for complex corrections
            create_backups: Whether to create backup files before modification
            backup_suffix: Suffix for backup files

        Returns:
            MultiFileCorrectionResult with results for all files
        """
        start_time = time.time()
        file_results = []

        try:
            for file_path in file_paths:
                if not os.path.exists(file_path):
                    logger.warning(f"File not found: {file_path}")
                    continue

                # Read file content
                try:
                    with open(file_path, 'r', encoding='utf-8') as f:
                        original_content = f.read()
                except Exception as e:
                    logger.error(f"Failed to read file {file_path}: {e}")
                    continue

                # Create backup if requested
                backup_path = None
                if create_backups:
                    backup_path = f"{file_path}{backup_suffix}"
                    try:
                        with open(backup_path, 'w', encoding='utf-8') as f:
                            f.write(original_content)
                        logger.info(f"Created backup: {backup_path}")
                    except Exception as e:
                        logger.error(f"Failed to create backup for {file_path}: {e}")
                        backup_path = None

                # Correct the file
                correction_result = await self.correct_errors(
                    code=original_content,
                    max_iterations=max_iterations,
                    use_llm=use_llm
                )

                # Check if content was actually changed
                was_modified = correction_result.corrected_code != original_content

                # Write corrected content back to file if modified
                if was_modified:
                    try:
                        with open(file_path, 'w', encoding='utf-8') as f:
                            f.write(correction_result.corrected_code)
                        logger.info(f"Updated file: {file_path}")
                    except Exception as e:
                        logger.error(f"Failed to write corrected content to {file_path}: {e}")
                        was_modified = False

                file_result = FileCorrectionResult(
                    file_path=file_path,
                    file_name=os.path.basename(file_path),
                    original_content=original_content,
                    corrected_content=correction_result.corrected_code,
                    correction_result=correction_result,
                    was_modified=was_modified,
                    backup_created=backup_path is not None,
                    backup_path=backup_path
                )

                file_results.append(file_result)

            processing_time = (time.time() - start_time) * 1000

            result = MultiFileCorrectionResult(
                file_results=file_results,
                processing_time_ms=processing_time
            )

            logger.info(
                f"Multi-file correction completed: {result.total_files_processed} files processed, "
                f"{result.files_corrected} corrected, {result.total_corrections_successful} "
                f"successful corrections in {processing_time:.2f}ms"
            )

            return result

        except Exception as e:
            logger.error(f"Multi-file correction failed: {e}", exc_info=True)
            processing_time = (time.time() - start_time) * 1000

            return MultiFileCorrectionResult(
                file_results=file_results,
                processing_time_ms=processing_time
            )

    async def scan_and_correct_directory(
        self,
        directory_path: str,
        validation_result: Optional[MultiFileValidationResult] = None,
        recursive: bool = True,
        file_pattern: str = "*.tf",
        max_iterations: int = 3,
        use_llm: bool = True,
        create_backups: bool = True,
        only_problematic: bool = True
    ) -> MultiFileCorrectionResult:
        """
        Scan directory, identify problematic files, and correct them.

        Args:
            directory_path: Path to directory to scan
            validation_result: Pre-computed validation results (optional)
            recursive: Whether to scan subdirectories
            file_pattern: Glob pattern for files to include
            max_iterations: Maximum correction iterations per file
            use_llm: Whether to use LLM for complex corrections
            create_backups: Whether to create backup files
            only_problematic: Only correct files that have validation issues

        Returns:
            MultiFileCorrectionResult with correction results
        """
        start_time = time.time()

        try:
            # Get validation results if not provided
            if validation_result is None:
                validation_result = await self.validator.scan_and_validate_directory(
                    directory_path=directory_path,
                    recursive=recursive,
                    file_pattern=file_pattern
                )

            # Determine which files to correct
            if only_problematic:
                files_to_correct = self.validator.get_problematic_files(
                    validation_result, include_warnings=True
                )
                logger.info(f"Found {len(files_to_correct)} problematic files to correct")
            else:
                files_to_correct = [result.file_path for result in validation_result.file_results]

            # Correct the files
            result = await self.correct_files(
                file_paths=files_to_correct,
                max_iterations=max_iterations,
                use_llm=use_llm,
                create_backups=create_backups
            )

            result.processed_directory = directory_path

            return result

        except Exception as e:
            logger.error(f"Directory scan and correction failed: {e}", exc_info=True)
            processing_time = (time.time() - start_time) * 1000

            return MultiFileCorrectionResult(
                processing_time_ms=processing_time,
                processed_directory=directory_path
            )

    async def autonomous_correction_cycle(
        self,
        directory_path: str,
        max_cycles: int = 3,
        max_iterations_per_file: int = 3,
        use_llm: bool = True,
        create_backups: bool = True,
        convergence_threshold: float = 0.95
    ) -> List[MultiFileCorrectionResult]:
        """
        Run autonomous correction cycles until convergence or max cycles reached.

        Args:
            directory_path: Path to directory to process
            max_cycles: Maximum number of correction cycles
            max_iterations_per_file: Maximum iterations per file per cycle
            use_llm: Whether to use LLM for complex corrections
            create_backups: Whether to create backup files
            convergence_threshold: Threshold for considering system converged (0.0-1.0)

        Returns:
            List of MultiFileCorrectionResult for each cycle
        """
        cycle_results = []
        previous_error_rate = 1.0

        logger.info(f"Starting autonomous correction with max {max_cycles} cycles")

        for cycle in range(max_cycles):
            logger.info(f"Starting correction cycle {cycle + 1}/{max_cycles}")

            # Scan and validate current state
            validation_result = await self.validator.scan_and_validate_directory(directory_path)

            # Calculate current error rate
            total_files = validation_result.total_files
            if total_files == 0:
                logger.info("No files found to process")
                break

            current_error_rate = validation_result.total_errors / total_files

            logger.info(
                f"Cycle {cycle + 1}: {validation_result.total_errors} errors in "
                f"{total_files} files (error rate: {current_error_rate:.3f})"
            )

            # Check for convergence
            if current_error_rate <= (1.0 - convergence_threshold):
                logger.info(f"Convergence achieved at cycle {cycle + 1}")
                break

            # Check if we're making progress
            if cycle > 0 and current_error_rate >= previous_error_rate:
                logger.warning(f"No improvement in cycle {cycle + 1}, stopping")
                break

            # Perform corrections
            correction_result = await self.scan_and_correct_directory(
                directory_path=directory_path,
                validation_result=validation_result,
                max_iterations=max_iterations_per_file,
                use_llm=use_llm,
                create_backups=create_backups,
                only_problematic=True
            )

            cycle_results.append(correction_result)
            previous_error_rate = current_error_rate

            # If no files were corrected, stop
            if correction_result.files_corrected == 0:
                logger.info("No files corrected in this cycle, stopping")
                break

        logger.info(f"Autonomous correction completed after {len(cycle_results)} cycles")
        return cycle_results

    def generate_correction_report(
        self,
        correction_result: MultiFileCorrectionResult,
        include_details: bool = True
    ) -> Dict[str, Any]:
        """
        Generate a detailed report of correction results.

        Args:
            correction_result: Result from multi-file correction
            include_details: Whether to include detailed per-file information

        Returns:
            Dictionary with correction report
        """
        report = {
            "summary": {
                "total_files_processed": correction_result.total_files_processed,
                "files_corrected": correction_result.files_corrected,
                "files_with_errors": correction_result.files_with_errors,
                "files_unchanged": correction_result.files_unchanged,
                "total_corrections_attempted": correction_result.total_corrections_attempted,
                "total_corrections_successful": correction_result.total_corrections_successful,
                "processing_time_ms": correction_result.processing_time_ms,
                "processed_directory": correction_result.processed_directory,
                "success_rate": (
                    correction_result.total_corrections_successful /
                    correction_result.total_corrections_attempted
                    if correction_result.total_corrections_attempted > 0 else 0
                )
            },
            "files": []
        }

        if include_details:
            for file_result in correction_result.file_results:
                file_info = {
                    "file_path": file_result.file_path,
                    "file_name": file_result.file_name,
                    "was_modified": file_result.was_modified,
                    "backup_created": file_result.backup_created,
                    "backup_path": file_result.backup_path,
                    "correction_success": file_result.correction_result.success,
                    "attempts_made": file_result.correction_result.total_attempts,
                    "successful_corrections": file_result.correction_result.successful_corrections,
                    "processing_time_ms": file_result.correction_result.processing_time_ms
                }

                # Add details about specific issues and fixes
                if file_result.correction_result.attempts:
                    file_info["issues_corrected"] = []
                    for attempt in file_result.correction_result.attempts:
                        if attempt.status == CorrectionStatus.SUCCESS:
                            file_info["issues_corrected"].append({
                                "issue_type": attempt.original_issue.error_type.value,
                                "severity": attempt.original_issue.severity.value,
                                "message": attempt.original_issue.message,
                                "fix_applied": attempt.applied_fix,
                                "confidence": attempt.confidence_score
                            })

                report["files"].append(file_info)

        return report

    def generate_validation_report(
        self,
        validation_result: MultiFileValidationResult,
        include_details: bool = True
    ) -> Dict[str, Any]:
        """
        Generate a detailed report of validation results.

        Args:
            validation_result: Result from multi-file validation
            include_details: Whether to include detailed per-file information

        Returns:
            Dictionary with validation report
        """
        report = {
            "summary": {
                "total_files": validation_result.total_files,
                "valid_files": validation_result.valid_files,
                "invalid_files": validation_result.invalid_files,
                "files_with_errors": len(validation_result.files_with_errors),
                "files_with_warnings": len(validation_result.files_with_warnings),
                "total_issues": validation_result.total_issues,
                "total_errors": validation_result.total_errors,
                "total_warnings": validation_result.total_warnings,
                "total_info": validation_result.total_info,
                "processing_time_ms": validation_result.processing_time_ms,
                "scanned_directory": validation_result.scanned_directory
            },
            "files": []
        }

        if include_details:
            for file_result in validation_result.file_results:
                file_info = {
                    "file_path": file_result.file_path,
                    "file_name": file_result.file_name,
                    "is_valid": file_result.validation_result.is_valid,
                    "issues_count": file_result.validation_result.total_issues,
                    "errors_count": file_result.validation_result.errors_count,
                    "warnings_count": file_result.validation_result.warnings_count,
                    "info_count": file_result.validation_result.info_count,
                    "file_size_bytes": file_result.file_size_bytes,
                    "last_modified": file_result.last_modified,
                    "processing_time_ms": file_result.validation_result.processing_time_ms
                }

                # Add details about specific issues
                if file_result.validation_result.issues:
                    file_info["issues"] = []
                    for issue in file_result.validation_result.issues:
                        file_info["issues"].append({
                            "type": issue.error_type.value,
                            "severity": issue.severity.value,
                            "message": issue.message,
                            "line_number": issue.line_number,
                            "column_number": issue.column_number,
                            "rule_id": issue.rule_id,
                            "suggestion": issue.suggestion
                        })

                report["files"].append(file_info)

        return report

    async def get_correction_stats(self) -> Dict[str, Any]:
        """
        Get correction statistics and history.

        Returns:
            Dictionary with correction statistics
        """
        total_corrections = len(self.correction_history)
        successful_corrections = sum(
            1 for entry in self.correction_history
            if entry["result"].success
        )

        return {
            "corrector_status": "operational",
            "total_corrections": total_corrections,
            "successful_corrections": successful_corrections,
            "success_rate": successful_corrections / total_corrections if total_corrections > 0 else 0,
            "pattern_fixes_available": len(self.pattern_fixes),
            "llm_integration": True,
            "async_processing": True,
            "multi_file_support": True,
            "autonomous_correction": True
        }