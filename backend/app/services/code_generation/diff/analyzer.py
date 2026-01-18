"""
Diff Analyzer for Terraform Code Changes.

This module provides comprehensive analysis of diff content to extract meaningful
insights, categorize changes, assess impact, and generate risk scores.
"""

import re
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Union, Any, Set
from enum import Enum

from logconfig.logger import get_logger

logger = get_logger()


class ChangeType(Enum):
    """Types of changes detected in diff."""
    ADDITION = "addition"
    DELETION = "deletion"
    MODIFICATION = "modification"
    RELOCATION = "relocation"


class ChangeCategory(Enum):
    """Categories of changes based on Terraform constructs."""
    RESOURCE = "resource"
    MODULE = "module"
    VARIABLE = "variable"
    OUTPUT = "output"
    PROVIDER = "provider"
    DATA_SOURCE = "data_source"
    LOCALS = "locals"
    TERRAFORM_BLOCK = "terraform_block"
    OTHER = "other"


class ImpactLevel(Enum):
    """Impact levels for changes."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass
class ChangeItem:
    """Individual change item with metadata."""
    change_type: ChangeType
    category: ChangeCategory
    content: str
    line_number: int
    block_name: Optional[str] = None
    attribute_name: Optional[str] = None
    impact_level: ImpactLevel = ImpactLevel.LOW
    risk_score: float = 0.0
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class DiffAnalysis:
    """Comprehensive analysis of diff content."""
    changes: List[ChangeItem] = field(default_factory=list)
    summary: Dict[str, Any] = field(default_factory=dict)
    risk_assessment: Dict[str, Any] = field(default_factory=dict)
    impact_assessment: Dict[str, Any] = field(default_factory=dict)
    recommendations: List[str] = field(default_factory=list)
    processing_time_ms: float = 0.0


@dataclass
class AnalysisOptions:
    """Configuration options for diff analysis."""
    enable_risk_scoring: bool = True
    enable_impact_assessment: bool = True
    detect_terraform_patterns: bool = True
    max_changes_to_analyze: Optional[int] = None
    include_recommendations: bool = True


class TerraformDiffAnalyzer:
    """
    Advanced analyzer for Terraform diff content with change categorization,
    impact assessment, and risk scoring capabilities.
    """

    def __init__(self):
        """Initialize the diff analyzer."""
        self.default_options = AnalysisOptions()
        self._init_patterns()
        self._init_risk_weights()
        logger.info("TerraformDiffAnalyzer initialized")

    def _init_patterns(self):
        """Initialize regex patterns for Terraform constructs."""
        self.patterns = {
            "resource": re.compile(r'resource\s+"([^"]+)"\s+"([^"]+)"'),
            "module": re.compile(r'module\s+"([^"]+)"'),
            "variable": re.compile(r'variable\s+"([^"]+)"'),
            "output": re.compile(r'output\s+"([^"]+)"'),
            "provider": re.compile(r'provider\s+"([^"]+)"'),
            "data_source": re.compile(r'data\s+"([^"]+)"\s+"([^"]+)"'),
            "locals": re.compile(r'locals\s*\{'),
            "terraform_block": re.compile(r'terraform\s*\{'),
            "attribute": re.compile(r'^(\s*)([a-zA-Z_][a-zA-Z0-9_]*)\s*='),
            "block_start": re.compile(r'^(\s*)\{'),
            "block_end": re.compile(r'^(\s*)\}'),
        }

    def _init_risk_weights(self):
        """Initialize risk scoring weights for different change types."""
        self.risk_weights = {
            ChangeCategory.RESOURCE: {
                ChangeType.ADDITION: 0.3,
                ChangeType.DELETION: 0.8,
                ChangeType.MODIFICATION: 0.5,
            },
            ChangeCategory.MODULE: {
                ChangeType.ADDITION: 0.4,
                ChangeType.DELETION: 0.9,
                ChangeType.MODIFICATION: 0.6,
            },
            ChangeCategory.PROVIDER: {
                ChangeType.ADDITION: 0.6,
                ChangeType.DELETION: 0.9,
                ChangeType.MODIFICATION: 0.7,
            },
            ChangeCategory.VARIABLE: {
                ChangeType.ADDITION: 0.2,
                ChangeType.DELETION: 0.4,
                ChangeType.MODIFICATION: 0.3,
            },
            ChangeCategory.OUTPUT: {
                ChangeType.ADDITION: 0.1,
                ChangeType.DELETION: 0.3,
                ChangeType.MODIFICATION: 0.2,
            },
            ChangeCategory.DATA_SOURCE: {
                ChangeType.ADDITION: 0.2,
                ChangeType.DELETION: 0.5,
                ChangeType.MODIFICATION: 0.3,
            },
            ChangeCategory.TERRAFORM_BLOCK: {
                ChangeType.ADDITION: 0.7,
                ChangeType.DELETION: 0.8,
                ChangeType.MODIFICATION: 0.6,
            },
            ChangeCategory.OTHER: {
                ChangeType.ADDITION: 0.1,
                ChangeType.DELETION: 0.2,
                ChangeType.MODIFICATION: 0.1,
            }
        }

    async def analyze_diff(
        self,
        diff_content: str,
        options: Optional[AnalysisOptions] = None
    ) -> DiffAnalysis:
        """
        Analyze diff content and generate comprehensive insights.

        Args:
            diff_content: Raw diff content to analyze
            options: Analysis configuration options

        Returns:
            DiffAnalysis with detailed change information and assessments
        """
        import time
        start_time = time.time()

        if options is None:
            options = self.default_options

        try:
            # Parse diff lines
            diff_lines = diff_content.splitlines()

            # Extract changes
            changes = self._extract_changes(diff_lines, options)

            # Generate summary
            summary = self._generate_summary(changes)

            # Risk assessment
            risk_assessment = {}
            if options.enable_risk_scoring:
                risk_assessment = self._assess_risk(changes)

            # Impact assessment
            impact_assessment = {}
            if options.enable_impact_assessment:
                impact_assessment = self._assess_impact(changes)

            # Generate recommendations
            recommendations = []
            if options.include_recommendations:
                recommendations = self._generate_recommendations(changes, risk_assessment)

            processing_time = (time.time() - start_time) * 1000

            analysis = DiffAnalysis(
                changes=changes,
                summary=summary,
                risk_assessment=risk_assessment,
                impact_assessment=impact_assessment,
                recommendations=recommendations,
                processing_time_ms=processing_time
            )

            logger.info(
                f"Analyzed diff with {len(changes)} changes in {processing_time:.2f}ms"
            )

            return analysis

        except Exception as e:
            logger.error(f"Diff analysis failed: {e}")
            processing_time = (time.time() - start_time) * 1000
            return DiffAnalysis(
                processing_time_ms=processing_time,
                summary={"error": str(e)}
            )

    def _extract_changes(self, diff_lines: List[str], options: AnalysisOptions) -> List[ChangeItem]:
        """Extract individual changes from diff lines."""
        changes = []
        current_line = 0

        for line in diff_lines:
            current_line += 1

            if line.startswith('+') and not line.startswith('+++'):
                # Addition
                change = self._parse_change_line(line[1:], ChangeType.ADDITION, current_line, options)
                if change:
                    changes.append(change)

            elif line.startswith('-') and not line.startswith('---'):
                # Deletion
                change = self._parse_change_line(line[1:], ChangeType.DELETION, current_line, options)
                if change:
                    changes.append(change)

            # Limit number of changes if specified
            if options.max_changes_to_analyze and len(changes) >= options.max_changes_to_analyze:
                break

        return changes

    def _parse_change_line(
        self,
        content: str,
        change_type: ChangeType,
        line_number: int,
        options: AnalysisOptions
    ) -> Optional[ChangeItem]:
        """Parse a single change line and categorize it."""
        if not options.detect_terraform_patterns:
            return ChangeItem(
                change_type=change_type,
                category=ChangeCategory.OTHER,
                content=content.strip(),
                line_number=line_number
            )

        # Detect Terraform constructs
        category = self._detect_category(content)
        block_name = self._extract_block_name(content, category)
        attribute_name = self._extract_attribute_name(content)

        # Calculate risk score
        risk_score = self._calculate_risk_score(category, change_type)

        # Determine impact level
        impact_level = self._determine_impact_level(category, change_type, content)

        return ChangeItem(
            change_type=change_type,
            category=category,
            content=content.strip(),
            line_number=line_number,
            block_name=block_name,
            attribute_name=attribute_name,
            impact_level=impact_level,
            risk_score=risk_score
        )

    def _detect_category(self, content: str) -> ChangeCategory:
        """Detect the category of a change based on Terraform patterns."""
        content = content.strip()

        # Check for each pattern
        if self.patterns["resource"].search(content):
            return ChangeCategory.RESOURCE
        elif self.patterns["module"].search(content):
            return ChangeCategory.MODULE
        elif self.patterns["variable"].search(content):
            return ChangeCategory.VARIABLE
        elif self.patterns["output"].search(content):
            return ChangeCategory.OUTPUT
        elif self.patterns["provider"].search(content):
            return ChangeCategory.PROVIDER
        elif self.patterns["data_source"].search(content):
            return ChangeCategory.DATA_SOURCE
        elif self.patterns["terraform_block"].search(content):
            return ChangeCategory.TERRAFORM_BLOCK
        elif self.patterns["locals"].search(content):
            return ChangeCategory.LOCALS
        else:
            return ChangeCategory.OTHER

    def _extract_block_name(self, content: str, category: ChangeCategory) -> Optional[str]:
        """Extract block name from content based on category."""
        content = content.strip()

        try:
            if category == ChangeCategory.RESOURCE:
                match = self.patterns["resource"].search(content)
                if match:
                    return f"{match.group(1)}.{match.group(2)}"
            elif category == ChangeCategory.MODULE:
                match = self.patterns["module"].search(content)
                if match:
                    return match.group(1)
            elif category == ChangeCategory.VARIABLE:
                match = self.patterns["variable"].search(content)
                if match:
                    return match.group(1)
            elif category == ChangeCategory.OUTPUT:
                match = self.patterns["output"].search(content)
                if match:
                    return match.group(1)
            elif category == ChangeCategory.PROVIDER:
                match = self.patterns["provider"].search(content)
                if match:
                    return match.group(1)
            elif category == ChangeCategory.DATA_SOURCE:
                match = self.patterns["data_source"].search(content)
                if match:
                    return f"{match.group(1)}.{match.group(2)}"
        except Exception:
            pass

        return None

    def _extract_attribute_name(self, content: str) -> Optional[str]:
        """Extract attribute name from content."""
        match = self.patterns["attribute"].search(content.strip())
        if match:
            return match.group(2)
        return None

    def _calculate_risk_score(self, category: ChangeCategory, change_type: ChangeType) -> float:
        """Calculate risk score for a change."""
        return self.risk_weights.get(category, self.risk_weights[ChangeCategory.OTHER]).get(change_type, 0.1)

    def _determine_impact_level(
        self,
        category: ChangeCategory,
        change_type: ChangeType,
        content: str
    ) -> ImpactLevel:
        """Determine impact level of a change."""
        risk_score = self._calculate_risk_score(category, change_type)

        if risk_score >= 0.8:
            return ImpactLevel.CRITICAL
        elif risk_score >= 0.6:
            return ImpactLevel.HIGH
        elif risk_score >= 0.4:
            return ImpactLevel.MEDIUM
        else:
            return ImpactLevel.LOW

    def _generate_summary(self, changes: List[ChangeItem]) -> Dict[str, Any]:
        """Generate summary statistics from changes."""
        summary = {
            "total_changes": len(changes),
            "additions": 0,
            "deletions": 0,
            "modifications": 0,
            "by_category": {},
            "by_impact": {},
            "unique_blocks_affected": set(),
            "risk_score_range": {"min": float('inf'), "max": 0.0, "avg": 0.0}
        }

        total_risk = 0.0

        for change in changes:
            # Count by type
            if change.change_type == ChangeType.ADDITION:
                summary["additions"] += 1
            elif change.change_type == ChangeType.DELETION:
                summary["deletions"] += 1
            elif change.change_type == ChangeType.MODIFICATION:
                summary["modifications"] += 1

            # Count by category
            cat_key = change.category.value
            summary["by_category"][cat_key] = summary["by_category"].get(cat_key, 0) + 1

            # Count by impact
            impact_key = change.impact_level.value
            summary["by_impact"][impact_key] = summary["by_impact"].get(impact_key, 0) + 1

            # Track unique blocks
            if change.block_name:
                summary["unique_blocks_affected"].add(change.block_name)

            # Risk score statistics
            summary["risk_score_range"]["min"] = min(summary["risk_score_range"]["min"], change.risk_score)
            summary["risk_score_range"]["max"] = max(summary["risk_score_range"]["max"], change.risk_score)
            total_risk += change.risk_score

        # Calculate average risk
        if changes:
            summary["risk_score_range"]["avg"] = total_risk / len(changes)

        # Convert set to count
        summary["unique_blocks_affected"] = len(summary["unique_blocks_affected"])

        return summary

    def _assess_risk(self, changes: List[ChangeItem]) -> Dict[str, Any]:
        """Assess overall risk of the changes."""
        if not changes:
            return {"overall_risk": "low", "score": 0.0}

        total_score = sum(change.risk_score for change in changes)
        avg_score = total_score / len(changes)

        # Determine risk level
        if avg_score >= 0.7:
            risk_level = "critical"
        elif avg_score >= 0.5:
            risk_level = "high"
        elif avg_score >= 0.3:
            risk_level = "medium"
        else:
            risk_level = "low"

        # Find highest risk changes
        high_risk_changes = [c for c in changes if c.risk_score >= 0.6]

        return {
            "overall_risk": risk_level,
            "average_score": avg_score,
            "total_score": total_score,
            "high_risk_changes": len(high_risk_changes),
            "risk_factors": self._identify_risk_factors(changes)
        }

    def _assess_impact(self, changes: List[ChangeItem]) -> Dict[str, Any]:
        """Assess impact of the changes."""
        impact_counts = {
            ImpactLevel.LOW: 0,
            ImpactLevel.MEDIUM: 0,
            ImpactLevel.HIGH: 0,
            ImpactLevel.CRITICAL: 0
        }

        for change in changes:
            impact_counts[change.impact_level] += 1

        # Determine overall impact
        if impact_counts[ImpactLevel.CRITICAL] > 0:
            overall_impact = "critical"
        elif impact_counts[ImpactLevel.HIGH] > 0:
            overall_impact = "high"
        elif impact_counts[ImpactLevel.MEDIUM] > 0:
            overall_impact = "medium"
        else:
            overall_impact = "low"

        return {
            "overall_impact": overall_impact,
            "breakdown": {level.value: count for level, count in impact_counts.items()},
            "resource_count_changes": self._analyze_resource_count_changes(changes)
        }

    def _analyze_resource_count_changes(self, changes: List[ChangeItem]) -> Dict[str, int]:
        """Analyze changes in resource counts."""
        resource_changes = {
            "added": 0,
            "removed": 0,
            "modified": 0
        }

        for change in changes:
            if change.category == ChangeCategory.RESOURCE:
                if change.change_type == ChangeType.ADDITION:
                    resource_changes["added"] += 1
                elif change.change_type == ChangeType.DELETION:
                    resource_changes["removed"] += 1
                elif change.change_type == ChangeType.MODIFICATION:
                    resource_changes["modified"] += 1

        return resource_changes

    def _identify_risk_factors(self, changes: List[ChangeItem]) -> List[str]:
        """Identify key risk factors from changes."""
        factors = []

        # Check for high-risk categories
        high_risk_cats = [ChangeCategory.PROVIDER, ChangeCategory.TERRAFORM_BLOCK]
        for change in changes:
            if change.category in high_risk_cats and change.change_type in [ChangeType.DELETION, ChangeType.MODIFICATION]:
                factors.append(f"High-risk change to {change.category.value}")

        # Check for multiple resource deletions
        deletions = [c for c in changes if c.change_type == ChangeType.DELETION and c.category == ChangeCategory.RESOURCE]
        if len(deletions) > 3:
            factors.append("Multiple resource deletions detected")

        # Check for provider changes
        provider_changes = [c for c in changes if c.category == ChangeCategory.PROVIDER]
        if provider_changes:
            factors.append("Provider configuration changes")

        return factors

    def _generate_recommendations(
        self,
        changes: List[ChangeItem],
        risk_assessment: Dict[str, Any]
    ) -> List[str]:
        """Generate recommendations based on analysis."""
        recommendations = []

        risk_level = risk_assessment.get("overall_risk", "low")

        if risk_level in ["high", "critical"]:
            recommendations.append("Consider testing changes in a development environment first")
            recommendations.append("Review changes with team members before applying")

        # Check for resource deletions
        deletions = [c for c in changes if c.change_type == ChangeType.DELETION and c.category == ChangeCategory.RESOURCE]
        if deletions:
            recommendations.append("Verify that deleted resources are safe to remove and not in use")

        # Check for provider changes
        provider_changes = [c for c in changes if c.category == ChangeCategory.PROVIDER]
        if provider_changes:
            recommendations.append("Provider changes may require re-initialization with 'terraform init'")

        # Check for terraform block changes
        tf_changes = [c for c in changes if c.category == ChangeCategory.TERRAFORM_BLOCK]
        if tf_changes:
            recommendations.append("Terraform block changes may affect backend configuration")

        if not recommendations:
            recommendations.append("Changes appear to be low-risk, but always test before applying")

        return recommendations

    async def get_analyzer_stats(self) -> Dict[str, Any]:
        """Get statistics about the diff analyzer."""
        return {
            "status": "operational",
            "patterns_loaded": len(self.patterns),
            "risk_categories": len(self.risk_weights),
            "change_types": len(ChangeType),
            "impact_levels": len(ImpactLevel)
        }