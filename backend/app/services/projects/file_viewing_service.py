"""
Enhanced file viewing service with syntax highlighting and tree structure.

This service provides comprehensive file viewing capabilities including:
- Syntax highlighting for multiple file types
- File tree structure with generation grouping
- File search and filtering
- Proper MIME type handling
- Download functionality
"""

import json
import mimetypes
from pathlib import Path
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass
from enum import Enum

import yaml
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_

from app.models.project import Project, ProjectFile, CodeGeneration, GeneratedFile
from app.services.azure.file_operations import FileOperationsService
from app.services.tree_sitter_service import TreeSitterService


class SupportedFileType(str, Enum):
    """Supported file types for syntax highlighting."""

    TERRAFORM = "tf"
    TERRAFORM_VARS = "tfvars"
    JSON = "json"
    YAML = "yaml"
    YML = "yml"
    MARKDOWN = "md"
    TEXT = "txt"
    HCL = "hcl"


@dataclass
class FileTreeNode:
    """Represents a node in the file tree structure."""

    name: str
    path: str
    type: str  # 'file' or 'directory'
    size_bytes: Optional[int] = None
    file_type: Optional[str] = None
    generation_id: Optional[str] = None
    generation_hash: Optional[str] = None
    children: Optional[List["FileTreeNode"]] = None
    metadata: Optional[Dict[str, Any]] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        result = {
            "name": self.name,
            "path": self.path,
            "type": self.type,
            "size_bytes": self.size_bytes,
            "file_type": self.file_type,
            "generation_id": self.generation_id,
            "generation_hash": self.generation_hash,
            "metadata": self.metadata or {},
        }

        if self.children:
            result["children"] = [child.to_dict() for child in self.children]

        return result


@dataclass
class SyntaxHighlightedContent:
    """Container for syntax highlighted file content."""

    content: str
    highlighted_content: str
    language: str
    line_count: int
    tokens: Optional[List[Dict[str, Any]]] = None
    syntax_errors: Optional[List[str]] = None


@dataclass
class FileSearchResult:
    """Result from file search operation."""

    file_path: str
    file_type: str
    size_bytes: int
    generation_id: Optional[str]
    matches: List[Dict[str, Any]]  # Line number, content, context
    score: float  # Relevance score


