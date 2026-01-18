"""
Terraform Best Practices Enforcer.

This module enforces Terraform best practices including naming conventions,
resource organization standards, security best practices, and performance optimization.
"""

import re
from typing import Dict, List, Any, Optional
from dataclasses import dataclass
from enum import Enum

from logconfig.logger import get_logger

logger = get_logger()


class PracticeCategory(Enum):
    """Categories of best practices."""
    NAMING = "naming"
    ORGANIZATION = "organization"
    SECURITY = "security"
    PERFORMANCE = "performance"
    MAINTAINABILITY = "maintainability"


class PracticeSeverity(Enum):
    """Severity levels for practice violations."""
    ERROR = "error"
    WARNING = "warning"
    INFO = "info"


@dataclass
class PracticeViolation:
    """Represents a best practice violation."""
    category: PracticeCategory
    severity: PracticeSeverity
    rule: str
    message: str
    suggestion: str
    line_number: Optional[int] = None
    context: Optional[str] = None


@dataclass
class BestPracticesReport:
    """Report of best practices analysis."""
    violations: List[PracticeViolation]
    score: float  # 0-100, higher is better
    total_violations: int
    errors_count: int
    warnings_count: int
    info_count: int


class TerraformBestPracticesEnforcer:
    """
    Enforces Terraform best practices and provides recommendations.

    This class analyzes Terraform code against established best practices
    and provides actionable recommendations for improvement.
    """

    def __init__(self):
        """Initialize the best practices enforcer."""
        self.naming_patterns = {
            'resource': re.compile(r'resource\s+"([^"]+)"\s+"([^"]+)"'),
            'module': re.compile(r'module\s+"([^"]+)"'),
            'variable': re.compile(r'variable\s+"([^"]+)"'),
            'output': re.compile(r'output\s+"([^"]+)"'),
            'data': re.compile(r'data\s+"([^"]+)"\s+"([^"]+)"'),
        }

        logger.info("TerraformBestPracticesEnforcer initialized")

    def analyze_code(self, code: str, strict_mode: bool = False) -> BestPracticesReport:
        """
        Analyze Terraform code for best practices violations.

        Args:
            code: Terraform code to analyze
            strict_mode: Enable strict validation rules

        Returns:
            BestPracticesReport with violations and score
        """
        violations = []

        # Run all analysis checks
        violations.extend(self._check_naming_conventions(code, strict_mode))
        violations.extend(self._check_resource_organization(code))
        violations.extend(self._check_security_practices(code))
        violations.extend(self._check_performance_optimization(code))
        violations.extend(self._check_maintainability(code))

        # Calculate score
        score = self._calculate_score(violations)

        # Count violations by severity
        errors_count = sum(1 for v in violations if v.severity == PracticeSeverity.ERROR)
        warnings_count = sum(1 for v in violations if v.severity == PracticeSeverity.WARNING)
        info_count = sum(1 for v in violations if v.severity == PracticeSeverity.INFO)

        report = BestPracticesReport(
            violations=violations,
            score=score,
            total_violations=len(violations),
            errors_count=errors_count,
            warnings_count=warnings_count,
            info_count=info_count
        )

        logger.info(f"Best practices analysis completed: {len(violations)} violations, score: {score:.1f}")

        return report

    def _check_naming_conventions(self, code: str, strict_mode: bool) -> List[PracticeViolation]:
        """Check Terraform naming conventions."""
        violations = []
        lines = code.split('\n')

        for i, line in enumerate(lines, 1):
            # Check resource naming
            resource_match = self.naming_patterns['resource'].search(line)
            if resource_match:
                resource_type, resource_name = resource_match.groups()
                violations.extend(self._validate_resource_name(resource_type, resource_name, i, strict_mode))

            # Check module naming
            module_match = self.naming_patterns['module'].search(line)
            if module_match:
                module_name = module_match.group(1)
                violations.extend(self._validate_module_name(module_name, i, strict_mode))

            # Check variable naming
            variable_match = self.naming_patterns['variable'].search(line)
            if variable_match:
                var_name = variable_match.group(1)
                violations.extend(self._validate_variable_name(var_name, i, strict_mode))

            # Check output naming
            output_match = self.naming_patterns['output'].search(line)
            if output_match:
                output_name = output_match.group(1)
                violations.extend(self._validate_output_name(output_name, i, strict_mode))

        return violations

    def _validate_resource_name(self, resource_type: str, resource_name: str, line_num: int, strict_mode: bool) -> List[PracticeViolation]:
        """Validate resource naming conventions."""
        violations = []

        # Check for underscores (prefer hyphens)
        if '_' in resource_name:
            severity = PracticeSeverity.ERROR if strict_mode else PracticeSeverity.WARNING
            violations.append(PracticeViolation(
                category=PracticeCategory.NAMING,
                severity=severity,
                rule="resource_name_underscores",
                message=f"Resource name '{resource_name}' contains underscores",
                suggestion="Use hyphens instead of underscores in resource names for consistency",
                line_number=line_num,
                context=f"resource \"{resource_type}\" \"{resource_name}\""
            ))

        # Check length
        if len(resource_name) > 64:
            violations.append(PracticeViolation(
                category=PracticeCategory.NAMING,
                severity=PracticeSeverity.WARNING,
                rule="resource_name_length",
                message=f"Resource name '{resource_name}' is too long ({len(resource_name)} characters)",
                suggestion="Keep resource names under 64 characters for readability",
                line_number=line_num
            ))

        # Check for uppercase
        if any(c.isupper() for c in resource_name):
            violations.append(PracticeViolation(
                category=PracticeCategory.NAMING,
                severity=PracticeSeverity.INFO,
                rule="resource_name_case",
                message=f"Resource name '{resource_name}' contains uppercase characters",
                suggestion="Use lowercase with hyphens for resource names",
                line_number=line_num
            ))

        return violations

    def _validate_module_name(self, module_name: str, line_num: int, strict_mode: bool) -> List[PracticeViolation]:
        """Validate module naming conventions."""
        violations = []

        # Check for underscores
        if '_' in module_name:
            severity = PracticeSeverity.ERROR if strict_mode else PracticeSeverity.WARNING
            violations.append(PracticeViolation(
                category=PracticeCategory.NAMING,
                severity=severity,
                rule="module_name_underscores",
                message=f"Module name '{module_name}' contains underscores",
                suggestion="Use hyphens instead of underscores in module names",
                line_number=line_num,
                context=f"module \"{module_name}\""
            ))

        return violations

    def _validate_variable_name(self, var_name: str, line_num: int, strict_mode: bool) -> List[PracticeViolation]:
        """Validate variable naming conventions."""
        violations = []

        # Variables should use underscores by convention
        if '-' in var_name:
            violations.append(PracticeViolation(
                category=PracticeCategory.NAMING,
                severity=PracticeSeverity.INFO,
                rule="variable_name_hyphens",
                message=f"Variable name '{var_name}' contains hyphens",
                suggestion="Use underscores in variable names for consistency",
                line_number=line_num,
                context=f"variable \"{var_name}\""
            ))

        return violations

    def _validate_output_name(self, output_name: str, line_num: int, strict_mode: bool) -> List[PracticeViolation]:
        """Validate output naming conventions."""
        violations = []

        # Outputs should use underscores by convention
        if '-' in output_name:
            violations.append(PracticeViolation(
                category=PracticeCategory.NAMING,
                severity=PracticeSeverity.INFO,
                rule="output_name_hyphens",
                message=f"Output name '{output_name}' contains hyphens",
                suggestion="Use underscores in output names for consistency",
                line_number=line_num,
                context=f"output \"{output_name}\""
            ))

        return violations

    def _check_resource_organization(self, code: str) -> List[PracticeViolation]:
        """Check resource organization and structure."""
        violations = []

        # Check for multiple providers in one file
        provider_count = code.count('provider "')
        if provider_count > 1:
            violations.append(PracticeViolation(
                category=PracticeCategory.ORGANIZATION,
                severity=PracticeSeverity.WARNING,
                rule="multiple_providers",
                message=f"Multiple providers ({provider_count}) defined in one file",
                suggestion="Consider separating providers into different files or using workspaces"
            ))

        # Check for resources without descriptions
        lines = code.split('\n')
        for i, line in enumerate(lines, 1):
            if 'resource "' in line and 'description' not in code[i:i+10]:
                # Look for the resource block
                resource_block = self._extract_resource_block(lines, i)
                if resource_block and 'description' not in resource_block:
                    violations.append(PracticeViolation(
                        category=PracticeCategory.ORGANIZATION,
                        severity=PracticeSeverity.INFO,
                        rule="missing_description",
                        message="Resource block missing description",
                        suggestion="Add a description field to document the resource purpose",
                        line_number=i
                    ))

        return violations

    def _check_security_practices(self, code: str) -> List[PracticeViolation]:
        """Check security best practices."""
        violations = []

        # Check for hardcoded secrets
        secret_patterns = [
            (r'password\s*=\s*["\'][^"\']+["\']', "Hardcoded password detected"),
            (r'secret\s*=\s*["\'][^"\']+["\']', "Hardcoded secret detected"),
            (r'key\s*=\s*["\'][^"\']+["\']', "Hardcoded key detected"),
            (r'token\s*=\s*["\'][^"\']+["\']', "Hardcoded token detected"),
        ]

        lines = code.split('\n')
        for i, line in enumerate(lines, 1):
            for pattern, message in secret_patterns:
                if re.search(pattern, line, re.IGNORECASE):
                    violations.append(PracticeViolation(
                        category=PracticeCategory.SECURITY,
                        severity=PracticeSeverity.ERROR,
                        rule="hardcoded_secret",
                        message=message,
                        suggestion="Use variables or secret management for sensitive values",
                        line_number=i,
                        context=line.strip()
                    ))

        # Check for public access without restrictions
        if 'publicly_accessible' in code and 'true' in code:
            violations.append(PracticeViolation(
                category=PracticeCategory.SECURITY,
                severity=PracticeSeverity.WARNING,
                rule="public_access",
                message="Resource configured with public access",
                suggestion="Review if public access is necessary and implement proper security controls"
            ))

        return violations

    def _check_performance_optimization(self, code: str) -> List[PracticeViolation]:
        """Check performance optimization practices."""
        violations = []

        # Check for count without for_each (potential performance issue)
        if 'count =' in code and 'for_each =' not in code:
            lines = code.split('\n')
            for i, line in enumerate(lines, 1):
                if 'count =' in line:
                    violations.append(PracticeViolation(
                        category=PracticeCategory.PERFORMANCE,
                        severity=PracticeSeverity.INFO,
                        rule="count_without_foreach",
                        message="Using count without for_each may impact performance",
                        suggestion="Consider using for_each instead of count for better performance",
                        line_number=i,
                        context=line.strip()
                    ))

        return violations

    def _check_maintainability(self, code: str) -> List[PracticeViolation]:
        """Check maintainability practices."""
        violations = []

        # Check for very long lines
        lines = code.split('\n')
        for i, line in enumerate(lines, 1):
            if len(line) > 120:
                violations.append(PracticeViolation(
                    category=PracticeCategory.MAINTAINABILITY,
                    severity=PracticeSeverity.INFO,
                    rule="long_line",
                    message=f"Line {i} is {len(line)} characters long",
                    suggestion="Break long lines for better readability and maintainability",
                    line_number=i
                ))

        # Check for complex expressions
        complex_patterns = [
            (r'\$\{.*\$\{.*\$\{.*', "Highly nested interpolation"),
            (r'length\s*\([^)]+\)', "Complex length expression"),
        ]

        for i, line in enumerate(lines, 1):
            for pattern, message in complex_patterns:
                if re.search(pattern, line):
                    violations.append(PracticeViolation(
                        category=PracticeCategory.MAINTAINABILITY,
                        severity=PracticeSeverity.WARNING,
                        rule="complex_expression",
                        message=message,
                        suggestion="Consider simplifying complex expressions using locals or variables",
                        line_number=i,
                        context=line.strip()
                    ))

        return violations

    def _extract_resource_block(self, lines: List[str], start_line: int) -> Optional[str]:
        """Extract a resource block from lines."""
        # Simple extraction - in practice, this would need proper parsing
        block_lines = []
        brace_count = 0
        in_block = False

        for i in range(start_line - 1, min(start_line + 20, len(lines))):
            line = lines[i]
            if 'resource "' in line:
                in_block = True

            if in_block:
                block_lines.append(line)
                brace_count += line.count('{') - line.count('}')

                if brace_count == 0 and in_block and line.strip().endswith('}'):
                    break

        return '\n'.join(block_lines) if block_lines else None

    def _calculate_score(self, violations: List[PracticeViolation]) -> float:
        """Calculate a best practices score from 0-100."""
        if not violations:
            return 100.0

        # Weight violations by severity
        error_weight = 10
        warning_weight = 3
        info_weight = 1

        total_penalty = 0
        for violation in violations:
            if violation.severity == PracticeSeverity.ERROR:
                total_penalty += error_weight
            elif violation.severity == PracticeSeverity.WARNING:
                total_penalty += warning_weight
            elif violation.severity == PracticeSeverity.INFO:
                total_penalty += info_weight

        # Cap penalty and calculate score
        max_penalty = 100  # Score of 0 if penalty reaches this
        penalty = min(total_penalty, max_penalty)

        return max(0, 100 - penalty)

    def get_practice_recommendations(self, code: str) -> Dict[str, Any]:
        """
        Get practice recommendations for improving Terraform code.

        Args:
            code: Terraform code to analyze

        Returns:
            Dictionary with recommendations organized by category
        """
        report = self.analyze_code(code)

        recommendations = {
            "overall_score": report.score,
            "categories": {}
        }

        # Group violations by category
        for category in PracticeCategory:
            category_violations = [v for v in report.violations if v.category == category]
            if category_violations:
                recommendations["categories"][category.value] = {
                    "violations": len(category_violations),
                    "issues": [
                        {
                            "rule": v.rule,
                            "message": v.message,
                            "suggestion": v.suggestion,
                            "severity": v.severity.value,
                            "line_number": v.line_number
                        }
                        for v in category_violations[:5]  # Top 5 issues
                    ]
                }

        return recommendations