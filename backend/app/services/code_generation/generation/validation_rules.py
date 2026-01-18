"""
Modular Validation Rules Engine for Terraform Code.

This module provides a comprehensive, extensible validation rules engine that can
validate different Terraform constructs with modular, configurable rules.
"""

import re
from typing import Dict, List, Any, Optional, Callable, Union, Pattern
from dataclasses import dataclass, field
from enum import Enum
from abc import ABC, abstractmethod

from logconfig.logger import get_logger
from .validator import ValidationIssue, ValidationErrorType, ValidationSeverity

logger = get_logger()


class RuleCategory(Enum):
    """Categories of validation rules."""
    SYNTAX = "syntax"
    SEMANTIC = "semantic"
    STYLE = "style"
    SECURITY = "security"
    NAMING = "naming"
    DEPENDENCY = "dependency"
    PERFORMANCE = "performance"


@dataclass
class ValidationRule:
    """A single validation rule with its configuration."""
    rule_id: str
    name: str
    description: str
    category: RuleCategory
    severity: ValidationSeverity
    enabled: bool = True
    target_constructs: List[str] = field(default_factory=list)  # e.g., ["resource", "variable", "module"]
    conditions: Dict[str, Any] = field(default_factory=dict)
    error_message: str = ""
    suggestion: Optional[str] = None
    validate_function: Optional[Callable] = None

    def __post_init__(self):
        if not self.error_message:
            self.error_message = f"Validation failed for rule: {self.name}"


@dataclass
class RuleValidationResult:
    """Result of validating a single rule."""
    rule: ValidationRule
    passed: bool
    issues: List[ValidationIssue] = field(default_factory=list)
    processing_time_ms: float = 0.0


class BaseRuleValidator(ABC):
    """Base class for rule validators."""

    def __init__(self, rule: ValidationRule):
        self.rule = rule

    @abstractmethod
    async def validate(self, code: str, context: Optional[Dict[str, Any]] = None) -> RuleValidationResult:
        """
        Validate code against this rule.

        Args:
            code: Terraform code to validate
            context: Additional validation context

        Returns:
            RuleValidationResult with validation outcome
        """
        pass


