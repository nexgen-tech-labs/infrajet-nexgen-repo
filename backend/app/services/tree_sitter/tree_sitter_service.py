"""
Tree-sitter service for parsing infrastructure and configuration files.

This module provides a unified interface for parsing various infrastructure
configuration files including Terraform, HCL, YAML, and JSON files using
multiple parsing strategies for maximum compatibility.
"""

import asyncio
from pathlib import Path
from typing import Dict, List, Optional, Any, Union
from dataclasses import dataclass

from logconfig.logger import get_logger
from .terraform_parser import TerraformParser

logger = get_logger()


@dataclass
class ParseResult:
    """
    Result of parsing a single file.

    Attributes:
        file_path: Path to the parsed file
        file_type: Type of file (terraform, yaml, json, etc.)
        success: Whether parsing was successful
        content: Parsed content as structured data
        error: Error message if parsing failed
        line_count: Number of lines in the file
    """

    file_path: str
    file_type: str
    success: bool
    content: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    line_count: int = 0


@dataclass
class ParseSummary:
    """
    Summary of parsing multiple files in a directory.

    Attributes:
        total_files: Total number of files processed
        successful_parses: Number of successfully parsed files
        failed_parses: Number of files that failed to parse
        results: List of individual parse results
        errors: List of error messages encountered
    """

    total_files: int
    successful_parses: int
    failed_parses: int
    results: List[ParseResult]
    errors: List[str]


