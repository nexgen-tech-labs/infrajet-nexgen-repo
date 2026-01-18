"""
Documentation generation utilities for Azure File Share integration.

This package provides comprehensive documentation generation capabilities
using Anthropic for intelligent content creation, including API references,
workflow guides, and OpenAPI enhancements.
"""

from .doc_generator import (
    DocGenerator,
    DocumentationType,
    DocumentationFormat,
    DocumentationRequest,
    DocumentationSection,
    GeneratedDocumentation,
    OpenAPIEnhancement,
    generate_api_documentation,
    generate_workflow_guide,
    generate_integration_guide,
    enhance_openapi_spec,
)

__all__ = [
    "DocGenerator",
    "DocumentationType",
    "DocumentationFormat",
    "DocumentationRequest",
    "DocumentationSection",
    "GeneratedDocumentation",
    "OpenAPIEnhancement",
    "generate_api_documentation",
    "generate_workflow_guide",
    "generate_integration_guide",
    "enhance_openapi_spec",
]