class PatternBasedValidator(BaseRuleValidator):
    """Validator for pattern-based rules."""

    def __init__(self, rule: ValidationRule):
        super().__init__(rule)
        self.patterns = self._compile_patterns()

    def _compile_patterns(self) -> Dict[str, Pattern]:
        """Compile regex patterns from rule conditions."""
        patterns = {}
        if "patterns" in self.rule.conditions:
            for key, pattern_str in self.rule.conditions["patterns"].items():
                try:
                    patterns[key] = re.compile(pattern_str, re.MULTILINE | re.IGNORECASE)
                except re.error as e:
                    logger.error(f"Failed to compile pattern for rule {self.rule.rule_id}: {e}")
        return patterns

    async def validate(self, code: str, context: Optional[Dict[str, Any]] = None) -> RuleValidationResult:
        """Validate using pattern matching."""
        import time
        start_time = time.time()

        issues = []

        try:
            # Check for forbidden patterns
            if "forbidden_patterns" in self.rule.conditions:
                for pattern_key, pattern in self.patterns.items():
                    if pattern_key.startswith("forbidden_"):
                        matches = list(pattern.finditer(code))
                        for match in matches:
                            line_number = code[:match.start()].count('\n') + 1
                            issues.append(ValidationIssue(
                                error_type=self._map_category_to_error_type(self.rule.category),
                                severity=self.rule.severity,
                                message=self.rule.error_message,
                                line_number=line_number,
                                context=match.group(0),
                                suggestion=self.rule.suggestion,
                                rule_id=self.rule.rule_id
                            ))

            # Check for required patterns
            if "required_patterns" in self.rule.conditions:
                has_required = False
                for pattern_key, pattern in self.patterns.items():
                    if pattern_key.startswith("required_"):
                        if pattern.search(code):
                            has_required = True
                            break

                if not has_required:
                    issues.append(ValidationIssue(
                        error_type=self._map_category_to_error_type(self.rule.category),
                        severity=self.rule.severity,
                        message=self.rule.error_message,
                        suggestion=self.rule.suggestion,
                        rule_id=self.rule.rule_id
                    ))

            # Check length constraints
            if "max_length" in self.rule.conditions:
                lines = code.split('\n')
                max_length = self.rule.conditions["max_length"]
                for i, line in enumerate(lines, 1):
                    if len(line) > max_length:
                        issues.append(ValidationIssue(
                            error_type=self._map_category_to_error_type(self.rule.category),
                            severity=self.rule.severity,
                            message=f"Line {i} exceeds maximum length of {max_length} characters",
                            line_number=i,
                            context=line,
                            suggestion=self.rule.suggestion,
                            rule_id=self.rule.rule_id
                        ))

        except Exception as e:
            logger.error(f"Pattern validation failed for rule {self.rule.rule_id}: {e}")
            issues.append(ValidationIssue(
                error_type=ValidationErrorType.SYNTAX,
                severity=ValidationSeverity.ERROR,
                message=f"Rule validation failed: {str(e)}",
                rule_id=self.rule.rule_id
            ))

        processing_time = (time.time() - start_time) * 1000

        return RuleValidationResult(
            rule=self.rule,
            passed=len(issues) == 0,
            issues=issues,
            processing_time_ms=processing_time
        )

    def _map_category_to_error_type(self, category: RuleCategory) -> ValidationErrorType:
        """Map rule category to validation error type."""
        mapping = {
            RuleCategory.SYNTAX: ValidationErrorType.SYNTAX,
            RuleCategory.SEMANTIC: ValidationErrorType.SEMANTIC,
            RuleCategory.STYLE: ValidationErrorType.STYLE,
            RuleCategory.SECURITY: ValidationErrorType.SECURITY,
            RuleCategory.NAMING: ValidationErrorType.SEMANTIC,
            RuleCategory.DEPENDENCY: ValidationErrorType.SEMANTIC,
            RuleCategory.PERFORMANCE: ValidationErrorType.SEMANTIC
        }
        return mapping.get(category, ValidationErrorType.SEMANTIC)