class TreeSitterService:
    """
    Service for parsing infrastructure and configuration files.

    This service provides a unified interface for parsing various types of
    infrastructure configuration files using multiple parsing strategies
    to ensure maximum compatibility and accuracy.

    Supported file types:
        - Terraform (.tf, .tfvars)
        - HCL (.hcl)
        - YAML (.yml, .yaml)
        - JSON (.json)
    """

    SUPPORTED_EXTENSIONS = {
        ".tf": "terraform",
        ".tfvars": "terraform_vars",
        ".hcl": "hcl",
        ".yml": "yaml",
        ".yaml": "yaml",
        ".json": "json",
    }

    # Production limits
    MAX_CONCURRENT_PARSES = 10
    MAX_DIRECTORY_FILES = 1000

    def __init__(self):
        """Initialize the TreeSitterService with required parsers."""
        try:
            self.terraform_parser = TerraformParser()
            self._parse_semaphore = asyncio.Semaphore(self.MAX_CONCURRENT_PARSES)
            logger.info("TreeSitterService initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize TreeSitterService: {e}")
            raise

    async def parse_file(self, file_path: Union[str, Path]) -> ParseResult:
        """Parse a single file and extract definitions."""
        file_path = Path(file_path)

        try:
            if not file_path.exists():
                return ParseResult(
                    file_path=str(file_path),
                    file_type="unknown",
                    success=False,
                    error=f"File not found: {file_path}",
                )

            # Determine file type
            file_type = self._get_file_type(file_path)
            if not file_type:
                return ParseResult(
                    file_path=str(file_path),
                    file_type="unsupported",
                    success=False,
                    error=f"Unsupported file extension: {file_path.suffix}",
                )

            # Read file content
            content = await self._read_file_async(file_path)
            line_count = len(content.split("\n"))

            # Parse based on file type with file path for production features
            parsed_content = await self._parse_content_by_type(
                content, file_type, str(file_path)
            )

            logger.info(f"Successfully parsed {file_type} file: {file_path}")

            return ParseResult(
                file_path=str(file_path),
                file_type=file_type,
                success=True,
                content=parsed_content,
                line_count=line_count,
            )

        except Exception as e:
            logger.error(f"Error parsing file {file_path}: {str(e)}", exc_info=True)
            return ParseResult(
                file_path=str(file_path),
                file_type=self._get_file_type(file_path) or "unknown",
                success=False,
                error=str(e),
            )

    async def parse_directory(
        self,
        directory_path: Union[str, Path],
        recursive: bool = True,
        max_files: int = None,
    ) -> ParseSummary:
        """Parse all supported files in a directory."""
        directory_path = Path(directory_path)

        if not directory_path.exists() or not directory_path.is_dir():
            return ParseSummary(
                total_files=0,
                successful_parses=0,
                failed_parses=1,
                results=[],
                errors=[f"Directory not found or not a directory: {directory_path}"],
            )

        # Use production limit if not specified
        if max_files is None:
            max_files = self.MAX_DIRECTORY_FILES

        # Find all supported files
        files = self._find_supported_files(directory_path, recursive, max_files)

        if not files:
            return ParseSummary(
                total_files=0,
                successful_parses=0,
                failed_parses=0,
                results=[],
                errors=["No supported files found in directory"],
            )

        # Parse files concurrently
        tasks = [self.parse_file(file_path) for file_path in files]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Process results
        parse_results = []
        errors = []
        successful_parses = 0
        failed_parses = 0

        for result in results:
            if isinstance(result, Exception):
                errors.append(str(result))
                failed_parses += 1
            elif isinstance(result, ParseResult):
                parse_results.append(result)
                if result.success:
                    successful_parses += 1
                else:
                    failed_parses += 1
                    if result.error:
                        errors.append(f"{result.file_path}: {result.error}")

        logger.info(
            f"Parsed directory {directory_path}: {successful_parses} successful, {failed_parses} failed"
        )

        return ParseSummary(
            total_files=len(files),
            successful_parses=successful_parses,
            failed_parses=failed_parses,
            results=parse_results,
            errors=errors,
        )

    async def get_terraform_resources(
        self, file_path: Union[str, Path]
    ) -> List[Dict[str, Any]]:
        """Get all Terraform resources from a file."""
        result = await self.parse_file(file_path)

        if not result.success or not result.content:
            return []

        return result.content.get("resources", [])

    async def get_terraform_modules(
        self, file_path: Union[str, Path]
    ) -> List[Dict[str, Any]]:
        """Get all Terraform modules from a file."""
        result = await self.parse_file(file_path)

        if not result.success or not result.content:
            return []

        return result.content.get("modules", [])

    async def get_terraform_variables(
        self, file_path: Union[str, Path]
    ) -> List[Dict[str, Any]]:
        """Get all Terraform variables from a file."""
        result = await self.parse_file(file_path)

        if not result.success or not result.content:
            return []

        return result.content.get("variables", [])

    async def get_terraform_outputs(
        self, file_path: Union[str, Path]
    ) -> List[Dict[str, Any]]:
        """Get all Terraform outputs from a file."""
        result = await self.parse_file(file_path)

        if not result.success or not result.content:
            return []

        return result.content.get("outputs", [])

    async def search_resources_by_type(
        self, directory_path: Union[str, Path], resource_type: str
    ) -> List[Dict[str, Any]]:
        """Search for Terraform resources of a specific type in a directory."""
        summary = await self.parse_directory(directory_path)

        matching_resources = []

        for result in summary.results:
            if result.success and result.content and result.file_type == "terraform":
                resources = result.content.get("resources", [])
                for resource in resources:
                    if resource.get("type") == resource_type:
                        resource["file_path"] = result.file_path
                        matching_resources.append(resource)

        return matching_resources

    def _get_file_type(self, file_path: Path) -> Optional[str]:
        """Determine the file type based on extension."""
        return self.SUPPORTED_EXTENSIONS.get(file_path.suffix.lower())

    def _find_supported_files(
        self, directory_path: Path, recursive: bool, max_files: int
    ) -> List[Path]:
        """Find all supported files in a directory."""
        files = []

        try:
            if recursive:
                pattern = "**/*"
            else:
                pattern = "*"

            for file_path in directory_path.glob(pattern):
                if file_path.is_file() and self._get_file_type(file_path):
                    files.append(file_path)

                    if len(files) >= max_files:
                        logger.warning(
                            f"Reached maximum file limit ({max_files}), stopping search"
                        )
                        break

        except Exception as e:
            logger.error(f"Error finding files in {directory_path}: {str(e)}")

        return files

    async def _read_file_async(self, file_path: Path) -> str:
        """Read file content asynchronously."""
        loop = asyncio.get_event_loop()

        def read_file():
            with open(file_path, "r", encoding="utf-8") as f:
                return f.read()

        return await loop.run_in_executor(None, read_file)

    async def _parse_content_by_type(
        self, content: str, file_type: str, file_path: Optional[str] = None
    ) -> Dict[str, Any]:
        """Parse content based on file type with production features."""
        if file_type == "terraform":
            return self.terraform_parser.parse_content(content, file_path)
        elif file_type == "terraform_vars":
            return self._parse_terraform_vars(content)
        elif file_type == "yaml":
            return self._parse_yaml(content)
        elif file_type == "json":
            return self._parse_json(content)
        elif file_type == "hcl":
            # For now, treat HCL similar to Terraform
            return self.terraform_parser.parse_content(content, file_path)
        else:
            return {"raw_content": content}

    def _parse_terraform_vars(self, content: str) -> Dict[str, Any]:
        """Parse Terraform variables file (.tfvars)."""
        variables = {}

        for line in content.split("\n"):
            line = line.strip()
            if not line or line.startswith("#"):
                continue

            if "=" in line:
                key, value = line.split("=", 1)
                key = key.strip()
                value = value.strip().rstrip(",")

                # Remove quotes if present
                if value.startswith('"') and value.endswith('"'):
                    value = value[1:-1]
                elif value.startswith("'") and value.endswith("'"):
                    value = value[1:-1]

                variables[key] = value

        return {"variables": variables}

    def _parse_yaml(self, content: str) -> Dict[str, Any]:
        """Parse YAML content."""
        try:
            import yaml

            return {"yaml_content": yaml.safe_load(content)}
        except ImportError:
            logger.warning("PyYAML not installed, returning raw content")
            return {"raw_content": content}
        except Exception as e:
            logger.error(f"Error parsing YAML: {str(e)}")
            return {"raw_content": content, "parse_error": str(e)}

    def _parse_json(self, content: str) -> Dict[str, Any]:
        """Parse JSON content."""
        try:
            import json

            return {"json_content": json.loads(content)}
        except Exception as e:
            logger.error(f"Error parsing JSON: {str(e)}")
            return {"raw_content": content, "parse_error": str(e)}
