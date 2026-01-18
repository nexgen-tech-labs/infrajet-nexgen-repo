"""
Documentation Generation Module using Anthropic.

This module provides comprehensive documentation generation capabilities
for the Azure File Share integration, including API examples, workflow guides,
and OpenAPI enhancements.
"""

import json
import logging
from typing import Dict, List, Optional, Any, Union
from dataclasses import dataclass, asdict
from enum import Enum
from pathlib import Path
import yaml
from datetime import datetime

from pydantic import BaseModel, Field


class DocumentationType(str, Enum):
    """Types of documentation that can be generated."""

    API_REFERENCE = "api_reference"
    WORKFLOW_GUIDE = "workflow_guide"
    INTEGRATION_GUIDE = "integration_guide"
    TROUBLESHOOTING = "troubleshooting"
    EXAMPLES = "examples"
    OPENAPI_ENHANCEMENT = "openapi_enhancement"


class DocumentationFormat(str, Enum):
    """Output formats for generated documentation."""

    MARKDOWN = "markdown"
    HTML = "html"
    JSON = "json"
    YAML = "yaml"
    OPENAPI = "openapi"


@dataclass
class DocumentationRequest:
    """Request for documentation generation."""

    doc_type: DocumentationType
    title: str
    description: Optional[str] = None
    format: DocumentationFormat = DocumentationFormat.MARKDOWN
    include_examples: bool = True
    include_code_snippets: bool = True
    target_audience: str = "developers"
    api_endpoints: Optional[List[str]] = None
    workflow_steps: Optional[List[str]] = None
    metadata: Optional[Dict[str, Any]] = None


class DocumentationSection(BaseModel):
    """A section within generated documentation."""

    title: str = Field(description="Section title")
    content: str = Field(description="Section content")
    subsections: List["DocumentationSection"] = Field(
        default_factory=list, description="Nested subsections"
    )
    code_examples: List[Dict[str, str]] = Field(
        default_factory=list, description="Code examples"
    )
    metadata: Dict[str, Any] = Field(
        default_factory=dict, description="Section metadata"
    )


class GeneratedDocumentation(BaseModel):
    """Generated documentation output."""

    title: str = Field(description="Document title")
    description: str = Field(description="Document description")
    doc_type: DocumentationType = Field(description="Type of documentation")
    format: DocumentationFormat = Field(description="Output format")
    sections: List[DocumentationSection] = Field(description="Document sections")
    generated_at: datetime = Field(
        default_factory=datetime.now, description="Generation timestamp"
    )
    metadata: Dict[str, Any] = Field(
        default_factory=dict, description="Document metadata"
    )

    class Config:
        json_encoders = {datetime: lambda v: v.isoformat()}


class OpenAPIEnhancement(BaseModel):
    """OpenAPI specification enhancement."""

    endpoint: str = Field(description="API endpoint path")
    method: str = Field(description="HTTP method")
    enhanced_description: str = Field(description="Enhanced endpoint description")
    examples: List[Dict[str, Any]] = Field(description="Request/response examples")
    workflow_context: str = Field(description="Workflow context for the endpoint")
    error_scenarios: List[Dict[str, str]] = Field(description="Common error scenarios")


