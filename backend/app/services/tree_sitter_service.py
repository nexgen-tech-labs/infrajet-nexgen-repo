"""
FastAPI service wrapper for tree-sitter parsing functionality.

This module provides a FastAPI-compatible wrapper around the core
tree-sitter parsing service, handling HTTP exceptions and providing
API-friendly interfaces.
"""

from pathlib import Path
from typing import Dict, List, Optional, Any, Union
from fastapi import HTTPException

from logconfig.logger import get_logger
from .tree_sitter.tree_sitter_service import TreeSitterService as BaseTreeSitterService
from .tree_sitter.tree_sitter_service import ParseResult, ParseSummary

logger = get_logger()


class TreeSitterService:
    """
    FastAPI service wrapper for tree-sitter parsing functionality.

    This service provides HTTP-friendly interfaces for parsing infrastructure
    configuration files, with proper error handling and response formatting
    for FastAPI applications.
    """

    def __init__(self):
        """Initialize the FastAPI service wrapper."""
        try:
            self.parser_service = BaseTreeSitterService()
            logger.info("TreeSitterService wrapper initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize TreeSitterService wrapper: {e}")
            # Don't raise - allow graceful degradation
            self.parser_service = None

    async def parse_file(self, file_path: Union[str, Path]) -> ParseResult:
        """Parse a single file and return ParseResult."""
        if not self.parser_service:
            return ParseResult(
                file_path=str(file_path),
                file_type="unknown",
                success=False,
                error="TreeSitter parser not available",
            )
        return await self.parser_service.parse_file(file_path)

    async def parse_terraform_file(self, file_path: Union[str, Path]) -> Dict[str, Any]:
        """Parse a single Terraform file and return structured data."""
        if not self.parser_service:
            raise HTTPException(
                status_code=503, detail="TreeSitter parser service not available"
            )

        try:
            result = await self.parser_service.parse_file(file_path)

            if not result.success:
                raise HTTPException(
                    status_code=400, detail=f"Failed to parse file: {result.error}"
                )

            return {
                "file_path": result.file_path,
                "file_type": result.file_type,
                "line_count": result.line_count,
                "content": result.content,
                "success": True,
            }

        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error in parse_terraform_file: {str(e)}", exc_info=True)
            raise HTTPException(
                status_code=500,
                detail=f"Internal server error while parsing file: {str(e)}",
            )

    async def parse_terraform_directory(
        self,
        directory_path: Union[str, Path],
        recursive: bool = True,
        max_files: int = 100,
    ) -> Dict[str, Any]:
        """Parse all Terraform files in a directory."""
        try:
            summary = await self.parser_service.parse_directory(
                directory_path, recursive, max_files
            )

            return {
                "directory_path": str(directory_path),
                "total_files": summary.total_files,
                "successful_parses": summary.successful_parses,
                "failed_parses": summary.failed_parses,
                "results": [
                    {
                        "file_path": result.file_path,
                        "file_type": result.file_type,
                        "success": result.success,
                        "content": result.content,
                        "error": result.error,
                        "line_count": result.line_count,
                    }
                    for result in summary.results
                ],
                "errors": summary.errors,
            }

        except Exception as e:
            logger.error(f"Error in parse_terraform_directory: {str(e)}", exc_info=True)
            raise HTTPException(
                status_code=500,
                detail=f"Internal server error while parsing directory: {str(e)}",
            )

    async def get_terraform_resources(
        self, file_path: Union[str, Path]
    ) -> List[Dict[str, Any]]:
        """Extract all Terraform resources from a file."""
        try:
            resources = await self.parser_service.get_terraform_resources(file_path)
            return resources

        except Exception as e:
            logger.error(f"Error getting Terraform resources: {str(e)}", exc_info=True)
            raise HTTPException(
                status_code=500, detail=f"Error extracting resources: {str(e)}"
            )

    async def get_terraform_modules(
        self, file_path: Union[str, Path]
    ) -> List[Dict[str, Any]]:
        """Extract all Terraform modules from a file."""
        try:
            modules = await self.parser_service.get_terraform_modules(file_path)
            return modules

        except Exception as e:
            logger.error(f"Error getting Terraform modules: {str(e)}", exc_info=True)
            raise HTTPException(
                status_code=500, detail=f"Error extracting modules: {str(e)}"
            )

    async def get_terraform_variables(
        self, file_path: Union[str, Path]
    ) -> List[Dict[str, Any]]:
        """Extract all Terraform variables from a file."""
        try:
            variables = await self.parser_service.get_terraform_variables(file_path)
            return variables

        except Exception as e:
            logger.error(f"Error getting Terraform variables: {str(e)}", exc_info=True)
            raise HTTPException(
                status_code=500, detail=f"Error extracting variables: {str(e)}"
            )

    async def get_terraform_outputs(
        self, file_path: Union[str, Path]
    ) -> List[Dict[str, Any]]:
        """Extract all Terraform outputs from a file."""
        try:
            outputs = await self.parser_service.get_terraform_outputs(file_path)
            return outputs

        except Exception as e:
            logger.error(f"Error getting Terraform outputs: {str(e)}", exc_info=True)
            raise HTTPException(
                status_code=500, detail=f"Error extracting outputs: {str(e)}"
            )

    async def search_resources_by_type(
        self, directory_path: Union[str, Path], resource_type: str
    ) -> List[Dict[str, Any]]:
        """Search for Terraform resources of a specific type."""
        try:
            resources = await self.parser_service.search_resources_by_type(
                directory_path, resource_type
            )
            return resources

        except Exception as e:
            logger.error(f"Error searching resources by type: {str(e)}", exc_info=True)
            raise HTTPException(
                status_code=500, detail=f"Error searching resources: {str(e)}"
            )

    async def analyze_terraform_project(
        self, project_path: Union[str, Path]
    ) -> Dict[str, Any]:
        """Analyze an entire Terraform project and provide insights."""
        try:
            summary = await self.parser_service.parse_directory(project_path)

            # Aggregate statistics
            total_resources = 0
            total_modules = 0
            total_variables = 0
            total_outputs = 0
            resource_types = {}

            for result in summary.results:
                if result.success and result.content:
                    resources = result.content.get("resources", [])
                    modules = result.content.get("modules", [])
                    variables = result.content.get("variables", [])
                    outputs = result.content.get("outputs", [])

                    total_resources += len(resources)
                    total_modules += len(modules)
                    total_variables += len(variables)
                    total_outputs += len(outputs)

                    # Count resource types
                    for resource in resources:
                        res_type = resource.get("type", "unknown")
                        resource_types[res_type] = resource_types.get(res_type, 0) + 1

            return {
                "project_path": str(project_path),
                "summary": {
                    "total_files": summary.total_files,
                    "successful_parses": summary.successful_parses,
                    "failed_parses": summary.failed_parses,
                    "total_resources": total_resources,
                    "total_modules": total_modules,
                    "total_variables": total_variables,
                    "total_outputs": total_outputs,
                },
                "resource_types": resource_types,
                "errors": summary.errors,
                "files": [
                    {
                        "file_path": result.file_path,
                        "file_type": result.file_type,
                        "success": result.success,
                        "line_count": result.line_count,
                        "resource_count": (
                            len(result.content.get("resources", []))
                            if result.content
                            else 0
                        ),
                        "module_count": (
                            len(result.content.get("modules", []))
                            if result.content
                            else 0
                        ),
                    }
                    for result in summary.results
                ],
            }

        except Exception as e:
            logger.error(f"Error analyzing Terraform project: {str(e)}", exc_info=True)
            raise HTTPException(
                status_code=500, detail=f"Error analyzing project: {str(e)}"
            )

    def get_supported_file_types(self) -> List[str]:
        """Get list of supported file extensions."""
        if not self.parser_service:
            return []
        return list(self.parser_service.SUPPORTED_EXTENSIONS.keys())

    def is_available(self) -> bool:
        """Check if the TreeSitter service is available."""
        return self.parser_service is not None

    async def highlight_terraform(
        self, content: str
    ) -> tuple[str, List[Dict[str, Any]]]:
        """
        Apply syntax highlighting to Terraform content.

        Args:
            content: Terraform file content

        Returns:
            Tuple of (highlighted_content, tokens)
        """
        try:
            if not self.parser_service:
                # Fallback to basic highlighting
                return self._basic_terraform_highlight(content), []

            # Use tree-sitter for advanced highlighting
            # This is a simplified implementation - in a real scenario,
            # you'd use tree-sitter's syntax highlighting capabilities
            tokens = []
            highlighted_content = self._basic_terraform_highlight(content)

            return highlighted_content, tokens

        except Exception as e:
            logger.error(f"Error highlighting Terraform content: {str(e)}")
            # Fallback to basic highlighting
            return self._basic_terraform_highlight(content), []

    def _basic_terraform_highlight(self, content: str) -> str:
        """Apply basic Terraform syntax highlighting."""
        lines = content.split("\n")
        highlighted_lines = []

        terraform_keywords = [
            "resource",
            "data",
            "variable",
            "output",
            "module",
            "provider",
            "terraform",
            "locals",
            "moved",
            "import",
        ]

        for line in lines:
            highlighted_line = line

            # Highlight comments
            if line.strip().startswith("#"):
                highlighted_line = f'<span class="terraform-comment">{line}</span>'
            elif line.strip().startswith("//"):
                highlighted_line = f'<span class="terraform-comment">{line}</span>'
            else:
                # Highlight keywords
                for keyword in terraform_keywords:
                    if f'{keyword} "' in line or f"{keyword} {{" in line:
                        highlighted_line = highlighted_line.replace(
                            keyword, f'<span class="terraform-keyword">{keyword}</span>'
                        )

                # Highlight strings
                import re

                highlighted_line = re.sub(
                    r'"([^"]*)"',
                    r'<span class="terraform-string">"$1"</span>',
                    highlighted_line,
                )

                # Highlight resource types and names
                if 'resource "' in line:
                    highlighted_line = re.sub(
                        r'resource\s+"([^"]+)"\s+"([^"]+)"',
                        r'<span class="terraform-keyword">resource</span> <span class="terraform-type">"$1"</span> <span class="terraform-name">"$2"</span>',
                        highlighted_line,
                    )

            highlighted_lines.append(highlighted_line)

        return "\n".join(highlighted_lines)

    async def validate_terraform_syntax(
        self, file_path: Union[str, Path]
    ) -> Dict[str, Any]:
        """Basic Terraform syntax validation."""
        try:
            result = await self.parser_service.parse_file(file_path)

            validation_result = {
                "file_path": str(file_path),
                "is_valid": result.success,
                "errors": [],
                "warnings": [],
            }

            if not result.success:
                validation_result["errors"].append(
                    result.error or "Unknown parsing error"
                )

            if result.success and result.content:
                # Basic validation checks
                resources = result.content.get("resources", [])
                modules = result.content.get("modules", [])

                # Check for common issues
                for resource in resources:
                    if not resource.get("name"):
                        validation_result["warnings"].append(
                            f"Resource {resource.get('type', 'unknown')} missing name"
                        )

                for module in modules:
                    if not module.get("source"):
                        validation_result["warnings"].append(
                            f"Module {module.get('name', 'unknown')} missing source"
                        )

            return validation_result

        except Exception as e:
            logger.error(f"Error validating Terraform syntax: {str(e)}", exc_info=True)
            raise HTTPException(
                status_code=500, detail=f"Error validating syntax: {str(e)}"
            )
