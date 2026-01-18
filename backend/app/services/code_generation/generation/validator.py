"""
Terraform Validator with TreeSitter Integration.

This module provides comprehensive validation capabilities for generated Terraform code,
including syntax validation, semantic analysis, and best practices checking.
"""

import asyncio
import re
import time
import os
from pathlib import Path
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass, field
from enum import Enum

from logconfig.logger import get_logger
from app.services.tree_sitter_service import TreeSitterService
from app.services.code_generation.config.settings import get_code_generation_settings

logger = get_logger()
settings = get_code_generation_settings()


class ValidationErrorType(Enum):
    """Types of validation errors."""
    SYNTAX = "syntax"
    SEMANTIC = "semantic"
    STYLE = "style"
    SECURITY = "security"


class ValidationSeverity(Enum):
    """Severity levels for validation issues."""
    ERROR = "error"
    WARNING = "warning"
    INFO = "info"


@dataclass
class ValidationIssue:
    """Represents a single validation issue."""
    error_type: ValidationErrorType
    severity: ValidationSeverity
    message: str
    line_number: Optional[int] = None
    column_number: Optional[int] = None
    context: Optional[str] = None
    suggestion: Optional[str] = None
    rule_id: Optional[str] = None


@dataclass
class ValidationResult:
    """Result of a validation operation."""
    is_valid: bool
    issues: List[ValidationIssue] = field(default_factory=list)
    processing_time_ms: float = 0.0
    total_issues: int = 0
    errors_count: int = 0
    warnings_count: int = 0
    info_count: int = 0

    def __post_init__(self):
        self.total_issues = len(self.issues)
        self.errors_count = sum(1 for issue in self.issues if issue.severity == ValidationSeverity.ERROR)
        self.warnings_count = sum(1 for issue in self.issues if issue.severity == ValidationSeverity.WARNING)
        self.info_count = sum(1 for issue in self.issues if issue.severity == ValidationSeverity.INFO)


@dataclass
class FileValidationResult:
    """Result of validating a single file."""
    file_path: str
    file_name: str
    validation_result: ValidationResult
    file_size_bytes: int = 0
    last_modified: Optional[float] = None


@dataclass
class MultiFileValidationResult:
    """Result of validating multiple files."""
    total_files: int = 0
    valid_files: int = 0
    invalid_files: int = 0
    files_with_errors: List[str] = field(default_factory=list)
    files_with_warnings: List[str] = field(default_factory=list)
    file_results: List[FileValidationResult] = field(default_factory=list)
    total_issues: int = 0
    total_errors: int = 0
    total_warnings: int = 0
    total_info: int = 0
    processing_time_ms: float = 0.0
    scanned_directory: Optional[str] = None

    def __post_init__(self):
        self.total_files = len(self.file_results)
        self.valid_files = sum(1 for result in self.file_results if result.validation_result.is_valid)
        self.invalid_files = self.total_files - self.valid_files
        self.files_with_errors = [
            result.file_path for result in self.file_results
            if result.validation_result.errors_count > 0
        ]
        self.files_with_warnings = [
            result.file_path for result in self.file_results
            if result.validation_result.warnings_count > 0 and result.validation_result.errors_count == 0
        ]
        self.total_issues = sum(result.validation_result.total_issues for result in self.file_results)
        self.total_errors = sum(result.validation_result.errors_count for result in self.file_results)
        self.total_warnings = sum(result.validation_result.warnings_count for result in self.file_results)
        self.total_info = sum(result.validation_result.info_count for result in self.file_results)