class DocGenerator:
    """
    Documentation generator using Anthropic for intelligent content creation.

    This class provides methods to generate comprehensive documentation
    for the Azure File Share integration, including API references,
    workflow guides, and enhanced OpenAPI specifications.
    """

    def __init__(self, logger: Optional[logging.Logger] = None):
        """Initialize the documentation generator."""
        self.logger = logger or logging.getLogger(__name__)
        self._templates = self._load_templates()

    def generate_documentation(
        self, request: DocumentationRequest
    ) -> GeneratedDocumentation:
        """
        Generate documentation based on the request.

        Args:
            request: Documentation generation request

        Returns:
            Generated documentation
        """
        self.logger.info(
            f"Generating {request.doc_type} documentation: {request.title}"
        )

        try:
            # Generate content based on documentation type
            if request.doc_type == DocumentationType.API_REFERENCE:
                return self._generate_api_reference(request)
            elif request.doc_type == DocumentationType.WORKFLOW_GUIDE:
                return self._generate_workflow_guide(request)
            elif request.doc_type == DocumentationType.INTEGRATION_GUIDE:
                return self._generate_integration_guide(request)
            elif request.doc_type == DocumentationType.TROUBLESHOOTING:
                return self._generate_troubleshooting_guide(request)
            elif request.doc_type == DocumentationType.EXAMPLES:
                return self._generate_examples(request)
            elif request.doc_type == DocumentationType.OPENAPI_ENHANCEMENT:
                return self._generate_openapi_enhancement(request)
            else:
                raise ValueError(f"Unsupported documentation type: {request.doc_type}")

        except Exception as e:
            self.logger.error(f"Failed to generate documentation: {str(e)}")
            raise

    def _generate_api_reference(
        self, request: DocumentationRequest
    ) -> GeneratedDocumentation:
        """Generate API reference documentation."""

        sections = [
            DocumentationSection(
                title="Overview",
                content=self._generate_api_overview(),
                metadata={"section_type": "overview"},
            ),
            DocumentationSection(
                title="Authentication",
                content=self._generate_authentication_docs(),
                code_examples=[
                    {
                        "title": "JWT Token Usage",
                        "language": "python",
                        "code": self._get_auth_example(),
                    }
                ],
            ),
            DocumentationSection(
                title="Project Management Endpoints",
                content=self._generate_project_endpoints_docs(),
                subsections=self._generate_project_endpoint_sections(),
            ),
            DocumentationSection(
                title="File Management Endpoints",
                content=self._generate_file_endpoints_docs(),
                subsections=self._generate_file_endpoint_sections(),
            ),
            DocumentationSection(
                title="Code Generation Integration",
                content=self._generate_code_generation_docs(),
                code_examples=[
                    {
                        "title": "Generate with Project Integration",
                        "language": "python",
                        "code": self._get_generate_example(),
                    }
                ],
            ),
            DocumentationSection(
                title="Error Handling",
                content=self._generate_error_handling_docs(),
                code_examples=[
                    {
                        "title": "Error Response Format",
                        "language": "json",
                        "code": self._get_error_example(),
                    }
                ],
            ),
        ]

        return GeneratedDocumentation(
            title=request.title,
            description=request.description
            or "Comprehensive API reference for Azure File Share integration",
            doc_type=request.doc_type,
            format=request.format,
            sections=sections,
            metadata={
                "api_version": "v1",
                "base_url": "/api/v1",
                "generated_for": request.target_audience,
            },
        )

    def _generate_workflow_guide(
        self, request: DocumentationRequest
    ) -> GeneratedDocumentation:
        """Generate workflow guide documentation."""

        sections = [
            DocumentationSection(
                title="Introduction",
                content=self._generate_workflow_introduction(),
                metadata={"section_type": "introduction"},
            ),
            DocumentationSection(
                title="Basic Code Generation Workflow",
                content=self._generate_basic_workflow(),
                code_examples=[
                    {
                        "title": "Simple Code Generation",
                        "language": "curl",
                        "code": self._get_basic_workflow_example(),
                    }
                ],
            ),
            DocumentationSection(
                title="Project-Based Workflow",
                content=self._generate_project_workflow(),
                subsections=[
                    DocumentationSection(
                        title="Creating a New Project",
                        content=self._generate_project_creation_workflow(),
                        code_examples=[
                            {
                                "title": "Create Project via Generate Endpoint",
                                "language": "python",
                                "code": self._get_project_creation_example(),
                            }
                        ],
                    ),
                    DocumentationSection(
                        title="Working with Existing Projects",
                        content=self._generate_existing_project_workflow(),
                        code_examples=[
                            {
                                "title": "Generate Code for Existing Project",
                                "language": "python",
                                "code": self._get_existing_project_example(),
                            }
                        ],
                    ),
                ],
            ),
            DocumentationSection(
                title="File Management Workflow",
                content=self._generate_file_management_workflow(),
                subsections=[
                    DocumentationSection(
                        title="Browsing Project Files",
                        content=self._generate_file_browsing_workflow(),
                        code_examples=[
                            {
                                "title": "List Project Files",
                                "language": "python",
                                "code": self._get_file_listing_example(),
                            }
                        ],
                    ),
                    DocumentationSection(
                        title="Downloading Files",
                        content=self._generate_file_download_workflow(),
                        code_examples=[
                            {
                                "title": "Download Project File",
                                "language": "python",
                                "code": self._get_file_download_example(),
                            }
                        ],
                    ),
                ],
            ),
            DocumentationSection(
                title="Advanced Workflows",
                content=self._generate_advanced_workflows(),
                subsections=[
                    DocumentationSection(
                        title="Batch Operations",
                        content=self._generate_batch_workflow(),
                        code_examples=[
                            {
                                "title": "Multiple Generations",
                                "language": "python",
                                "code": self._get_batch_example(),
                            }
                        ],
                    ),
                    DocumentationSection(
                        title="Integration with CI/CD",
                        content=self._generate_cicd_workflow(),
                        code_examples=[
                            {
                                "title": "GitHub Actions Integration",
                                "language": "yaml",
                                "code": self._get_cicd_example(),
                            }
                        ],
                    ),
                ],
            ),
        ]

        return GeneratedDocumentation(
            title=request.title,
            description=request.description
            or "Complete workflow guide for Azure File Share integration",
            doc_type=request.doc_type,
            format=request.format,
            sections=sections,
            metadata={
                "workflow_complexity": "beginner_to_advanced",
                "estimated_time": "30_minutes",
                "prerequisites": ["API access", "Authentication token"],
            },
        )

    def _generate_integration_guide(
        self, request: DocumentationRequest
    ) -> GeneratedDocumentation:
        """Generate integration guide documentation."""

        sections = [
            DocumentationSection(
                title="Getting Started",
                content=self._generate_integration_overview(),
                code_examples=[
                    {
                        "title": "Environment Setup",
                        "language": "bash",
                        "code": self._get_environment_setup_example(),
                    }
                ],
            ),
            DocumentationSection(
                title="Azure Configuration",
                content=self._generate_azure_config_guide(),
                subsections=[
                    DocumentationSection(
                        title="Connection String Setup",
                        content=self._generate_connection_string_guide(),
                        code_examples=[
                            {
                                "title": "Environment Variables",
                                "language": "bash",
                                "code": self._get_azure_env_example(),
                            }
                        ],
                    ),
                    DocumentationSection(
                        title="File Share Configuration",
                        content=self._generate_file_share_config_guide(),
                        code_examples=[
                            {
                                "title": "Configuration Validation",
                                "language": "python",
                                "code": self._get_config_validation_example(),
                            }
                        ],
                    ),
                ],
            ),
            DocumentationSection(
                title="Client Integration",
                content=self._generate_client_integration_guide(),
                subsections=[
                    DocumentationSection(
                        title="Python Client",
                        content=self._generate_python_client_guide(),
                        code_examples=[
                            {
                                "title": "Python SDK Usage",
                                "language": "python",
                                "code": self._get_python_client_example(),
                            }
                        ],
                    ),
                    DocumentationSection(
                        title="JavaScript Client",
                        content=self._generate_js_client_guide(),
                        code_examples=[
                            {
                                "title": "JavaScript SDK Usage",
                                "language": "javascript",
                                "code": self._get_js_client_example(),
                            }
                        ],
                    ),
                ],
            ),
            DocumentationSection(
                title="Best Practices",
                content=self._generate_best_practices_guide(),
                subsections=[
                    DocumentationSection(
                        title="Error Handling",
                        content=self._generate_error_handling_best_practices(),
                    ),
                    DocumentationSection(
                        title="Performance Optimization",
                        content=self._generate_performance_best_practices(),
                    ),
                    DocumentationSection(
                        title="Security Considerations",
                        content=self._generate_security_best_practices(),
                    ),
                ],
            ),
        ]

        return GeneratedDocumentation(
            title=request.title,
            description=request.description
            or "Integration guide for Azure File Share with code generation",
            doc_type=request.doc_type,
            format=request.format,
            sections=sections,
            metadata={
                "integration_type": "azure_file_share",
                "supported_languages": ["python", "javascript", "curl"],
                "difficulty": "intermediate",
            },
        )

    def _generate_troubleshooting_guide(
        self, request: DocumentationRequest
    ) -> GeneratedDocumentation:
        """Generate troubleshooting guide documentation."""

        sections = [
            DocumentationSection(
                title="Common Issues",
                content=self._generate_common_issues_guide(),
                subsections=[
                    DocumentationSection(
                        title="Connection Issues",
                        content=self._generate_connection_troubleshooting(),
                        code_examples=[
                            {
                                "title": "Connection Test",
                                "language": "python",
                                "code": self._get_connection_test_example(),
                            }
                        ],
                    ),
                    DocumentationSection(
                        title="Authentication Problems",
                        content=self._generate_auth_troubleshooting(),
                        code_examples=[
                            {
                                "title": "Token Validation",
                                "language": "python",
                                "code": self._get_token_validation_example(),
                            }
                        ],
                    ),
                    DocumentationSection(
                        title="File Operation Errors",
                        content=self._generate_file_operation_troubleshooting(),
                        code_examples=[
                            {
                                "title": "File Upload Debug",
                                "language": "python",
                                "code": self._get_file_debug_example(),
                            }
                        ],
                    ),
                ],
            ),
            DocumentationSection(
                title="Error Codes Reference",
                content=self._generate_error_codes_reference(),
                metadata={"section_type": "reference"},
            ),
            DocumentationSection(
                title="Diagnostic Tools",
                content=self._generate_diagnostic_tools_guide(),
                code_examples=[
                    {
                        "title": "Health Check Script",
                        "language": "python",
                        "code": self._get_health_check_example(),
                    }
                ],
            ),
            DocumentationSection(
                title="Performance Issues",
                content=self._generate_performance_troubleshooting(),
                subsections=[
                    DocumentationSection(
                        title="Slow Upload/Download",
                        content=self._generate_performance_issues_guide(),
                    ),
                    DocumentationSection(
                        title="Timeout Problems",
                        content=self._generate_timeout_troubleshooting(),
                    ),
                ],
            ),
        ]

        return GeneratedDocumentation(
            title=request.title,
            description=request.description
            or "Troubleshooting guide for Azure File Share integration",
            doc_type=request.doc_type,
            format=request.format,
            sections=sections,
            metadata={
                "troubleshooting_scope": "azure_file_share_integration",
                "support_level": "self_service",
                "escalation_path": "github_issues",
            },
        )

    def _generate_examples(
        self, request: DocumentationRequest
    ) -> GeneratedDocumentation:
        """Generate examples documentation."""

        sections = [
            DocumentationSection(
                title="Basic Examples",
                content=self._generate_basic_examples_intro(),
                subsections=[
                    DocumentationSection(
                        title="Simple Code Generation",
                        content="Generate Terraform code without project management:",
                        code_examples=[
                            {
                                "title": "Basic Generation Request",
                                "language": "python",
                                "code": self._get_basic_generation_example(),
                            },
                            {
                                "title": "cURL Example",
                                "language": "bash",
                                "code": self._get_basic_curl_example(),
                            },
                        ],
                    ),
                    DocumentationSection(
                        title="Project Creation",
                        content="Create a new project and generate code:",
                        code_examples=[
                            {
                                "title": "Create Project with Generation",
                                "language": "python",
                                "code": self._get_project_creation_full_example(),
                            }
                        ],
                    ),
                ],
            ),
            DocumentationSection(
                title="Advanced Examples",
                content=self._generate_advanced_examples_intro(),
                subsections=[
                    DocumentationSection(
                        title="Multi-Generation Workflow",
                        content="Generate multiple resources for the same project:",
                        code_examples=[
                            {
                                "title": "Sequential Generations",
                                "language": "python",
                                "code": self._get_multi_generation_example(),
                            }
                        ],
                    ),
                    DocumentationSection(
                        title="File Management",
                        content="Browse and download generated files:",
                        code_examples=[
                            {
                                "title": "Complete File Management",
                                "language": "python",
                                "code": self._get_file_management_example(),
                            }
                        ],
                    ),
                ],
            ),
            DocumentationSection(
                title="Integration Examples",
                content=self._generate_integration_examples_intro(),
                subsections=[
                    DocumentationSection(
                        title="CI/CD Pipeline",
                        content="Integrate with continuous deployment:",
                        code_examples=[
                            {
                                "title": "GitHub Actions Workflow",
                                "language": "yaml",
                                "code": self._get_github_actions_example(),
                            }
                        ],
                    ),
                    DocumentationSection(
                        title="Terraform Automation",
                        content="Automate Terraform deployment:",
                        code_examples=[
                            {
                                "title": "Terraform Deployment Script",
                                "language": "bash",
                                "code": self._get_terraform_automation_example(),
                            }
                        ],
                    ),
                ],
            ),
        ]

        return GeneratedDocumentation(
            title=request.title,
            description=request.description
            or "Comprehensive examples for Azure File Share integration",
            doc_type=request.doc_type,
            format=request.format,
            sections=sections,
            metadata={
                "example_count": sum(
                    len(section.code_examples)
                    + sum(len(sub.code_examples) for sub in section.subsections)
                    for section in sections
                ),
                "languages": ["python", "bash", "yaml", "json"],
                "complexity_levels": ["basic", "intermediate", "advanced"],
            },
        )

    def _generate_openapi_enhancement(
        self, request: DocumentationRequest
    ) -> GeneratedDocumentation:
        """Generate OpenAPI specification enhancements."""

        enhancements = []

        # Generate enhancements for each endpoint
        if request.api_endpoints:
            for endpoint in request.api_endpoints:
                enhancement = self._create_endpoint_enhancement(endpoint)
                enhancements.append(enhancement)

        sections = [
            DocumentationSection(
                title="Enhanced API Specification",
                content=self._generate_openapi_overview(),
                metadata={"enhancements": enhancements},
            ),
            DocumentationSection(
                title="Endpoint Enhancements",
                content=self._generate_endpoint_enhancements_summary(),
                subsections=self._generate_endpoint_enhancement_sections(enhancements),
            ),
            DocumentationSection(
                title="Workflow Integration",
                content=self._generate_workflow_integration_docs(),
                code_examples=[
                    {
                        "title": "OpenAPI Client Generation",
                        "language": "bash",
                        "code": self._get_openapi_client_example(),
                    }
                ],
            ),
        ]

        return GeneratedDocumentation(
            title=request.title,
            description=request.description
            or "Enhanced OpenAPI specification with examples and workflows",
            doc_type=request.doc_type,
            format=request.format,
            sections=sections,
            metadata={
                "openapi_version": "3.0.3",
                "enhanced_endpoints": len(enhancements),
                "enhancement_types": [
                    "descriptions",
                    "examples",
                    "workflows",
                    "error_scenarios",
                ],
            },
        )

    def export_documentation(
        self, doc: GeneratedDocumentation, output_path: str
    ) -> str:
        """
        Export generated documentation to file.

        Args:
            doc: Generated documentation
            output_path: Output file path

        Returns:
            Path to exported file
        """
        output_file = Path(output_path)
        output_file.parent.mkdir(parents=True, exist_ok=True)

        if doc.format == DocumentationFormat.MARKDOWN:
            content = self._export_to_markdown(doc)
        elif doc.format == DocumentationFormat.HTML:
            content = self._export_to_html(doc)
        elif doc.format == DocumentationFormat.JSON:
            content = self._export_to_json(doc)
        elif doc.format == DocumentationFormat.YAML:
            content = self._export_to_yaml(doc)
        else:
            raise ValueError(f"Unsupported export format: {doc.format}")

        with open(output_file, "w", encoding="utf-8") as f:
            f.write(content)

        self.logger.info(f"Documentation exported to: {output_file}")
        return str(output_file)

    def _load_templates(self) -> Dict[str, str]:
        """Load documentation templates."""
        # In a real implementation, these would be loaded from template files
        return {
            "api_overview": "This API provides comprehensive project management and file storage capabilities...",
            "workflow_intro": "The Azure File Share integration enables seamless code generation workflows...",
            "troubleshooting_intro": "This guide helps resolve common issues with the Azure File Share integration...",
        }

    # Content generation methods (these would use Anthropic API in a real implementation)
    def _generate_api_overview(self) -> str:
        """Generate API overview content."""
        return """
The Azure File Share Integration API provides comprehensive project management and file storage capabilities for generated Terraform code. This API seamlessly integrates with the existing code generation system to provide persistent, organized storage for your infrastructure code.

## Key Features

- **Automatic Project Management**: Projects are created automatically when generating code
- **Persistent File Storage**: All generated code is stored in Azure File Share
- **Backward Compatibility**: Existing code generation workflows continue to work unchanged
- **File Organization**: Generated files are organized by project and generation hash
- **Secure Access**: All operations are authenticated and authorized per user

## Base URL

All API endpoints are available under the base URL: `/api/v1`

## Authentication

All requests require a valid JWT token in the Authorization header:
```
Authorization: Bearer <your-jwt-token>
```
"""

    def _generate_authentication_docs(self) -> str:
        """Generate authentication documentation."""
        return """
The API uses JWT (JSON Web Token) based authentication. You must include a valid JWT token in the Authorization header of all requests.

## Obtaining a Token

Tokens are obtained through the authentication endpoint:

```http
POST /api/v1/auth/login
Content-Type: application/json

{
  "email": "user@example.com",
  "password": "your-password"
}
```

## Token Usage

Include the token in the Authorization header:

```http
Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...
```

## Token Expiration

Tokens expire after 30 minutes. Use the refresh token to obtain a new access token without re-authenticating.
"""

    def _get_auth_example(self) -> str:
        """Get authentication code example."""
        return """
import requests

# Login to get token
login_response = requests.post(
    "http://localhost:8000/api/v1/auth/login",
    json={
        "email": "user@example.com",
        "password": "password"
    }
)

token = login_response.json()["access_token"]

# Use token in subsequent requests
headers = {"Authorization": f"Bearer {token}"}

response = requests.get(
    "http://localhost:8000/api/v1/projects",
    headers=headers
)
"""

    def _generate_project_endpoints_docs(self) -> str:
        """Generate project endpoints documentation."""
        return """
Project management endpoints allow you to view and manage projects created through the code generation process. Projects are automatically created when you generate code with a `project_name` parameter.

## Available Endpoints

- `GET /projects` - List all projects for the authenticated user
- `GET /projects/{project_id}` - Get details for a specific project
- `GET /projects/{project_id}/files` - List files in a project
- `GET /projects/{project_id}/files/{file_path}` - Download a specific file

All project operations are scoped to the authenticated user - you can only access your own projects.
"""

    def _generate_project_endpoint_sections(self) -> List[DocumentationSection]:
        """Generate project endpoint subsections."""
        return [
            DocumentationSection(
                title="List Projects",
                content="Retrieve all projects for the authenticated user.",
                code_examples=[
                    {
                        "title": "List Projects Request",
                        "language": "python",
                        "code": """
import requests

response = requests.get(
    "http://localhost:8000/api/v1/projects",
    headers={"Authorization": f"Bearer {token}"}
)

projects = response.json()
for project in projects:
    print(f"Project: {project['name']} ({project['id']})")
""",
                    }
                ],
            ),
            DocumentationSection(
                title="Get Project Details",
                content="Retrieve detailed information about a specific project.",
                code_examples=[
                    {
                        "title": "Get Project Details",
                        "language": "python",
                        "code": """
project_id = "your-project-id"
response = requests.get(
    f"http://localhost:8000/api/v1/projects/{project_id}",
    headers={"Authorization": f"Bearer {token}"}
)

project = response.json()
print(f"Project: {project['name']}")
print(f"Files: {project['file_count']}")
print(f"Size: {project['total_size_bytes']} bytes")
""",
                    }
                ],
            ),
        ]

    def _generate_file_endpoints_docs(self) -> str:
        """Generate file endpoints documentation."""
        return """
File management endpoints provide access to the generated Terraform files stored in Azure File Share. These endpoints allow you to browse, download, and analyze your generated code.

## File Organization

Files are organized in the following structure:
- `/projects/{project_id}/{generation_hash}/` - Generated files for a specific generation
- Each generation has a unique hash based on the generation parameters
- Files maintain their original structure (main.tf, variables.tf, etc.)

## File Access

All file operations require project access permissions. You can only access files in projects you own.
"""

    def _generate_file_endpoint_sections(self) -> List[DocumentationSection]:
        """Generate file endpoint subsections."""
        return [
            DocumentationSection(
                title="List Project Files",
                content="Get a list of all files in a project across all generations.",
                code_examples=[
                    {
                        "title": "List Files Request",
                        "language": "python",
                        "code": """
project_id = "your-project-id"
response = requests.get(
    f"http://localhost:8000/api/v1/projects/{project_id}/files",
    headers={"Authorization": f"Bearer {token}"}
)

files = response.json()
for file in files:
    print(f"File: {file['file_path']} ({file['size_bytes']} bytes)")
""",
                    }
                ],
            ),
            DocumentationSection(
                title="Download File",
                content="Download the content of a specific file.",
                code_examples=[
                    {
                        "title": "Download File",
                        "language": "python",
                        "code": """
project_id = "your-project-id"
file_path = "main.tf"

response = requests.get(
    f"http://localhost:8000/api/v1/projects/{project_id}/files/{file_path}",
    headers={"Authorization": f"Bearer {token}"}
)

if response.status_code == 200:
    with open(file_path, 'w') as f:
        f.write(response.text)
    print(f"Downloaded {file_path}")
""",
                    }
                ],
            ),
        ]

    def _generate_code_generation_docs(self) -> str:
        """Generate code generation integration documentation."""
        return """
The enhanced `/generate` endpoint now supports automatic project integration. You can create projects and store generated code seamlessly without any additional API calls.

## Project Integration

- Add `project_name` to create a new project automatically
- Add `project_id` to generate code for an existing project
- Omit both to use the traditional generation without project storage

## Backward Compatibility

Existing code generation requests continue to work unchanged. Project integration is entirely optional and additive.
"""

    def _get_generate_example(self) -> str:
        """Get code generation example."""
        return """
import requests

# Generate code with automatic project creation
response = requests.post(
    "http://localhost:8000/api/v1/generate",
    headers={"Authorization": f"Bearer {token}"},
    json={
        "query": "Create an AWS VPC with public and private subnets",
        "scenario": "new_resource",
        "project_name": "my-vpc-project"  # Creates project automatically
    }
)

result = response.json()
print(f"Job ID: {result['job_id']}")
print(f"Project ID: {result['project_id']}")

# Check job status
job_response = requests.get(
    f"http://localhost:8000/api/v1/jobs/{result['job_id']}/result",
    headers={"Authorization": f"Bearer {token}"}
)

if job_response.json()["status"] == "completed":
    print("Code generated and saved to Azure File Share!")
    print(f"Files: {job_response.json()['azure_paths']}")
"""

    def _generate_error_handling_docs(self) -> str:
        """Generate error handling documentation."""
        return """
The API uses standard HTTP status codes and provides detailed error information in JSON format.

## Error Response Format

All errors follow a consistent format:

```json
{
  "detail": "Error description",
  "error_code": "SPECIFIC_ERROR_CODE",
  "timestamp": "2024-01-01T12:00:00Z"
}
```

## Common Status Codes

- `400 Bad Request` - Invalid request parameters
- `401 Unauthorized` - Missing or invalid authentication token
- `403 Forbidden` - Insufficient permissions
- `404 Not Found` - Resource not found
- `422 Unprocessable Entity` - Validation errors
- `500 Internal Server Error` - Server-side errors
"""

    def _get_error_example(self) -> str:
        """Get error response example."""
        return """
{
  "detail": "Project not found or access denied",
  "error_code": "PROJECT_NOT_FOUND",
  "timestamp": "2024-01-01T12:00:00Z",
  "request_id": "req_123456789"
}
"""

    # Additional content generation methods would continue here...
    # For brevity, I'm including key methods but the pattern continues

    def _generate_workflow_introduction(self) -> str:
        """Generate workflow introduction."""
        return """
This guide walks you through the complete workflows available with the Azure File Share integration. Whether you're generating code for the first time or managing complex multi-resource projects, these workflows will help you get the most out of the system.

## Workflow Types

1. **Basic Code Generation** - Simple, one-off code generation
2. **Project-Based Workflow** - Organized, persistent project management
3. **File Management** - Browsing and downloading generated files
4. **Advanced Workflows** - Batch operations and CI/CD integration

Each workflow is designed to be intuitive and builds upon the previous concepts.
"""

    def _get_basic_workflow_example(self) -> str:
        """Get basic workflow example."""
        return """
# Simple code generation without project management
curl -X POST "http://localhost:8000/api/v1/generate" \\
  -H "Authorization: Bearer $TOKEN" \\
  -H "Content-Type: application/json" \\
  -d '{
    "query": "Create an S3 bucket with versioning enabled",
    "scenario": "new_resource"
  }'
"""

    def _export_to_markdown(self, doc: GeneratedDocumentation) -> str:
        """Export documentation to Markdown format."""
        lines = []

        # Title and description
        lines.append(f"# {doc.title}")
        lines.append("")
        if doc.description:
            lines.append(doc.description)
            lines.append("")

        # Metadata
        lines.append(
            f"*Generated on: {doc.generated_at.strftime('%Y-%m-%d %H:%M:%S')}*"
        )
        lines.append("")

        # Sections
        for section in doc.sections:
            lines.extend(self._section_to_markdown(section, level=2))

        return "\n".join(lines)

    def _section_to_markdown(
        self, section: DocumentationSection, level: int = 2
    ) -> List[str]:
        """Convert a section to Markdown format."""
        lines = []

        # Section title
        lines.append(f"{'#' * level} {section.title}")
        lines.append("")

        # Section content
        if section.content:
            lines.append(section.content)
            lines.append("")

        # Code examples
        for example in section.code_examples:
            lines.append(f"### {example['title']}")
            lines.append("")
            lines.append(f"```{example.get('language', '')}")
            lines.append(example["code"])
            lines.append("```")
            lines.append("")

        # Subsections
        for subsection in section.subsections:
            lines.extend(self._section_to_markdown(subsection, level + 1))

        return lines

    def _export_to_json(self, doc: GeneratedDocumentation) -> str:
        """Export documentation to JSON format."""
        return doc.model_dump_json(indent=2)

    def _export_to_yaml(self, doc: GeneratedDocumentation) -> str:
        """Export documentation to YAML format."""
        return yaml.dump(doc.model_dump(), default_flow_style=False, sort_keys=False)

    def _export_to_html(self, doc: GeneratedDocumentation) -> str:
        """Export documentation to HTML format."""
        # Basic HTML template - in a real implementation, this would use a proper template engine
        html_content = f"""
<!DOCTYPE html>
<html>
<head>
    <title>{doc.title}</title>
    <style>
        body {{ font-family: Arial, sans-serif; margin: 40px; }}
        h1, h2, h3 {{ color: #333; }}
        pre {{ background: #f4f4f4; padding: 10px; border-radius: 5px; }}
        code {{ background: #f4f4f4; padding: 2px 4px; border-radius: 3px; }}
    </style>
</head>
<body>
    <h1>{doc.title}</h1>
    <p><em>Generated on: {doc.generated_at.strftime('%Y-%m-%d %H:%M:%S')}</em></p>
    {self._sections_to_html(doc.sections)}
</body>
</html>
"""
        return html_content

    def _sections_to_html(self, sections: List[DocumentationSection]) -> str:
        """Convert sections to HTML."""
        html_parts = []
        for section in sections:
            html_parts.append(f"<h2>{section.title}</h2>")
            if section.content:
                html_parts.append(f"<p>{section.content}</p>")

            for example in section.code_examples:
                html_parts.append(f"<h3>{example['title']}</h3>")
                html_parts.append(f"<pre><code>{example['code']}</code></pre>")

            if section.subsections:
                html_parts.append(self._sections_to_html(section.subsections))

        return "\n".join(html_parts)

    # Placeholder methods for additional content generation
    # In a real implementation, these would use Anthropic API to generate intelligent content

    def _create_endpoint_enhancement(self, endpoint: str) -> OpenAPIEnhancement:
        """Create enhancement for an API endpoint."""
        return OpenAPIEnhancement(
            endpoint=endpoint,
            method="GET",
            enhanced_description=f"Enhanced description for {endpoint}",
            examples=[{"request": {}, "response": {}}],
            workflow_context=f"This endpoint is used in the context of {endpoint}",
            error_scenarios=[{"error": "404", "description": "Resource not found"}],
        )

    def _generate_openapi_overview(self) -> str:
        return "Enhanced OpenAPI specification with comprehensive examples and workflow integration."

    def _generate_endpoint_enhancements_summary(self) -> str:
        return (
            "Summary of endpoint enhancements including examples and error scenarios."
        )

    def _generate_endpoint_enhancement_sections(
        self, enhancements: List[OpenAPIEnhancement]
    ) -> List[DocumentationSection]:
        return [
            DocumentationSection(
                title=f"Enhanced {enhancement.endpoint}",
                content=enhancement.enhanced_description,
            )
            for enhancement in enhancements
        ]

    def _generate_workflow_integration_docs(self) -> str:
        return "Documentation on how to integrate the enhanced OpenAPI specification with workflows."

    def _get_openapi_client_example(self) -> str:
        return "# Generate client from OpenAPI spec\nopenapi-generator generate -i api-spec.yaml -g python -o client/"

    # Additional placeholder methods would continue here...
    # Each method would generate appropriate content for its section

    def _generate_basic_examples_intro(self) -> str:
        return (
            "Basic examples to get you started with the Azure File Share integration."
        )

    def _get_basic_generation_example(self) -> str:
        return """
import requests

response = requests.post(
    "http://localhost:8000/api/v1/generate",
    headers={"Authorization": f"Bearer {token}"},
    json={
        "query": "Create an AWS S3 bucket",
        "scenario": "new_resource"
    }
)
"""

    def _get_basic_curl_example(self) -> str:
        return """
curl -X POST "http://localhost:8000/api/v1/generate" \\
  -H "Authorization: Bearer $TOKEN" \\
  -H "Content-Type: application/json" \\
  -d '{"query": "Create an AWS S3 bucket", "scenario": "new_resource"}'
"""

    def _get_basic_curl_example(self) -> str:
        return """
curl -X POST "http://localhost:8000/api/v1/generate" \\
  -H "Authorization: Bearer $TOKEN" \\
  -H "Content-Type: application/json" \\
  -d '{"query": "Create an AWS S3 bucket", "scenario": "new_resource"}'
"""

    # Workflow guide methods
    def _generate_basic_workflow(self) -> str:
        return "Basic workflow for code generation without project management."

    def _generate_project_workflow(self) -> str:
        return "Project-based workflow for organized code generation."

    def _generate_project_creation_workflow(self) -> str:
        return "Steps to create a new project during code generation."

    def _get_project_creation_example(self) -> str:
        return """
import requests

response = requests.post(
    "http://localhost:8000/api/v1/generate",
    headers={"Authorization": f"Bearer {token}"},
    json={
        "query": "Create an AWS VPC",
        "scenario": "new_resource",
        "project_name": "my-vpc-project"
    }
)
"""

    def _generate_existing_project_workflow(self) -> str:
        return "Steps to generate code for an existing project."

    def _get_existing_project_example(self) -> str:
        return """
import requests

response = requests.post(
    "http://localhost:8000/api/v1/generate",
    headers={"Authorization": f"Bearer {token}"},
    json={
        "query": "Add S3 bucket to existing VPC",
        "scenario": "modify_existing",
        "project_id": "existing-project-id"
    }
)
"""

    def _generate_file_management_workflow(self) -> str:
        return "Workflow for managing generated files."

    def _generate_file_browsing_workflow(self) -> str:
        return "Steps to browse project files."

    def _get_file_listing_example(self) -> str:
        return """
import requests

response = requests.get(
    f"http://localhost:8000/api/v1/projects/{project_id}/files",
    headers={"Authorization": f"Bearer {token}"}
)

files = response.json()
for file in files:
    print(f"File: {file['file_path']}")
"""

    def _generate_file_download_workflow(self) -> str:
        return "Steps to download project files."

    def _get_file_download_example(self) -> str:
        return """
import requests

response = requests.get(
    f"http://localhost:8000/api/v1/projects/{project_id}/files/main.tf",
    headers={"Authorization": f"Bearer {token}"}
)

with open("main.tf", "w") as f:
    f.write(response.text)
"""

    def _generate_advanced_workflows(self) -> str:
        return "Advanced workflows for complex scenarios."

    def _generate_batch_workflow(self) -> str:
        return "Batch operations for multiple generations."

    def _get_batch_example(self) -> str:
        return """
import requests

# Generate multiple resources for the same project
resources = ["VPC", "S3 bucket", "RDS instance"]

for resource in resources:
    response = requests.post(
        "http://localhost:8000/api/v1/generate",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "query": f"Create an AWS {resource}",
            "scenario": "new_resource",
            "project_id": project_id
        }
    )
"""

    def _generate_cicd_workflow(self) -> str:
        return "CI/CD integration workflow."

    def _get_cicd_example(self) -> str:
        return """
name: Generate Infrastructure Code
on:
  push:
    branches: [main]

jobs:
  generate:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v2
      - name: Generate Terraform
        run: |
          curl -X POST "${{ secrets.API_URL }}/api/v1/generate" \\
            -H "Authorization: Bearer ${{ secrets.API_TOKEN }}" \\
            -H "Content-Type: application/json" \\
            -d '{"query": "Create infrastructure", "project_id": "${{ secrets.PROJECT_ID }}"}'
"""

    # Integration guide methods
    def _generate_integration_overview(self) -> str:
        return "Overview of Azure File Share integration setup and configuration."

    def _get_environment_setup_example(self) -> str:
        return """
# Install dependencies
pip install requests python-dotenv

# Set up environment variables
export AZURE_STORAGE_CONNECTION_STRING="your_connection_string"
export AZURE_FILE_SHARE_NAME="infrajet-projects"
export API_BASE_URL="http://localhost:8000"
"""

    def _generate_azure_config_guide(self) -> str:
        return "Guide for configuring Azure File Share connection."

    def _generate_connection_string_guide(self) -> str:
        return "How to set up Azure Storage connection string."

    def _get_azure_env_example(self) -> str:
        return """
# Azure File Share Configuration
AZURE_STORAGE_CONNECTION_STRING=DefaultEndpointsProtocol=https;AccountName=myaccount;AccountKey=mykey;EndpointSuffix=core.windows.net
AZURE_FILE_SHARE_NAME=infrajet-projects
AZURE_BASE_DIRECTORY=projects
AZURE_ENABLED=true
"""

    def _generate_file_share_config_guide(self) -> str:
        return "Configuration guide for Azure File Share settings."

    def _get_config_validation_example(self) -> str:
        return """
from app.core.config.azure_validator import validate_azure_configuration

# Validate configuration
report = validate_azure_configuration()

if report.is_valid:
    print("Configuration is valid")
else:
    for error in report.errors:
        print(f"Error: {error.message}")
"""

    def _generate_client_integration_guide(self) -> str:
        return "Guide for integrating with different client types."

    def _generate_python_client_guide(self) -> str:
        return "Python client integration guide."

    def _get_python_client_example(self) -> str:
        return """
import requests
from typing import Dict, Any

class InfrajetClient:
    def __init__(self, base_url: str, token: str):
        self.base_url = base_url
        self.headers = {"Authorization": f"Bearer {token}"}
    
    def generate_code(self, query: str, project_name: str = None) -> Dict[str, Any]:
        response = requests.post(
            f"{self.base_url}/api/v1/generate",
            headers=self.headers,
            json={"query": query, "project_name": project_name}
        )
        return response.json()

# Usage
client = InfrajetClient("http://localhost:8000", "your-token")
result = client.generate_code("Create an S3 bucket", "my-project")
"""

    def _generate_js_client_guide(self) -> str:
        return "JavaScript client integration guide."

    def _get_js_client_example(self) -> str:
        return """
class InfrajetClient {
    constructor(baseUrl, token) {
        this.baseUrl = baseUrl;
        this.headers = {
            'Authorization': `Bearer ${token}`,
            'Content-Type': 'application/json'
        };
    }
    
    async generateCode(query, projectName = null) {
        const response = await fetch(`${this.baseUrl}/api/v1/generate`, {
            method: 'POST',
            headers: this.headers,
            body: JSON.stringify({
                query: query,
                project_name: projectName
            })
        });
        return response.json();
    }
}

// Usage
const client = new InfrajetClient('http://localhost:8000', 'your-token');
const result = await client.generateCode('Create an S3 bucket', 'my-project');
"""

    def _generate_best_practices_guide(self) -> str:
        return "Best practices for Azure File Share integration."

    def _generate_error_handling_best_practices(self) -> str:
        return "Best practices for error handling in Azure File Share operations."

    def _generate_performance_best_practices(self) -> str:
        return "Performance optimization best practices."

    def _generate_security_best_practices(self) -> str:
        return "Security considerations and best practices."

    # Troubleshooting guide methods
    def _generate_common_issues_guide(self) -> str:
        return "Common issues and their solutions."

    def _generate_connection_troubleshooting(self) -> str:
        return "Troubleshooting Azure File Share connection issues."

    def _get_connection_test_example(self) -> str:
        return """
from app.core.config.azure_validator import quick_validate_azure_config

# Test Azure connection
is_valid, message = quick_validate_azure_config()

if is_valid:
    print("Azure connection is working")
else:
    print(f"Connection issue: {message}")
"""

    def _generate_auth_troubleshooting(self) -> str:
        return "Troubleshooting authentication problems."

    def _get_token_validation_example(self) -> str:
        return """
import requests

# Test token validity
response = requests.get(
    "http://localhost:8000/api/v1/projects",
    headers={"Authorization": f"Bearer {token}"}
)

if response.status_code == 401:
    print("Token is invalid or expired")
elif response.status_code == 200:
    print("Token is valid")
"""

    def _generate_file_operation_troubleshooting(self) -> str:
        return "Troubleshooting file operation errors."

    def _get_file_debug_example(self) -> str:
        return """
import logging

# Enable debug logging
logging.basicConfig(level=logging.DEBUG)

# Test file operations with detailed logging
try:
    response = requests.post("/api/v1/generate", json=data)
    print(f"Response: {response.status_code}")
except Exception as e:
    print(f"Error: {e}")
"""

    def _generate_error_codes_reference(self) -> str:
        return "Reference guide for error codes and their meanings."

    def _generate_diagnostic_tools_guide(self) -> str:
        return "Diagnostic tools for troubleshooting."

    def _get_health_check_example(self) -> str:
        return """
import requests

def health_check():
    try:
        # Check API health
        api_response = requests.get("http://localhost:8000/health")
        print(f"API Status: {api_response.status_code}")
        
        # Check Azure connection
        from app.core.config.azure_validator import validate_azure_configuration
        report = validate_azure_configuration()
        print(f"Azure Config Valid: {report.is_valid}")
        
    except Exception as e:
        print(f"Health check failed: {e}")

health_check()
"""

    def _generate_performance_troubleshooting(self) -> str:
        return "Troubleshooting performance issues."

    def _generate_performance_issues_guide(self) -> str:
        return "Guide for resolving performance issues."

    def _generate_timeout_troubleshooting(self) -> str:
        return "Troubleshooting timeout problems."

    # Examples methods
    def _get_project_creation_full_example(self) -> str:
        return """
import requests

# Create project and generate code in one request
response = requests.post(
    "http://localhost:8000/api/v1/generate",
    headers={"Authorization": f"Bearer {token}"},
    json={
        "query": "Create a complete VPC with subnets and security groups",
        "scenario": "new_resource",
        "project_name": "vpc-infrastructure"
    }
)

result = response.json()
print(f"Project created: {result['project_id']}")
print(f"Job ID: {result['job_id']}")
"""

    def _generate_advanced_examples_intro(self) -> str:
        return "Advanced examples for complex scenarios."

    def _get_multi_generation_example(self) -> str:
        return """
import requests
import time

project_id = "your-project-id"
resources = [
    "Create an AWS VPC with CIDR 10.0.0.0/16",
    "Add public subnet to the VPC",
    "Add private subnet to the VPC",
    "Create internet gateway for the VPC"
]

for i, query in enumerate(resources):
    response = requests.post(
        "http://localhost:8000/api/v1/generate",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "query": query,
            "scenario": "modify_existing" if i > 0 else "new_resource",
            "project_id": project_id
        }
    )
    
    print(f"Generated: {query}")
    time.sleep(1)  # Rate limiting
"""

    def _get_file_management_example(self) -> str:
        return """
import requests

# List all files in project
files_response = requests.get(
    f"http://localhost:8000/api/v1/projects/{project_id}/files",
    headers={"Authorization": f"Bearer {token}"}
)

files = files_response.json()
print(f"Found {len(files)} files")

# Download each file
for file in files:
    file_response = requests.get(
        f"http://localhost:8000/api/v1/projects/{project_id}/files/{file['file_path']}",
        headers={"Authorization": f"Bearer {token}"}
    )
    
    with open(file['file_path'], 'w') as f:
        f.write(file_response.text)
    
    print(f"Downloaded: {file['file_path']}")
"""

    def _generate_integration_examples_intro(self) -> str:
        return "Integration examples for CI/CD and automation."

    def _get_github_actions_example(self) -> str:
        return """
name: Infrastructure Code Generation
on:
  workflow_dispatch:
    inputs:
      infrastructure_query:
        description: 'Infrastructure to generate'
        required: true
        default: 'Create an AWS VPC'

jobs:
  generate-infrastructure:
    runs-on: ubuntu-latest
    steps:
      - name: Generate Infrastructure Code
        run: |
          response=$(curl -s -X POST "${{ secrets.INFRAJET_API_URL }}/api/v1/generate" \\
            -H "Authorization: Bearer ${{ secrets.INFRAJET_TOKEN }}" \\
            -H "Content-Type: application/json" \\
            -d "{
              \\"query\\": \\"${{ github.event.inputs.infrastructure_query }}\\",
              \\"project_name\\": \\"github-actions-${{ github.run_number }}\\"
            }")
          
          echo "Generation response: $response"
"""

    def _get_terraform_automation_example(self) -> str:
        return """
#!/bin/bash

# Terraform automation script with Infrajet integration

set -e

PROJECT_NAME="automated-infrastructure"
INFRAJET_API_URL="http://localhost:8000"
TOKEN="your-api-token"

echo "Starting infrastructure generation..."

# Generate infrastructure code
response=$(curl -s -X POST "$INFRAJET_API_URL/api/v1/generate" \\
  -H "Authorization: Bearer $TOKEN" \\
  -H "Content-Type: application/json" \\
  -d "{
    \\"query\\": \\"Create a production-ready AWS VPC\\",
    \\"scenario\\": \\"new_resource\\",
    \\"project_name\\": \\"$PROJECT_NAME\\"
  }")

job_id=$(echo $response | jq -r '.job_id')
project_id=$(echo $response | jq -r '.project_id')

echo "Job ID: $job_id"
echo "Project ID: $project_id"
"""