class FileViewingService:
    """Service for enhanced file viewing with syntax highlighting."""

    def __init__(self, db_session: Session):
        """Initialize the file viewing service."""
        self.db = db_session
        self.azure_service = FileOperationsService()
        self.tree_sitter_service = TreeSitterService()

        # MIME type mappings
        self.mime_types = {
            "tf": "text/x-terraform",
            "tfvars": "text/x-terraform-vars",
            "json": "application/json",
            "yaml": "text/yaml",
            "yml": "text/yaml",
            "md": "text/markdown",
            "txt": "text/plain",
            "hcl": "text/x-hcl",
        }

    async def get_project_file_tree(
        self,
        project_id: str,
        group_by_generation: bool = True,
        include_metadata: bool = True,
    ) -> FileTreeNode:
        """
        Get hierarchical file tree structure for a project.

        Args:
            project_id: Project ID
            group_by_generation: Whether to group files by generation
            include_metadata: Whether to include file metadata

        Returns:
            Root FileTreeNode representing the project structure
        """
        # Get all project files with generation info
        query = (
            self.db.query(ProjectFile, CodeGeneration, GeneratedFile)
            .outerjoin(GeneratedFile, ProjectFile.id == GeneratedFile.project_file_id)
            .outerjoin(CodeGeneration, GeneratedFile.generation_id == CodeGeneration.id)
            .filter(ProjectFile.project_id == project_id)
            .order_by(ProjectFile.file_path)
        )

        files_data = query.all()

        if group_by_generation:
            return self._build_generation_grouped_tree(files_data, include_metadata)
        else:
            return self._build_flat_tree(files_data, include_metadata)

    def _build_generation_grouped_tree(
        self, files_data: List[Tuple], include_metadata: bool
    ) -> FileTreeNode:
        """Build file tree grouped by generation."""
        root = FileTreeNode(name="project", path="", type="directory", children=[])

        # Group files by generation
        generations = {}
        ungrouped_files = []

        for file_record, generation, generated_file in files_data:
            if generation:
                gen_id = generation.id
                if gen_id not in generations:
                    generations[gen_id] = {"generation": generation, "files": []}
                generations[gen_id]["files"].append(file_record)
            else:
                ungrouped_files.append(file_record)

        # Add generation folders
        for gen_id, gen_data in generations.items():
            generation = gen_data["generation"]
            gen_node = FileTreeNode(
                name=f"Generation: {generation.scenario} ({generation.generation_hash[:8]})",
                path=f"generations/{gen_id}",
                type="directory",
                generation_id=gen_id,
                generation_hash=generation.generation_hash,
                children=[],
                metadata=(
                    {
                        "query": generation.query,
                        "status": generation.status,
                        "created_at": generation.created_at.isoformat(),
                        "file_count": len(gen_data["files"]),
                    }
                    if include_metadata
                    else None
                ),
            )

            # Add files to generation folder
            for file_record in gen_data["files"]:
                file_node = self._create_file_node(file_record, include_metadata)
                file_node.generation_id = gen_id
                file_node.generation_hash = generation.generation_hash
                gen_node.children.append(file_node)

            root.children.append(gen_node)

        # Add ungrouped files
        if ungrouped_files:
            misc_node = FileTreeNode(
                name="Other Files", path="misc", type="directory", children=[]
            )

            for file_record in ungrouped_files:
                file_node = self._create_file_node(file_record, include_metadata)
                misc_node.children.append(file_node)

            root.children.append(misc_node)

        return root

    def _build_flat_tree(
        self, files_data: List[Tuple], include_metadata: bool
    ) -> FileTreeNode:
        """Build flat file tree structure."""
        root = FileTreeNode(name="project", path="", type="directory", children=[])

        # Build directory structure
        dir_nodes = {}

        for file_record, generation, generated_file in files_data:
            file_path = Path(file_record.file_path)

            # Create directory nodes if needed
            current_path = ""
            current_node = root

            for part in file_path.parts[:-1]:  # All parts except filename
                current_path = str(Path(current_path) / part)

                if current_path not in dir_nodes:
                    dir_node = FileTreeNode(
                        name=part, path=current_path, type="directory", children=[]
                    )
                    dir_nodes[current_path] = dir_node
                    current_node.children.append(dir_node)

                current_node = dir_nodes[current_path]

            # Add file node
            file_node = self._create_file_node(file_record, include_metadata)
            if generation:
                file_node.generation_id = generation.id
                file_node.generation_hash = generation.generation_hash

            current_node.children.append(file_node)

        return root

    def _create_file_node(
        self, file_record: ProjectFile, include_metadata: bool
    ) -> FileTreeNode:
        """Create a file node from ProjectFile record."""
        filename = Path(file_record.file_path).name

        metadata = None
        if include_metadata:
            metadata = {
                "content_hash": file_record.content_hash,
                "created_at": file_record.created_at.isoformat(),
                "updated_at": file_record.updated_at.isoformat(),
                "azure_path": file_record.azure_path,
            }

        return FileTreeNode(
            name=filename,
            path=file_record.file_path,
            type="file",
            size_bytes=file_record.size_bytes,
            file_type=file_record.file_type,
            metadata=metadata,
        )

    async def get_file_with_syntax_highlighting(
        self, project_id: str, file_path: str, highlight_syntax: bool = True
    ) -> SyntaxHighlightedContent:
        """
        Get file content with syntax highlighting.

        Args:
            project_id: Project ID
            file_path: File path within project
            highlight_syntax: Whether to apply syntax highlighting

        Returns:
            SyntaxHighlightedContent with highlighted content
        """
        # Get file record
        file_record = (
            self.db.query(ProjectFile)
            .filter(
                and_(
                    ProjectFile.project_id == project_id,
                    ProjectFile.file_path == file_path,
                )
            )
            .first()
        )

        if not file_record:
            raise FileNotFoundError(
                f"File {file_path} not found in project {project_id}"
            )

        # Download file content
        content = await self.azure_service.download_file(project_id, file_path)

        if not highlight_syntax:
            return SyntaxHighlightedContent(
                content=content,
                highlighted_content=content,
                language="text",
                line_count=len(content.splitlines()),
            )

        # Determine language for syntax highlighting
        language = self._get_language_for_file_type(file_record.file_type)

        # Apply syntax highlighting
        try:
            highlighted_content, tokens, errors = await self._highlight_content(
                content, language, file_record.file_type
            )

            return SyntaxHighlightedContent(
                content=content,
                highlighted_content=highlighted_content,
                language=language,
                line_count=len(content.splitlines()),
                tokens=tokens,
                syntax_errors=errors,
            )

        except Exception as e:
            # Fallback to plain text if highlighting fails
            return SyntaxHighlightedContent(
                content=content,
                highlighted_content=content,
                language="text",
                line_count=len(content.splitlines()),
                syntax_errors=[f"Syntax highlighting failed: {str(e)}"],
            )

    async def _highlight_content(
        self, content: str, language: str, file_type: str
    ) -> Tuple[str, Optional[List[Dict]], Optional[List[str]]]:
        """Apply syntax highlighting to content."""
        tokens = []
        errors = []

        try:
            if file_type in ["json"]:
                # Validate and format JSON
                try:
                    parsed = json.loads(content)
                    formatted_content = json.dumps(parsed, indent=2)
                    highlighted = self._highlight_json(formatted_content)
                    return highlighted, tokens, errors
                except json.JSONDecodeError as e:
                    errors.append(f"JSON syntax error: {str(e)}")
                    return content, tokens, errors

            elif file_type in ["yaml", "yml"]:
                # Validate and highlight YAML
                try:
                    yaml.safe_load(content)
                    highlighted = self._highlight_yaml(content)
                    return highlighted, tokens, errors
                except yaml.YAMLError as e:
                    errors.append(f"YAML syntax error: {str(e)}")
                    return content, tokens, errors

            elif file_type in ["tf", "tfvars", "hcl"]:
                # Use tree-sitter for Terraform/HCL
                highlighted, parse_tokens = (
                    await self.tree_sitter_service.highlight_terraform(content)
                )
                tokens = parse_tokens
                return highlighted, tokens, errors

            else:
                # Basic highlighting for other types
                highlighted = self._highlight_generic(content, language)
                return highlighted, tokens, errors

        except Exception as e:
            errors.append(f"Highlighting error: {str(e)}")
            return content, tokens, errors

    def _highlight_json(self, content: str) -> str:
        """Apply basic JSON syntax highlighting."""
        # This is a simplified implementation
        # In a real implementation, you'd use a proper syntax highlighter
        lines = content.split("\n")
        highlighted_lines = []

        for line in lines:
            # Basic JSON highlighting patterns
            line = line.replace('"', '<span class="json-string">"</span>')
            line = line.replace(":", '<span class="json-colon">:</span>')
            line = line.replace("{", '<span class="json-brace">{</span>')
            line = line.replace("}", '<span class="json-brace">}</span>')
            highlighted_lines.append(line)

        return "\n".join(highlighted_lines)

    def _highlight_yaml(self, content: str) -> str:
        """Apply basic YAML syntax highlighting."""
        lines = content.split("\n")
        highlighted_lines = []

        for line in lines:
            stripped = line.strip()
            if stripped.startswith("#"):
                # Comment
                highlighted_lines.append(f'<span class="yaml-comment">{line}</span>')
            elif ":" in stripped and not stripped.startswith("-"):
                # Key-value pair
                key, value = line.split(":", 1)
                highlighted_line = f'<span class="yaml-key">{key}</span>:<span class="yaml-value">{value}</span>'
                highlighted_lines.append(highlighted_line)
            else:
                highlighted_lines.append(line)

        return "\n".join(highlighted_lines)

    def _highlight_generic(self, content: str, language: str) -> str:
        """Apply generic syntax highlighting."""
        # Basic highlighting for generic files
        return content  # Return as-is for now

    def _get_language_for_file_type(self, file_type: str) -> str:
        """Get language identifier for syntax highlighting."""
        language_map = {
            "tf": "terraform",
            "tfvars": "terraform",
            "hcl": "hcl",
            "json": "json",
            "yaml": "yaml",
            "yml": "yaml",
            "md": "markdown",
            "txt": "text",
        }
        return language_map.get(file_type.lower(), "text")

    def get_mime_type(self, file_type: str) -> str:
        """Get MIME type for file type."""
        return self.mime_types.get(file_type.lower(), "text/plain")

    async def search_files(
        self,
        project_id: str,
        query: str,
        file_types: Optional[List[str]] = None,
        max_results: int = 50,
    ) -> List[FileSearchResult]:
        """
        Search for files and content within a project.

        Args:
            project_id: Project ID to search in
            query: Search query
            file_types: Optional list of file types to filter by
            max_results: Maximum number of results to return

        Returns:
            List of FileSearchResult objects
        """
        # Build file query
        file_query = self.db.query(ProjectFile).filter(
            ProjectFile.project_id == project_id
        )

        if file_types:
            file_query = file_query.filter(ProjectFile.file_type.in_(file_types))

        files = file_query.all()
        results = []

        for file_record in files:
            try:
                # Search in filename
                filename_score = self._calculate_filename_match_score(
                    file_record.file_path, query
                )

                # Search in content
                content = await self.azure_service.download_file(
                    project_id, file_record.file_path
                )
                content_matches = self._search_content(content, query)

                if filename_score > 0 or content_matches:
                    # Get generation info if available
                    generation_query = (
                        self.db.query(CodeGeneration)
                        .join(
                            GeneratedFile,
                            CodeGeneration.id == GeneratedFile.generation_id,
                        )
                        .filter(GeneratedFile.project_file_id == file_record.id)
                        .first()
                    )

                    generation_id = generation_query.id if generation_query else None

                    result = FileSearchResult(
                        file_path=file_record.file_path,
                        file_type=file_record.file_type,
                        size_bytes=file_record.size_bytes,
                        generation_id=generation_id,
                        matches=content_matches,
                        score=filename_score + len(content_matches),
                    )
                    results.append(result)

            except Exception as e:
                # Skip files that can't be processed
                continue

        # Sort by relevance score and limit results
        results.sort(key=lambda x: x.score, reverse=True)
        return results[:max_results]

    def _calculate_filename_match_score(self, file_path: str, query: str) -> float:
        """Calculate relevance score for filename match."""
        filename = Path(file_path).name.lower()
        query_lower = query.lower()

        if query_lower == filename:
            return 10.0
        elif query_lower in filename:
            return 5.0
        elif any(word in filename for word in query_lower.split()):
            return 2.0
        else:
            return 0.0

    def _search_content(self, content: str, query: str) -> List[Dict[str, Any]]:
        """Search for query in file content."""
        matches = []
        lines = content.split("\n")
        query_lower = query.lower()

        for line_num, line in enumerate(lines, 1):
            if query_lower in line.lower():
                # Get context lines
                start_line = max(0, line_num - 2)
                end_line = min(len(lines), line_num + 2)
                context = lines[start_line:end_line]

                match = {
                    "line_number": line_num,
                    "line_content": line.strip(),
                    "context": context,
                    "match_positions": self._find_match_positions(
                        line.lower(), query_lower
                    ),
                }
                matches.append(match)

        return matches

    def _find_match_positions(self, text: str, query: str) -> List[Tuple[int, int]]:
        """Find all positions where query matches in text."""
        positions = []
        start = 0

        while True:
            pos = text.find(query, start)
            if pos == -1:
                break
            positions.append((pos, pos + len(query)))
            start = pos + 1

        return positions
