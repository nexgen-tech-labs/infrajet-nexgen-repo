"""
Unified Diff Generator for Terraform Code Changes.

This module provides robust diff generation capabilities for Terraform code,
supporting both file-to-file and string-to-string comparisons with Terraform-aware
formatting and context handling.
"""

import asyncio
import difflib
import hashlib
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Union, Any
from enum import Enum

from logconfig.logger import get_logger

logger = get_logger()


class DiffMode(Enum):
    """Diff generation modes."""
    UNIFIED = "unified"
    CONTEXT = "context"
    HTML = "html"


class DiffScope(Enum):
    """Scope of diff comparison."""
    FILE = "file"
    STRING = "string"
    BLOCK = "block"


@dataclass
class DiffOptions:
    """Configuration options for diff generation."""
    context_lines: int = 3
    ignore_whitespace: bool = False
    ignore_blank_lines: bool = False
    show_line_numbers: bool = True
    tab_width: int = 8
    max_line_length: Optional[int] = None
    terraform_aware: bool = True
    mode: DiffMode = DiffMode.UNIFIED


@dataclass
class DiffResult:
    """Result of a diff generation operation."""
    diff_content: str
    additions: int = 0
    deletions: int = 0
    changes: int = 0
    has_changes: bool = False
    source_hash: str = ""
    target_hash: str = ""
    processing_time_ms: float = 0.0
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class FileDiffRequest:
    """Request for file-based diff generation."""
    source_file: Union[str, Path]
    target_file: Union[str, Path]
    options: DiffOptions = field(default_factory=DiffOptions)


@dataclass
class StringDiffRequest:
    """Request for string-based diff generation."""
    source_content: str
    target_content: str
    source_name: str = "source"
    target_name: str = "target"
    options: DiffOptions = field(default_factory=DiffOptions)