# Convenience functions for common documentation tasks
def generate_api_documentation(
    title: str = "Azure File Share Integration API",
) -> GeneratedDocumentation:
    """Generate comprehensive API documentation."""
    generator = DocGenerator()
    request = DocumentationRequest(
        doc_type=DocumentationType.API_REFERENCE,
        title=title,
        description="Complete API reference for Azure File Share integration",
        include_examples=True,
        include_code_snippets=True,
    )
    return generator.generate_documentation(request)


def generate_workflow_guide(
    title: str = "Azure File Share Workflow Guide",
) -> GeneratedDocumentation:
    """Generate workflow guide documentation."""
    generator = DocGenerator()
    request = DocumentationRequest(
        doc_type=DocumentationType.WORKFLOW_GUIDE,
        title=title,
        description="Complete workflow guide for Azure File Share integration",
        include_examples=True,
        include_code_snippets=True,
    )
    return generator.generate_documentation(request)


def generate_integration_guide(
    title: str = "Azure File Share Integration Guide",
) -> GeneratedDocumentation:
    """Generate integration guide documentation."""
    generator = DocGenerator()
    request = DocumentationRequest(
        doc_type=DocumentationType.INTEGRATION_GUIDE,
        title=title,
        description="Complete integration guide for Azure File Share",
        include_examples=True,
        include_code_snippets=True,
    )
    return generator.generate_documentation(request)


