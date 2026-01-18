"""
Terraform Best Practices Enforcement.

This module provides validation and enforcement of Terraform best practices
including naming conventions, resource organization, and security standards.
"""

from .enforcer import TerraformBestPracticesEnforcer

__all__ = ["TerraformBestPracticesEnforcer"]