class TerraformValidator:
    """
    Comprehensive Terraform code validator with TreeSitter integration.

    This validator performs syntax validation, semantic analysis, and best practices
    checking on generated Terraform code using TreeSitter for parsing and AST analysis.
    """

    def __init__(self):
        """Initialize the Terraform validator."""
        try:
            self.tree_sitter = TreeSitterService()
            self.tree_sitter_available = self.tree_sitter.is_available()
        except Exception as e:
            logger.warning(f"TreeSitter service not available: {e}")
            self.tree_sitter = None
            self.tree_sitter_available = False

        self.validation_rules = []  # Will be populated by ValidationRulesEngine
        logger.info(f"TerraformValidator initialized (TreeSitter: {'available' if self.tree_sitter_available else 'unavailable'})")

    async def validate_code(
        self,
        code: str,
        file_path: Optional[str] = None,
        strict_mode: bool = False
    ) -> ValidationResult:
        """
        Validate Terraform code comprehensively.

        Args:
            code: Terraform code to validate
            file_path: Optional file path for context
            strict_mode: Enable strict validation rules

        Returns:
            ValidationResult with detailed issues and metrics
        """
        start_time = time.time()
        issues = []

        try:
            # Stage 1: Syntax Validation
            syntax_issues = await self._validate_syntax(code, file_path)
            issues.extend(syntax_issues)

            # Stage 2: Semantic Validation (if syntax is valid or has only warnings)
            has_critical_errors = any(
                issue.severity == ValidationSeverity.ERROR and
                issue.error_type == ValidationErrorType.SYNTAX
                for issue in syntax_issues
            )

            if not has_critical_errors:
                semantic_issues = await self._validate_semantic(code, file_path)
                issues.extend(semantic_issues)

            # Stage 3: Style and Best Practices Validation
            style_issues = await self._validate_style_and_best_practices(code, file_path, strict_mode)
            issues.extend(style_issues)

            # Stage 4: Security Validation
            security_issues = await self._validate_security(code, file_path)
            issues.extend(security_issues)

            # Determine overall validity
            has_errors = any(issue.severity == ValidationSeverity.ERROR for issue in issues)
            is_valid = not has_errors

            processing_time = (time.time() - start_time) * 1000

            result = ValidationResult(
                is_valid=is_valid,
                issues=issues,
                processing_time_ms=processing_time
            )

            logger.info(
                f"Validation completed for {'file' if file_path else 'code block'}: "
                f"{result.total_issues} issues ({result.errors_count} errors, "
                f"{result.warnings_count} warnings, {result.info_count} info) "
                f"in {processing_time:.2f}ms"
            )

            return result

        except Exception as e:
            logger.error(f"Validation failed: {e}", exc_info=True)
            processing_time = (time.time() - start_time) * 1000

            error_issue = ValidationIssue(
                error_type=ValidationErrorType.SYNTAX,
                severity=ValidationSeverity.ERROR,
                message=f"Validation failed: {str(e)}",
                rule_id="validation_failure"
            )

            return ValidationResult(
                is_valid=False,
                issues=[error_issue],
                processing_time_ms=processing_time
            )

    async def _validate_syntax(
        self,
        code: str,
        file_path: Optional[str]
    ) -> List[ValidationIssue]:
        """
        Perform syntax validation with robust fallback mechanisms.

        Args:
            code: Terraform code to validate
            file_path: Optional file path

        Returns:
            List of syntax validation issues
        """
        issues = []

        try:
            # Try TreeSitter parsing first if available
            if self.tree_sitter_available and self.tree_sitter:
                try:
                    # For TreeSitter, we need to create a temporary file or use content directly
                    if file_path and os.path.exists(file_path):
                        parse_result = await self.tree_sitter.parse_file(file_path)
                        if not parse_result.success:
                            issues.append(ValidationIssue(
                                error_type=ValidationErrorType.SYNTAX,
                                severity=ValidationSeverity.ERROR,
                                message=parse_result.error or "Syntax parsing failed",
                                rule_id="syntax_parse_error"
                            ))
                    else:
                        # For in-memory content, try basic validation
                        issues.extend(self._check_basic_syntax(code))
                except Exception as e:
                    logger.warning(f"TreeSitter parsing failed: {e}, falling back to basic validation")
                    issues.extend(self._check_basic_syntax(code))
            else:
                # TreeSitter not available, use basic validation
                logger.debug("TreeSitter not available, using basic syntax validation")
                issues.extend(self._check_basic_syntax(code))

        except Exception as e:
            logger.error(f"Syntax validation failed: {e}")
            issues.append(ValidationIssue(
                error_type=ValidationErrorType.SYNTAX,
                severity=ValidationSeverity.ERROR,
                message=f"Syntax validation error: {str(e)}",
                rule_id="syntax_validation_error"
            ))

        return issues

    async def _validate_semantic(
        self,
        code: str,
        file_path: Optional[str]
    ) -> List[ValidationIssue]:
        """
        Perform semantic validation on parsed Terraform code.

        Args:
            code: Terraform code to validate
            file_path: Optional file path

        Returns:
            List of semantic validation issues
        """
        issues = []

        try:
            # Check for resource dependencies
            issues.extend(self._check_resource_dependencies(code))

            # Check for variable usage
            issues.extend(self._check_variable_usage(code))

            # Check for module configurations
            issues.extend(self._check_module_configurations(code))

            # Check for data source usage
            issues.extend(self._check_data_source_usage(code))

        except Exception as e:
            logger.error(f"Semantic validation failed: {e}")
            issues.append(ValidationIssue(
                error_type=ValidationErrorType.SEMANTIC,
                severity=ValidationSeverity.ERROR,
                message=f"Semantic validation error: {str(e)}",
                rule_id="semantic_validation_error"
            ))

        return issues

    async def _validate_style_and_best_practices(
        self,
        code: str,
        file_path: Optional[str],
        strict_mode: bool
    ) -> List[ValidationIssue]:
        """
        Validate style and best practices.

        Args:
            code: Terraform code to validate
            file_path: Optional file path
            strict_mode: Enable strict validation

        Returns:
            List of style and best practice issues
        """
        issues = []

        try:
            # Check naming conventions
            issues.extend(self._check_naming_conventions(code, strict_mode))

            # Check code organization
            issues.extend(self._check_code_organization(code))

            # Check for deprecated features
            issues.extend(self._check_deprecated_features(code))

            # Check for code complexity
            issues.extend(self._check_code_complexity(code))

        except Exception as e:
            logger.error(f"Style validation failed: {e}")
            issues.append(ValidationIssue(
                error_type=ValidationErrorType.STYLE,
                severity=ValidationSeverity.WARNING,
                message=f"Style validation error: {str(e)}",
                rule_id="style_validation_error"
            ))

        return issues

    async def _validate_security(
        self,
        code: str,
        file_path: Optional[str]
    ) -> List[ValidationIssue]:
        """
        Perform security validation on Terraform code.

        Args:
            code: Terraform code to validate
            file_path: Optional file path

        Returns:
            List of security validation issues
        """
        issues = []

        try:
            # Check for exposed secrets
            issues.extend(self._check_exposed_secrets(code))

            # Check for insecure configurations
            issues.extend(self._check_insecure_configurations(code))

            # Check for proper access controls
            issues.extend(self._check_access_controls(code))

        except Exception as e:
            logger.error(f"Security validation failed: {e}")
            issues.append(ValidationIssue(
                error_type=ValidationErrorType.SECURITY,
                severity=ValidationSeverity.WARNING,
                message=f"Security validation error: {str(e)}",
                rule_id="security_validation_error"
            ))

        return issues

    def _check_basic_syntax(self, code: str) -> List[ValidationIssue]:
        """Perform basic syntax checks."""
        issues = []

        # Check for balanced braces
        if code.count('{') != code.count('}'):
            issues.append(ValidationIssue(
                error_type=ValidationErrorType.SYNTAX,
                severity=ValidationSeverity.ERROR,
                message="Unbalanced braces: number of '{' does not match number of '}'",
                rule_id="unbalanced_braces"
            ))

        # Check for balanced brackets
        if code.count('[') != code.count(']'):
            issues.append(ValidationIssue(
                error_type=ValidationErrorType.SYNTAX,
                severity=ValidationSeverity.ERROR,
                message="Unbalanced brackets: number of '[' does not match number of ']'",
                rule_id="unbalanced_brackets"
            ))

        # Check for balanced parentheses
        if code.count('(') != code.count(')'):
            issues.append(ValidationIssue(
                error_type=ValidationErrorType.SYNTAX,
                severity=ValidationSeverity.ERROR,
                message="Unbalanced parentheses: number of '(' does not match number of ')'",
                rule_id="unbalanced_parentheses"
            ))

        return issues

    def _check_resource_dependencies(self, code: str) -> List[ValidationIssue]:
        """Check for proper resource dependencies."""
        issues = []
        lines = code.split('\n')

        for i, line in enumerate(lines, 1):
            # Check for resources without proper references
            if 'resource "' in line and 'depends_on' not in code:
                # This is a basic check - in practice, we'd need AST analysis
                issues.append(ValidationIssue(
                    error_type=ValidationErrorType.SEMANTIC,
                    severity=ValidationSeverity.INFO,
                    message="Consider using depends_on for explicit resource dependencies",
                    line_number=i,
                    rule_id="missing_depends_on",
                    suggestion="Add depends_on blocks for resources that depend on each other"
                ))

        return issues

    def _check_variable_usage(self, code: str) -> List[ValidationIssue]:
        """Check variable declarations and usage."""
        issues = []

        # Check for undeclared variables
        import re
        var_usage = re.findall(r'var\.(\w+)', code)
        var_declarations = re.findall(r'variable\s+"(\w+)"', code)

        for var in var_usage:
            if var not in var_declarations:
                issues.append(ValidationIssue(
                    error_type=ValidationErrorType.SEMANTIC,
                    severity=ValidationSeverity.WARNING,
                    message=f"Variable '{var}' is used but not declared",
                    rule_id="undeclared_variable",
                    suggestion=f"Declare variable '{var}' or ensure it's available in the scope"
                ))

        return issues

    def _check_module_configurations(self, code: str) -> List[ValidationIssue]:
        """Check module configurations."""
        issues = []

        # Check for modules without source
        if 'module "' in code and 'source' not in code:
            issues.append(ValidationIssue(
                error_type=ValidationErrorType.SEMANTIC,
                severity=ValidationSeverity.ERROR,
                message="Module declared without source parameter",
                rule_id="module_without_source",
                suggestion="Add source parameter to module configuration"
            ))

        return issues

    def _check_data_source_usage(self, code: str) -> List[ValidationIssue]:
        """Check data source usage."""
        issues = []

        # Check for data sources that might be better as resources
        if 'data "' in code and 'count' in code:
            issues.append(ValidationIssue(
                error_type=ValidationErrorType.SEMANTIC,
                severity=ValidationSeverity.WARNING,
                message="Data source with count - consider if this should be a resource instead",
                rule_id="data_source_with_count",
                suggestion="Review if this data source should be converted to a resource"
            ))

        return issues

    def _check_naming_conventions(self, code: str, strict_mode: bool) -> List[ValidationIssue]:
        """Check Terraform naming conventions."""
        issues = []

        # Check resource naming
        import re
        resource_pattern = r'resource\s+"([^"]+)"\s+"([^"]+)"'
        for match in re.finditer(resource_pattern, code):
            resource_type, resource_name = match.groups()

            # Check for underscores in resource names (prefer hyphens)
            if '_' in resource_name and strict_mode:
                issues.append(ValidationIssue(
                    error_type=ValidationErrorType.STYLE,
                    severity=ValidationSeverity.WARNING,
                    message=f"Resource name '{resource_name}' contains underscores, consider using hyphens",
                    rule_id="resource_name_underscores",
                    suggestion="Use hyphens instead of underscores in resource names"
                ))

        return issues

    def _check_code_organization(self, code: str) -> List[ValidationIssue]:
        """Check code organization and structure."""
        issues = []

        # Check for multiple providers in one file
        provider_count = code.count('provider "')
        if provider_count > 1:
            issues.append(ValidationIssue(
                error_type=ValidationErrorType.STYLE,
                severity=ValidationSeverity.INFO,
                message=f"Multiple providers ({provider_count}) in one file",
                rule_id="multiple_providers",
                suggestion="Consider separating providers into different files or using workspaces"
            ))

        return issues

    def _check_deprecated_features(self, code: str) -> List[ValidationIssue]:
        """Check for deprecated Terraform features."""
        issues = []

        # Check for deprecated syntax
        if 'terraform.workspace' in code:
            issues.append(ValidationIssue(
                error_type=ValidationErrorType.STYLE,
                severity=ValidationSeverity.WARNING,
                message="terraform.workspace is deprecated in Terraform 0.12+",
                rule_id="deprecated_workspace",
                suggestion="Use terraform.workspace from terraform 0.12+ or workspace() function"
            ))

        return issues

    def _check_code_complexity(self, code: str) -> List[ValidationIssue]:
        """Check for code complexity issues."""
        issues = []

        # Check for very long lines
        lines = code.split('\n')
        for i, line in enumerate(lines, 1):
            if len(line) > 120:
                issues.append(ValidationIssue(
                    error_type=ValidationErrorType.STYLE,
                    severity=ValidationSeverity.INFO,
                    message=f"Line {i} is {len(line)} characters long, consider breaking it",
                    line_number=i,
                    rule_id="long_line",
                    suggestion="Break long lines for better readability"
                ))

        return issues

    def _check_exposed_secrets(self, code: str) -> List[ValidationIssue]:
        """Check for potentially exposed secrets."""
        issues = []

        # Check for hardcoded secrets
        sensitive_patterns = [
            r'password\s*=\s*["\'][^"\']+["\']',
            r'secret\s*=\s*["\'][^"\']+["\']',
            r'key\s*=\s*["\'][^"\']+["\']',
            r'token\s*=\s*["\'][^"\']+["\']'
        ]

        import re
        for pattern in sensitive_patterns:
            for match in re.finditer(pattern, code, re.IGNORECASE):
                issues.append(ValidationIssue(
                    error_type=ValidationErrorType.SECURITY,
                    severity=ValidationSeverity.ERROR,
                    message="Potential hardcoded secret detected",
                    rule_id="hardcoded_secret",
                    suggestion="Use variables or secret management for sensitive values"
                ))

        return issues

    def _check_insecure_configurations(self, code: str) -> List[ValidationIssue]:
        """Check for insecure configurations."""
        issues = []

        # Check for public access
        if 'publicly_accessible' in code and 'true' in code:
            issues.append(ValidationIssue(
                error_type=ValidationErrorType.SECURITY,
                severity=ValidationSeverity.WARNING,
                message="Resource configured with public access",
                rule_id="public_access",
                suggestion="Review if public access is necessary and secure"
            ))

        return issues

    def _check_access_controls(self, code: str) -> List[ValidationIssue]:
        """Check for proper access controls."""
        issues = []

        # This would be expanded with more specific checks
        # For now, just a placeholder for access control validation

        return issues

    async def validate_files(
        self,
        file_paths: List[str],
        strict_mode: bool = False
    ) -> MultiFileValidationResult:
        """
        Validate multiple Terraform files.

        Args:
            file_paths: List of file paths to validate
            strict_mode: Enable strict validation rules

        Returns:
            MultiFileValidationResult with results for all files
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
                        code = f.read()
                except Exception as e:
                    logger.error(f"Failed to read file {file_path}: {e}")
                    continue

                # Get file metadata
                file_stat = os.stat(file_path)
                file_size = file_stat.st_size
                last_modified = file_stat.st_mtime

                # Validate the file
                validation_result = await self.validate_code(
                    code=code,
                    file_path=file_path,
                    strict_mode=strict_mode
                )

                file_result = FileValidationResult(
                    file_path=file_path,
                    file_name=os.path.basename(file_path),
                    validation_result=validation_result,
                    file_size_bytes=file_size,
                    last_modified=last_modified
                )

                file_results.append(file_result)

            processing_time = (time.time() - start_time) * 1000

            result = MultiFileValidationResult(
                file_results=file_results,
                processing_time_ms=processing_time
            )

            logger.info(
                f"Multi-file validation completed: {result.total_files} files, "
                f"{result.invalid_files} invalid, {result.total_errors} errors, "
                f"{result.total_warnings} warnings in {processing_time:.2f}ms"
            )

            return result

        except Exception as e:
            logger.error(f"Multi-file validation failed: {e}", exc_info=True)
            processing_time = (time.time() - start_time) * 1000

            return MultiFileValidationResult(
                file_results=file_results,
                processing_time_ms=processing_time
            )

    async def scan_and_validate_directory(
        self,
        directory_path: str,
        recursive: bool = True,
        file_pattern: str = "*.tf",
        strict_mode: bool = False
    ) -> MultiFileValidationResult:
        """
        Scan a directory for Terraform files and validate them.

        Args:
            directory_path: Path to directory to scan
            recursive: Whether to scan subdirectories
            file_pattern: Glob pattern for files to include
            strict_mode: Enable strict validation rules

        Returns:
            MultiFileValidationResult with validation results
        """
        start_time = time.time()

        try:
            # Find all Terraform files
            path_obj = Path(directory_path)
            if recursive:
                tf_files = list(path_obj.rglob(file_pattern))
            else:
                tf_files = list(path_obj.glob(file_pattern))

            # Convert to string paths
            file_paths = [str(f) for f in tf_files if f.is_file()]

            logger.info(f"Found {len(file_paths)} Terraform files in {directory_path}")

            # Validate all files
            result = await self.validate_files(
                file_paths=file_paths,
                strict_mode=strict_mode
            )

            result.scanned_directory = directory_path

            return result

        except Exception as e:
            logger.error(f"Directory scan failed: {e}", exc_info=True)
            processing_time = (time.time() - start_time) * 1000

            return MultiFileValidationResult(
                processing_time_ms=processing_time,
                scanned_directory=directory_path
            )

    def get_problematic_files(
        self,
        validation_result: MultiFileValidationResult,
        include_warnings: bool = False
    ) -> List[str]:
        """
        Get list of files that have validation issues.

        Args:
            validation_result: Result from multi-file validation
            include_warnings: Whether to include files with only warnings

        Returns:
            List of file paths with issues
        """
        problematic_files = validation_result.files_with_errors.copy()

        if include_warnings:
            problematic_files.extend(validation_result.files_with_warnings)

        return list(set(problematic_files))  # Remove duplicates

    async def get_validation_stats(self) -> Dict[str, Any]:
        """
        Get validation statistics and health information.

        Returns:
            Dictionary with validation statistics
        """
        return {
            "validator_status": "operational",
            "supported_features": [
                "syntax_validation",
                "semantic_validation",
                "style_validation",
                "security_validation",
                "multi_file_validation",
                "directory_scanning"
            ],
            "tree_sitter_integration": True,
            "async_processing": True,
            "multi_file_support": True
        }