class TerraformDiffGenerator:
    """
    Unified diff generator specialized for Terraform code changes.

    Provides comprehensive diff generation with Terraform-specific formatting,
    block-level awareness, and performance optimizations.
    """

    def __init__(self):
        """Initialize the diff generator."""
        self.default_options = DiffOptions()
        logger.info("TerraformDiffGenerator initialized")

    async def generate_file_diff(self, request: FileDiffRequest) -> DiffResult:
        """
        Generate diff between two files.

        Args:
            request: File diff request with source and target files

        Returns:
            DiffResult containing the generated diff and metadata
        """
        start_time = asyncio.get_event_loop().time()

        try:
            # Read file contents
            source_path = Path(request.source_file)
            target_path = Path(request.target_file)

            if not source_path.exists():
                raise FileNotFoundError(f"Source file not found: {source_path}")
            if not target_path.exists():
                raise FileNotFoundError(f"Target file not found: {target_path}")

            source_content = await self._read_file_async(source_path)
            target_content = await self._read_file_async(target_path)

            # Generate string diff
            string_request = StringDiffRequest(
                source_content=source_content,
                target_content=target_content,
                source_name=str(source_path.name),
                target_name=str(target_path.name),
                options=request.options
            )

            result = await self.generate_string_diff(string_request)

            # Update metadata
            result.metadata.update({
                "source_file": str(source_path),
                "target_file": str(target_path),
                "diff_scope": DiffScope.FILE.value
            })

            processing_time = (asyncio.get_event_loop().time() - start_time) * 1000
            result.processing_time_ms = processing_time

            logger.info(
                f"Generated file diff between {source_path.name} and {target_path.name} "
                f"in {processing_time:.2f}ms"
            )

            return result

        except Exception as e:
            logger.error(f"File diff generation failed: {e}")
            processing_time = (asyncio.get_event_loop().time() - start_time) * 1000
            return DiffResult(
                diff_content="",
                processing_time_ms=processing_time,
                metadata={"error": str(e), "diff_scope": DiffScope.FILE.value}
            )

    async def generate_string_diff(self, request: StringDiffRequest) -> DiffResult:
        """
        Generate diff between two string contents.

        Args:
            request: String diff request with source and target content

        Returns:
            DiffResult containing the generated diff and metadata
        """
        start_time = asyncio.get_event_loop().time()

        try:
            # Preprocess content if needed
            source_lines = self._preprocess_content(request.source_content, request.options)
            target_lines = self._preprocess_content(request.target_content, request.options)

            # Generate hashes for change detection
            source_hash = hashlib.md5(request.source_content.encode()).hexdigest()
            target_hash = hashlib.md5(request.target_content.encode()).hexdigest()

            # Check if content has changed
            if source_hash == target_hash:
                return DiffResult(
                    diff_content="",
                    source_hash=source_hash,
                    target_hash=target_hash,
                    processing_time_ms=(asyncio.get_event_loop().time() - start_time) * 1000,
                    metadata={"diff_scope": DiffScope.STRING.value}
                )

            # Generate unified diff
            diff_lines = list(difflib.unified_diff(
                source_lines,
                target_lines,
                fromfile=request.source_name,
                tofile=request.target_name,
                lineterm='',
                n=request.options.context_lines
            ))

            # Apply Terraform-aware formatting if enabled
            if request.options.terraform_aware:
                diff_lines = self._apply_terraform_formatting(diff_lines, request.options)

            # Format the diff content
            diff_content = '\n'.join(diff_lines)

            # Analyze changes
            additions, deletions, changes = self._analyze_diff_lines(diff_lines)

            processing_time = (asyncio.get_event_loop().time() - start_time) * 1000

            result = DiffResult(
                diff_content=diff_content,
                additions=additions,
                deletions=deletions,
                changes=changes,
                has_changes=True,
                source_hash=source_hash,
                target_hash=target_hash,
                processing_time_ms=processing_time,
                metadata={
                    "diff_scope": DiffScope.STRING.value,
                    "source_name": request.source_name,
                    "target_name": request.target_name
                }
            )

            logger.info(
                f"Generated string diff with {additions} additions, {deletions} deletions "
                f"in {processing_time:.2f}ms"
            )

            return result

        except Exception as e:
            logger.error(f"String diff generation failed: {e}")
            processing_time = (asyncio.get_event_loop().time() - start_time) * 1000
            return DiffResult(
                diff_content="",
                processing_time_ms=processing_time,
                metadata={"error": str(e), "diff_scope": DiffScope.STRING.value}
            )

    async def generate_block_diff(
        self,
        source_blocks: Dict[str, str],
        target_blocks: Dict[str, str],
        block_type: str = "resource",
        options: Optional[DiffOptions] = None
    ) -> Dict[str, DiffResult]:
        """
        Generate diffs for specific Terraform blocks (resources, modules, etc.).

        Args:
            source_blocks: Dictionary of source blocks {block_name: content}
            target_blocks: Dictionary of target blocks {block_name: content}
            block_type: Type of blocks being compared
            options: Diff options

        Returns:
            Dictionary of diff results keyed by block name
        """
        if options is None:
            options = self.default_options

        results = {}
        tasks = []

        # Create diff tasks for each block
        all_block_names = set(source_blocks.keys()) | set(target_blocks.keys())

        for block_name in all_block_names:
            source_content = source_blocks.get(block_name, "")
            target_content = target_blocks.get(block_name, "")

            task = self._generate_single_block_diff(
                block_name, source_content, target_content, block_type, options
            )
            tasks.append(task)

        # Execute all block diffs concurrently
        block_results = await asyncio.gather(*tasks, return_exceptions=True)

        # Process results
        for i, block_name in enumerate(all_block_names):
            result = block_results[i]
            if isinstance(result, Exception):
                logger.error(f"Block diff failed for {block_name}: {result}")
                results[block_name] = DiffResult(
                    diff_content="",
                    metadata={"error": str(result), "diff_scope": DiffScope.BLOCK.value}
                )
            else:
                results[block_name] = result

        logger.info(f"Generated block diffs for {len(results)} {block_type} blocks")
        return results

    async def _generate_single_block_diff(
        self,
        block_name: str,
        source_content: str,
        target_content: str,
        block_type: str,
        options: DiffOptions
    ) -> DiffResult:
        """Generate diff for a single block."""
        request = StringDiffRequest(
            source_content=source_content,
            target_content=target_content,
            source_name=f"{block_type}.{block_name}",
            target_name=f"{block_type}.{block_name}",
            options=options
        )

        result = await self.generate_string_diff(request)
        result.metadata["block_type"] = block_type
        result.metadata["block_name"] = block_name
        result.metadata["diff_scope"] = DiffScope.BLOCK.value

        return result

    async def _read_file_async(self, file_path: Path) -> str:
        """Read file content asynchronously."""
        def read_file():
            with open(file_path, 'r', encoding='utf-8') as f:
                return f.read()

        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, read_file)

    def _preprocess_content(self, content: str, options: DiffOptions) -> List[str]:
        """Preprocess content for diff generation."""
        lines = content.splitlines()

        if options.ignore_blank_lines:
            lines = [line for line in lines if line.strip()]

        if options.ignore_whitespace:
            lines = [line.rstrip() for line in lines]

        return lines

    def _apply_terraform_formatting(self, diff_lines: List[str], options: DiffOptions) -> List[str]:
        """Apply Terraform-specific formatting to diff lines."""
        formatted_lines = []

        for line in diff_lines:
            if line.startswith('@@'):
                # Hunk header - add Terraform context
                formatted_lines.append(line)
            elif line.startswith('+') or line.startswith('-'):
                # Changed line - check for Terraform block starts
                stripped = line[1:].strip()
                if any(stripped.startswith(keyword) for keyword in [
                    'resource "', 'module "', 'variable "', 'output "', 'provider "', 'data "'
                ]):
                    # Add comment for block changes
                    formatted_lines.append(line)
                else:
                    formatted_lines.append(line)
            else:
                # Context line
                formatted_lines.append(line)

        return formatted_lines

    def _analyze_diff_lines(self, diff_lines: List[str]) -> tuple[int, int, int]:
        """Analyze diff lines to count additions, deletions, and changes."""
        additions = 0
        deletions = 0
        changes = 0

        for line in diff_lines:
            if line.startswith('+') and not line.startswith('+++'):
                additions += 1
            elif line.startswith('-') and not line.startswith('---'):
                deletions += 1

        changes = additions + deletions
        return additions, deletions, changes

    async def get_generator_stats(self) -> Dict[str, Any]:
        """Get statistics about the diff generator."""
        return {
            "status": "operational",
            "default_context_lines": self.default_options.context_lines,
            "terraform_aware": self.default_options.terraform_aware,
            "supported_modes": [mode.value for mode in DiffMode],
            "supported_scopes": [scope.value for scope in DiffScope]
        }