class ConstructSpecificValidator(BaseRuleValidator):
    """Validator for specific Terraform constructs."""

    async def validate(self, code: str, context: Optional[Dict[str, Any]] = None) -> RuleValidationResult:
        """Validate specific Terraform constructs."""
        import time
        start_time = time.time()

        issues = []

        try:
            # Parse constructs from code
            constructs = self._parse_constructs(code)

            for construct in constructs:
                if construct["type"] in self.rule.target_constructs:
                    construct_issues = await self._validate_construct(construct, context)
                    issues.extend(construct_issues)

        except Exception as e:
            logger.error(f"Construct validation failed for rule {self.rule.rule_id}: {e}")
            issues.append(ValidationIssue(
                error_type=ValidationErrorType.SEMANTIC,
                severity=ValidationSeverity.ERROR,
                message=f"Construct validation failed: {str(e)}",
                rule_id=self.rule.rule_id
            ))

        processing_time = (time.time() - start_time) * 1000

        return RuleValidationResult(
            rule=self.rule,
            passed=len(issues) == 0,
            issues=issues,
            processing_time_ms=processing_time
        )

    def _parse_constructs(self, code: str) -> List[Dict[str, Any]]:
        """Parse Terraform constructs from code."""
        constructs = []

        # Simple regex-based parsing (in production, would use TreeSitter)
        patterns = {
            "resource": r'resource\s+"([^"]+)"\s+"([^"]+)"\s*\{([^}]*)\}',
            "variable": r'variable\s+"([^"]+)"\s*\{([^}]*)\}',
            "output": r'output\s+"([^"]+)"\s*\{([^}]*)\}',
            "module": r'module\s+"([^"]+)"\s*\{([^}]*)\}',
            "data": r'data\s+"([^"]+)"\s+"([^"]+)"\s*\{([^}]*)\}'
        }

        for construct_type, pattern in patterns.items():
            matches = re.findall(pattern, code, re.DOTALL)
            for match in matches:
                if construct_type in ["resource", "data"]:
                    construct_type_name, name, body = match
                    constructs.append({
                        "type": construct_type,
                        "type_name": construct_type_name,
                        "name": name,
                        "body": body
                    })
                else:
                    name, body = match
                    constructs.append({
                        "type": construct_type,
                        "name": name,
                        "body": body
                    })

        return constructs

    async def _validate_construct(self, construct: Dict[str, Any], context: Optional[Dict[str, Any]]) -> List[ValidationIssue]:
        """Validate a specific construct."""
        issues = []

        # Apply rule-specific validation logic
        if self.rule.rule_id == "resource_naming_convention":
            issues.extend(self._validate_resource_naming(construct))
        elif self.rule.rule_id == "variable_declaration_complete":
            issues.extend(self._validate_variable_declaration(construct))
        elif self.rule.rule_id == "module_source_required":
            issues.extend(self._validate_module_source(construct))
        elif self.rule.rule_id == "output_description_required":
            issues.extend(self._validate_output_description(construct))

        return issues

    def _validate_resource_naming(self, construct: Dict[str, Any]) -> List[ValidationIssue]:
        """Validate resource naming conventions."""
        issues = []

        if construct["type"] == "resource":
            name = construct["name"]
            # Check for underscores (prefer hyphens)
            if '_' in name:
                issues.append(ValidationIssue(
                    error_type=ValidationErrorType.SEMANTIC,
                    severity=ValidationSeverity.WARNING,
                    message=f"Resource name '{name}' contains underscores, consider using hyphens",
                    suggestion="Use hyphens instead of underscores in resource names",
                    rule_id=self.rule.rule_id
                ))

        return issues

    def _validate_variable_declaration(self, construct: Dict[str, Any]) -> List[ValidationIssue]:
        """Validate variable declarations are complete."""
        issues = []

        if construct["type"] == "variable":
            body = construct["body"]
            required_fields = ["type", "description"]

            for field in required_fields:
                if field not in body:
                    issues.append(ValidationIssue(
                        error_type=ValidationErrorType.SEMANTIC,
                        severity=ValidationSeverity.WARNING,
                        message=f"Variable '{construct['name']}' missing {field}",
                        suggestion=f"Add {field} to variable declaration",
                        rule_id=self.rule.rule_id
                    ))

        return issues

    def _validate_module_source(self, construct: Dict[str, Any]) -> List[ValidationIssue]:
        """Validate module has source."""
        issues = []

        if construct["type"] == "module":
            body = construct["body"]
            if "source" not in body:
                issues.append(ValidationIssue(
                    error_type=ValidationErrorType.SEMANTIC,
                    severity=ValidationSeverity.ERROR,
                    message=f"Module '{construct['name']}' missing source parameter",
                    suggestion="Add source parameter to module configuration",
                    rule_id=self.rule.rule_id
                ))

        return issues

    def _validate_output_description(self, construct: Dict[str, Any]) -> List[ValidationIssue]:
        """Validate output has description."""
        issues = []

        if construct["type"] == "output":
            body = construct["body"]
            if "description" not in body:
                issues.append(ValidationIssue(
                    error_type=ValidationErrorType.SEMANTIC,
                    severity=ValidationSeverity.INFO,
                    message=f"Output '{construct['name']}' missing description",
                    suggestion="Add description to output for better documentation",
                    rule_id=self.rule.rule_id
                ))

        return issues