def enhance_openapi_spec(
    endpoints: List[str], title: str = "Enhanced API Specification"
) -> GeneratedDocumentation:
    """Generate OpenAPI specification enhancements."""
    generator = DocGenerator()
    request = DocumentationRequest(
        doc_type=DocumentationType.OPENAPI_ENHANCEMENT,
        title=title,
        description="Enhanced OpenAPI specification with examples and workflows",
        api_endpoints=endpoints,
        include_examples=True,
        include_code_snippets=True,
    )
    return generator.generate_documentation(request)

    def _get_basic_curl_example(self) -> str:
        return """
curl -X POST "http://localhost:8000/api/v1/generate" \\
  -H "Authorization: Bearer $TOKEN" \\
  -H "Content-Type: application/json" \\
  -d '{"query": "Create an AWS S3 bucket", "scenario": "new_resource"}'
"""

    # Workflow guide methods
    def _generate_basic_workflow(self) -> str:
        return "Basic workflow for code generation without project management."

    def _generate_project_workflow(self) -> str:
        return "Project-based workflow for organized code generation."

    def _generate_project_creation_workflow(self) -> str:
        return "Steps to create a new project during code generation."

    def _get_project_creation_example(self) -> str:
        return """
import requests

response = requests.post(
    "http://localhost:8000/api/v1/generate",
    headers={"Authorization": f"Bearer {token}"},
    json={
        "query": "Create an AWS VPC",
        "scenario": "new_resource",
        "project_name": "my-vpc-project"
    }
)
"""

    def _generate_existing_project_workflow(self) -> str:
        return "Steps to generate code for an existing project."

    def _get_existing_project_example(self) -> str:
        return """
import requests

response = requests.post(
    "http://localhost:8000/api/v1/generate",
    headers={"Authorization": f"Bearer {token}"},
    json={
        "query": "Add S3 bucket to existing VPC",
        "scenario": "modify_existing",
        "project_id": "existing-project-id"
    }
)
"""

    def _generate_file_management_workflow(self) -> str:
        return "Workflow for managing generated files."

    def _generate_file_browsing_workflow(self) -> str:
        return "Steps to browse project files."

    def _get_file_listing_example(self) -> str:
        return """
import requests

response = requests.get(
    f"http://localhost:8000/api/v1/projects/{project_id}/files",
    headers={"Authorization": f"Bearer {token}"}
)

files = response.json()
for file in files:
    print(f"File: {file['file_path']}")
"""

    def _generate_file_download_workflow(self) -> str:
        return "Steps to download project files."

    def _get_file_download_example(self) -> str:
        return """
import requests

response = requests.get(
    f"http://localhost:8000/api/v1/projects/{project_id}/files/main.tf",
    headers={"Authorization": f"Bearer {token}"}
)

with open("main.tf", "w") as f:
    f.write(response.text)
"""

    def _generate_advanced_workflows(self) -> str:
        return "Advanced workflows for complex scenarios."

    def _generate_batch_workflow(self) -> str:
        return "Batch operations for multiple generations."

    def _get_batch_example(self) -> str:
        return """
import requests

# Generate multiple resources for the same project
resources = ["VPC", "S3 bucket", "RDS instance"]

for resource in resources:
    response = requests.post(
        "http://localhost:8000/api/v1/generate",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "query": f"Create an AWS {resource}",
            "scenario": "new_resource",
            "project_id": project_id
        }
    )
"""

    def _generate_cicd_workflow(self) -> str:
        return "CI/CD integration workflow."

    def _get_cicd_example(self) -> str:
        return """
name: Generate Infrastructure Code
on:
  push:
    branches: [main]

jobs:
  generate:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v2
      - name: Generate Terraform
        run: |
          curl -X POST "${{ secrets.API_URL }}/api/v1/generate" \\
            -H "Authorization: Bearer ${{ secrets.API_TOKEN }}" \\
            -H "Content-Type: application/json" \\
            -d '{"query": "Create infrastructure", "project_id": "${{ secrets.PROJECT_ID }}"}'
"""

    # Integration guide methods
    def _generate_integration_overview(self) -> str:
        return "Overview of Azure File Share integration setup and configuration."

    def _get_environment_setup_example(self) -> str:
        return """
# Install dependencies
pip install requests python-dotenv

# Set up environment variables
export AZURE_STORAGE_CONNECTION_STRING="your_connection_string"
export AZURE_FILE_SHARE_NAME="infrajet-projects"
export API_BASE_URL="http://localhost:8000"
"""

    def _generate_azure_config_guide(self) -> str:
        return "Guide for configuring Azure File Share connection."

    def _generate_connection_string_guide(self) -> str:
        return "How to set up Azure Storage connection string."

    def _get_azure_env_example(self) -> str:
        return """
# Azure File Share Configuration
AZURE_STORAGE_CONNECTION_STRING=DefaultEndpointsProtocol=https;AccountName=myaccount;AccountKey=mykey;EndpointSuffix=core.windows.net
AZURE_FILE_SHARE_NAME=infrajet-projects
AZURE_BASE_DIRECTORY=projects
AZURE_ENABLED=true
"""

    def _generate_file_share_config_guide(self) -> str:
        return "Configuration guide for Azure File Share settings."

    def _get_config_validation_example(self) -> str:
        return """
from app.core.config.azure_validator import validate_azure_configuration

# Validate configuration
report = validate_azure_configuration()

if report.is_valid:
    print("Configuration is valid")
else:
    for error in report.errors:
        print(f"Error: {error.message}")
"""

    def _generate_client_integration_guide(self) -> str:
        return "Guide for integrating with different client types."

    def _generate_python_client_guide(self) -> str:
        return "Python client integration guide."

    def _get_python_client_example(self) -> str:
        return """
import requests
from typing import Dict, Any

class InfrajetClient:
    def __init__(self, base_url: str, token: str):
        self.base_url = base_url
        self.headers = {"Authorization": f"Bearer {token}"}
    
    def generate_code(self, query: str, project_name: str = None) -> Dict[str, Any]:
        response = requests.post(
            f"{self.base_url}/api/v1/generate",
            headers=self.headers,
            json={"query": query, "project_name": project_name}
        )
        return response.json()

# Usage
client = InfrajetClient("http://localhost:8000", "your-token")
result = client.generate_code("Create an S3 bucket", "my-project")
"""

    def _generate_js_client_guide(self) -> str:
        return "JavaScript client integration guide."

    def _get_js_client_example(self) -> str:
        return """
class InfrajetClient {
    constructor(baseUrl, token) {
        this.baseUrl = baseUrl;
        this.headers = {
            'Authorization': `Bearer ${token}`,
            'Content-Type': 'application/json'
        };
    }
    
    async generateCode(query, projectName = null) {
        const response = await fetch(`${this.baseUrl}/api/v1/generate`, {
            method: 'POST',
            headers: this.headers,
            body: JSON.stringify({
                query: query,
                project_name: projectName
            })
        });
        return response.json();
    }
}

// Usage
const client = new InfrajetClient('http://localhost:8000', 'your-token');
const result = await client.generateCode('Create an S3 bucket', 'my-project');
"""

    def _generate_best_practices_guide(self) -> str:
        return "Best practices for Azure File Share integration."

    def _generate_error_handling_best_practices(self) -> str:
        return "Best practices for error handling in Azure File Share operations."

    def _generate_performance_best_practices(self) -> str:
        return "Performance optimization best practices."

    def _generate_security_best_practices(self) -> str:
        return "Security considerations and best practices."

    # Troubleshooting guide methods
    def _generate_common_issues_guide(self) -> str:
        return "Common issues and their solutions."

    def _generate_connection_troubleshooting(self) -> str:
        return "Troubleshooting Azure File Share connection issues."

    def _get_connection_test_example(self) -> str:
        return """
from app.core.config.azure_validator import quick_validate_azure_config

# Test Azure connection
is_valid, message = quick_validate_azure_config()

if is_valid:
    print("Azure connection is working")
else:
    print(f"Connection issue: {message}")
"""

    def _generate_auth_troubleshooting(self) -> str:
        return "Troubleshooting authentication problems."

    def _get_token_validation_example(self) -> str:
        return """
import requests

# Test token validity
response = requests.get(
    "http://localhost:8000/api/v1/projects",
    headers={"Authorization": f"Bearer {token}"}
)

if response.status_code == 401:
    print("Token is invalid or expired")
elif response.status_code == 200:
    print("Token is valid")
"""

    def _generate_file_operation_troubleshooting(self) -> str:
        return "Troubleshooting file operation errors."

    def _get_file_debug_example(self) -> str:
        return """
import logging

# Enable debug logging
logging.basicConfig(level=logging.DEBUG)

# Test file operations with detailed logging
try:
    response = requests.post("/api/v1/generate", json=data)
    print(f"Response: {response.status_code}")
except Exception as e:
    print(f"Error: {e}")
"""

    def _generate_error_codes_reference(self) -> str:
        return "Reference guide for error codes and their meanings."

    def _generate_diagnostic_tools_guide(self) -> str:
        return "Diagnostic tools for troubleshooting."

    def _get_health_check_example(self) -> str:
        return """
import requests

def health_check():
    try:
        # Check API health
        api_response = requests.get("http://localhost:8000/health")
        print(f"API Status: {api_response.status_code}")
        
        # Check Azure connection
        from app.core.config.azure_validator import validate_azure_configuration
        report = validate_azure_configuration()
        print(f"Azure Config Valid: {report.is_valid}")
        
    except Exception as e:
        print(f"Health check failed: {e}")

health_check()
"""

    def _generate_performance_troubleshooting(self) -> str:
        return "Troubleshooting performance issues."

    def _generate_performance_issues_guide(self) -> str:
        return "Guide for resolving performance issues."

    def _generate_timeout_troubleshooting(self) -> str:
        return "Troubleshooting timeout problems."

    # Examples methods
    def _get_project_creation_full_example(self) -> str:
        return """
import requests

# Create project and generate code in one request
response = requests.post(
    "http://localhost:8000/api/v1/generate",
    headers={"Authorization": f"Bearer {token}"},
    json={
        "query": "Create a complete VPC with subnets and security groups",
        "scenario": "new_resource",
        "project_name": "vpc-infrastructure"
    }
)

result = response.json()
print(f"Project created: {result['project_id']}")
print(f"Job ID: {result['job_id']}")
"""

    def _generate_advanced_examples_intro(self) -> str:
        return "Advanced examples for complex scenarios."

    def _get_multi_generation_example(self) -> str:
        return """
import requests
import time

project_id = "your-project-id"
resources = [
    "Create an AWS VPC with CIDR 10.0.0.0/16",
    "Add public subnet to the VPC",
    "Add private subnet to the VPC",
    "Create internet gateway for the VPC"
]

for i, query in enumerate(resources):
    response = requests.post(
        "http://localhost:8000/api/v1/generate",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "query": query,
            "scenario": "modify_existing" if i > 0 else "new_resource",
            "project_id": project_id
        }
    )
    
    print(f"Generated: {query}")
    time.sleep(1)  # Rate limiting
"""

    def _get_file_management_example(self) -> str:
        return """
import requests

# List all files in project
files_response = requests.get(
    f"http://localhost:8000/api/v1/projects/{project_id}/files",
    headers={"Authorization": f"Bearer {token}"}
)

files = files_response.json()
print(f"Found {len(files)} files")

# Download each file
for file in files:
    file_response = requests.get(
        f"http://localhost:8000/api/v1/projects/{project_id}/files/{file['file_path']}",
        headers={"Authorization": f"Bearer {token}"}
    )
    
    with open(file['file_path'], 'w') as f:
        f.write(file_response.text)
    
    print(f"Downloaded: {file['file_path']}")
"""

    def _generate_integration_examples_intro(self) -> str:
        return "Integration examples for CI/CD and automation."

    def _get_github_actions_example(self) -> str:
        return """
name: Infrastructure Code Generation
on:
  workflow_dispatch:
    inputs:
      infrastructure_query:
        description: 'Infrastructure to generate'
        required: true
        default: 'Create an AWS VPC'

jobs:
  generate-infrastructure:
    runs-on: ubuntu-latest
    steps:
      - name: Generate Infrastructure Code
        run: |
          response=$(curl -s -X POST "${{ secrets.INFRAJET_API_URL }}/api/v1/generate" \\
            -H "Authorization: Bearer ${{ secrets.INFRAJET_TOKEN }}" \\
            -H "Content-Type: application/json" \\
            -d "{
              \\"query\\": \\"${{ github.event.inputs.infrastructure_query }}\\",
              \\"project_name\\": \\"github-actions-${{ github.run_number }}\\"
            }")
          
          echo "Generation response: $response"
"""

    def _get_terraform_automation_example(self) -> str:
        return """
#!/bin/bash

# Terraform automation script with Infrajet integration

set -e

PROJECT_NAME="automated-infrastructure"
INFRAJET_API_URL="http://localhost:8000"
TOKEN="your-api-token"

echo "Starting infrastructure generation..."

# Generate infrastructure code
response=$(curl -s -X POST "$INFRAJET_API_URL/api/v1/generate" \\
  -H "Authorization: Bearer $TOKEN" \\
  -H "Content-Type: application/json" \\
  -d "{
    \\"query\\": \\"Create a production-ready AWS VPC\\",
    \\"scenario\\": \\"new_resource\\",
    \\"project_name\\": \\"$PROJECT_NAME\\"
  }")

job_id=$(echo $response | jq -r '.job_id')
project_id=$(echo $response | jq -r '.project_id')

echo "Job ID: $job_id"
echo "Project ID: $project_id"
"""