class ValidationRulesEngine:
    """
    Modular validation rules engine for Terraform code.

    This engine manages a collection of validation rules and applies them
    to Terraform code in a modular, extensible way.
    """

    def __init__(self):
        """Initialize the validation rules engine."""
        self.rules: Dict[str, ValidationRule] = {}
        self.rule_validators: Dict[str, BaseRuleValidator] = {}
        self._initialize_default_rules()

        logger.info("ValidationRulesEngine initialized")

    def _initialize_default_rules(self):
        """Initialize default validation rules."""
        default_rules = [
            # Syntax Rules
            ValidationRule(
                rule_id="balanced_braces",
                name="Balanced Braces",
                description="Check for balanced braces in Terraform code",
                category=RuleCategory.SYNTAX,
                severity=ValidationSeverity.ERROR,
                target_constructs=["*"],
                conditions={
                    "patterns": {
                        "forbidden_unbalanced": r'(?<!\\)\{([^{}]*(?<!\\)\{|[^{}]*\})'
                    }
                },
                error_message="Unbalanced braces detected",
                suggestion="Ensure all opening braces '{' have matching closing braces '}'"
            ),

            # Security Rules
            ValidationRule(
                rule_id="no_hardcoded_secrets",
                name="No Hardcoded Secrets",
                description="Detect hardcoded secrets in Terraform code",
                category=RuleCategory.SECURITY,
                severity=ValidationSeverity.ERROR,
                target_constructs=["*"],
                conditions={
                    "patterns": {
                        "forbidden_password": r'password\s*=\s*["\'][^"\']+["\']',
                        "forbidden_secret": r'secret\s*=\s*["\'][^"\']+["\']',
                        "forbidden_key": r'key\s*=\s*["\'][^"\']+["\']',
                        "forbidden_token": r'token\s*=\s*["\'][^"\']+["\']'
                    }
                },
                error_message="Potential hardcoded secret detected",
                suggestion="Use variables or secret management for sensitive values"
            ),

            # Naming Convention Rules
            ValidationRule(
                rule_id="resource_naming_convention",
                name="Resource Naming Convention",
                description="Enforce resource naming conventions",
                category=RuleCategory.NAMING,
                severity=ValidationSeverity.WARNING,
                target_constructs=["resource"],
                error_message="Resource name does not follow naming conventions",
                suggestion="Use hyphens instead of underscores in resource names"
            ),

            # Style Rules
            ValidationRule(
                rule_id="line_length_limit",
                name="Line Length Limit",
                description="Check line length does not exceed limit",
                category=RuleCategory.STYLE,
                severity=ValidationSeverity.INFO,
                target_constructs=["*"],
                conditions={"max_length": 120},
                error_message="Line exceeds maximum length",
                suggestion="Break long lines for better readability"
            ),

            # Semantic Rules
            ValidationRule(
                rule_id="variable_declaration_complete",
                name="Complete Variable Declaration",
                description="Ensure variables have all required fields",
                category=RuleCategory.SEMANTIC,
                severity=ValidationSeverity.WARNING,
                target_constructs=["variable"],
                error_message="Variable declaration is incomplete",
                suggestion="Add missing required fields to variable declaration"
            ),

            ValidationRule(
                rule_id="module_source_required",
                name="Module Source Required",
                description="Ensure modules have source parameter",
                category=RuleCategory.SEMANTIC,
                severity=ValidationSeverity.ERROR,
                target_constructs=["module"],
                error_message="Module missing source parameter",
                suggestion="Add source parameter to module configuration"
            ),

            ValidationRule(
                rule_id="output_description_required",
                name="Output Description Required",
                description="Ensure outputs have descriptions",
                category=RuleCategory.SEMANTIC,
                severity=ValidationSeverity.INFO,
                target_constructs=["output"],
                error_message="Output missing description",
                suggestion="Add description to output for better documentation"
            ),

            # Dependency Rules
            ValidationRule(
                rule_id="explicit_dependencies",
                name="Explicit Dependencies",
                description="Check for explicit resource dependencies",
                category=RuleCategory.DEPENDENCY,
                severity=ValidationSeverity.INFO,
                target_constructs=["resource"],
                error_message="Consider using depends_on for resource dependencies",
                suggestion="Add depends_on blocks for resources that depend on each other"
            ),

            # Performance Rules
            ValidationRule(
                rule_id="avoid_count_loops",
                name="Avoid Count Loops",
                description="Avoid using count for large numbers of resources",
                category=RuleCategory.PERFORMANCE,
                severity=ValidationSeverity.WARNING,
                target_constructs=["resource"],
                conditions={
                    "patterns": {
                        "forbidden_count": r'count\s*=\s*\d+'
                    }
                },
                error_message="Large count values can impact performance",
                suggestion="Consider using for_each instead of count for better performance"
            )
        ]

        for rule in default_rules:
            self.add_rule(rule)

    def add_rule(self, rule: ValidationRule):
        """
        Add a validation rule to the engine.

        Args:
            rule: Validation rule to add
        """
        self.rules[rule.rule_id] = rule

        # Create appropriate validator
        if rule.conditions and ("patterns" in rule.conditions or "max_length" in rule.conditions):
            validator = PatternBasedValidator(rule)
        elif rule.target_constructs:
            validator = ConstructSpecificValidator(rule)
        else:
            # Default to pattern-based for backward compatibility
            validator = PatternBasedValidator(rule)

        self.rule_validators[rule.rule_id] = validator

        logger.debug(f"Added validation rule: {rule.rule_id}")

    def remove_rule(self, rule_id: str):
        """
        Remove a validation rule from the engine.

        Args:
            rule_id: ID of the rule to remove
        """
        if rule_id in self.rules:
            del self.rules[rule_id]
            del self.rule_validators[rule_id]
            logger.debug(f"Removed validation rule: {rule_id}")

    def enable_rule(self, rule_id: str):
        """
        Enable a validation rule.

        Args:
            rule_id: ID of the rule to enable
        """
        if rule_id in self.rules:
            self.rules[rule_id].enabled = True
            logger.debug(f"Enabled validation rule: {rule_id}")

    def disable_rule(self, rule_id: str):
        """
        Disable a validation rule.

        Args:
            rule_id: ID of the rule to disable
        """
        if rule_id in self.rules:
            self.rules[rule_id].enabled = False
            logger.debug(f"Disabled validation rule: {rule_id}")

    async def validate_code(
        self,
        code: str,
        categories: Optional[List[RuleCategory]] = None,
        context: Optional[Dict[str, Any]] = None
    ) -> List[RuleValidationResult]:
        """
        Validate code against all enabled rules.

        Args:
            code: Terraform code to validate
            categories: Optional list of rule categories to validate
            context: Additional validation context

        Returns:
            List of rule validation results
        """
        results = []

        for rule_id, rule in self.rules.items():
            if not rule.enabled:
                continue

            if categories and rule.category not in categories:
                continue

            validator = self.rule_validators.get(rule_id)
            if validator:
                result = await validator.validate(code, context)
                results.append(result)

        return results

    def get_rules_summary(self) -> Dict[str, Any]:
        """
        Get a summary of all validation rules.

        Returns:
            Dictionary with rules summary
        """
        categories = {}
        enabled_count = 0

        for rule in self.rules.values():
            if rule.enabled:
                enabled_count += 1

            category_name = rule.category.value
            if category_name not in categories:
                categories[category_name] = []
            categories[category_name].append({
                "rule_id": rule.rule_id,
                "name": rule.name,
                "severity": rule.severity.value,
                "enabled": rule.enabled
            })

        return {
            "total_rules": len(self.rules),
            "enabled_rules": enabled_count,
            "disabled_rules": len(self.rules) - enabled_count,
            "categories": categories
        }

    def get_rule(self, rule_id: str) -> Optional[ValidationRule]:
        """
        Get a specific validation rule.

        Args:
            rule_id: ID of the rule to retrieve

        Returns:
            ValidationRule if found, None otherwise
        """
        return self.rules.get(rule_id)

    async def validate_with_custom_rules(
        self,
        code: str,
        custom_rules: List[ValidationRule],
        context: Optional[Dict[str, Any]] = None
    ) -> List[RuleValidationResult]:
        """
        Validate code with custom rules (without adding them permanently).

        Args:
            code: Terraform code to validate
            custom_rules: List of custom rules to apply
            context: Additional validation context

        Returns:
            List of rule validation results
        """
        results = []

        for rule in custom_rules:
            # Create temporary validator
            if rule.conditions and ("patterns" in rule.conditions or "max_length" in rule.conditions):
                validator = PatternBasedValidator(rule)
            elif rule.target_constructs:
                validator = ConstructSpecificValidator(rule)
            else:
                validator = PatternBasedValidator(rule)

            result = await validator.validate(code, context)
            results.append(result)

        return results