# Convenience functions for common documentation tasks
def generate_api_documentation(
    title: str = "Azure File Share Integration API",
) -> GeneratedDocumentation:
    """Generate comprehensive API documentation."""
    generator = DocGenerator()
    request = DocumentationRequest(
        doc_type=DocumentationType.API_REFERENCE,
        title=title,
        description="Complete API reference for Azure File Share integration",
        include_examples=True,
        include_code_snippets=True,
    )
    return generator.generate_documentation(request)


def generate_workflow_guide(
    title: str = "Azure File Share Workflow Guide",
) -> GeneratedDocumentation:
    """Generate workflow guide documentation."""
    generator = DocGenerator()
    request = DocumentationRequest(
        doc_type=DocumentationType.WORKFLOW_GUIDE,
        title=title,
        description="Complete workflow guide for Azure File Share integration",
        include_examples=True,
        include_code_snippets=True,
    )
    return generator.generate_documentation(request)


def generate_integration_guide(
    title: str = "Azure File Share Integration Guide",
) -> GeneratedDocumentation:
    """Generate integration guide documentation."""
    generator = DocGenerator()
    request = DocumentationRequest(
        doc_type=DocumentationType.INTEGRATION_GUIDE,
        title=title,
        description="Complete integration guide for Azure File Share",
        include_examples=True,
        include_code_snippets=True,
    )
    return generator.generate_documentation(request)


def enhance_openapi_spec(
    endpoints: List[str], title: str = "Enhanced API Specification"
) -> GeneratedDocumentation:
    """Generate OpenAPI specification enhancements."""
    generator = DocGenerator()
    request = DocumentationRequest(
        doc_type=DocumentationType.OPENAPI_ENHANCEMENT,
        title=title,
        description="Enhanced OpenAPI specification with examples and workflows",
        api_endpoints=endpoints,
        include_examples=True,
        include_code_snippets=True,
    )
    return generator.generate_documentation(request)
