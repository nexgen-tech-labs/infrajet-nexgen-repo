"""
Knowledge Base Integration for Terraform code generation.

This module provides intelligent knowledge base functionality that extracts,
analyzes, and suggests reusable Terraform patterns from existing repositories.
It integrates with TreeSitterService for parsing and pattern extraction.
"""

import asyncio
import hashlib
import json
from typing import Dict, List, Any, Optional, Tuple, Set
from dataclasses import dataclass, field
from pathlib import Path
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.tree_sitter_service import TreeSitterService
from app.vectorstores.postgres_store import PostgresVectorStore
from app.services.code_generation.rag.retriever import RetrievedDocument
from logconfig.logger import get_logger

logger = get_logger()


@dataclass
class TerraformPattern:
    """Represents a reusable Terraform pattern."""
    pattern_id: str
    pattern_type: str  # "resource", "module", "data_source", "variable", "output"
    resource_type: Optional[str] = None  # e.g., "aws_instance", "azurerm_virtual_machine"
    code_snippet: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)
    usage_count: int = 0
    confidence_score: float = 0.0
    tags: List[str] = field(default_factory=list)
    dependencies: List[str] = field(default_factory=list)


@dataclass
class PatternMatch:
    """Result of pattern matching against a query."""
    pattern: TerraformPattern
    similarity_score: float
    matched_terms: List[str] = field(default_factory=list)
    context_relevance: float = 0.0


@dataclass
class KnowledgeBaseResult:
    """Result from knowledge base query."""
    query: str
    matched_patterns: List[PatternMatch] = field(default_factory=list)
    suggested_patterns: List[TerraformPattern] = field(default_factory=list)
    processing_time_ms: float = 0.0
    total_patterns_searched: int = 0


class KnowledgeBase:
    """
    Intelligent knowledge base for Terraform patterns.

    This class extracts, stores, and retrieves reusable Terraform patterns
    from existing repositories using TreeSitter parsing and vector similarity.
    """

    def __init__(self, db_session: AsyncSession):
        """
        Initialize the knowledge base.

        Args:
            db_session: Database session for pattern storage
        """
        self.db = db_session
        self.tree_sitter_service = TreeSitterService()
        self.vector_store = PostgresVectorStore(db_session)

        # Pattern storage
        self.patterns: Dict[str, TerraformPattern] = {}
        self.pattern_index: Dict[str, List[str]] = {}  # term -> pattern_ids

        # Caching
        self.pattern_cache: Dict[str, List[PatternMatch]] = {}
        self.cache_ttl = 3600  # 1 hour

        # Configuration
        self.min_pattern_length = 50  # Minimum characters for a pattern
        self.max_patterns_per_type = 100
        self.similarity_threshold = 0.6

        logger.info("KnowledgeBase initialized")

    async def extract_patterns_from_repository(
        self,
        repository_name: str,
        repository_path: str
    ) -> Dict[str, int]:
        """
        Extract reusable patterns from a Terraform repository.

        Args:
            repository_name: Name of the repository
            repository_path: Path to the repository

        Returns:
            Dictionary with extraction statistics
        """
        try:
            logger.info(f"Extracting patterns from repository: {repository_name}")

            # Discover Terraform files
            tf_files = await self._discover_terraform_files(repository_path)

            # Extract patterns from each file
            extracted_patterns = []
            for file_path in tf_files:
                patterns = await self._extract_patterns_from_file(
                    repository_name, file_path
                )
                extracted_patterns.extend(patterns)

            # Store patterns
            stored_count = await self._store_patterns(extracted_patterns)

            # Update pattern index
            await self._update_pattern_index(extracted_patterns)

            stats = {
                "files_processed": len(tf_files),
                "patterns_extracted": len(extracted_patterns),
                "patterns_stored": stored_count,
                "repository": repository_name
            }

            logger.info(f"Pattern extraction completed: {stats}")
            return stats

        except Exception as e:
            logger.error(f"Pattern extraction failed for {repository_name}: {e}")
            return {"error": str(e), "files_processed": 0, "patterns_extracted": 0}

    async def _discover_terraform_files(self, repository_path: str) -> List[str]:
        """
        Discover Terraform files in the repository.

        Args:
            repository_path: Path to the repository

        Returns:
            List of Terraform file paths
        """
        tf_extensions = [".tf", ".hcl"]
        discovered_files = []

        repo_path = Path(repository_path)
        if not repo_path.exists():
            return discovered_files

        for file_path in repo_path.rglob("*"):
            if file_path.is_file() and file_path.suffix in tf_extensions:
                # Skip common non-infrastructure files
                if any(skip in str(file_path) for skip in [".terraform", "modules"]):
                    continue
                discovered_files.append(str(file_path))

        return discovered_files

    async def _extract_patterns_from_file(
        self,
        repository_name: str,
        file_path: str
    ) -> List[TerraformPattern]:
        """
        Extract patterns from a single Terraform file.

        Args:
            repository_name: Name of the repository
            file_path: Path to the Terraform file

        Returns:
            List of extracted patterns
        """
        patterns = []

        try:
            # Parse the file with TreeSitter
            parse_result = await self.tree_sitter_service.parse_file(file_path)

            if not parse_result.success or not parse_result.content:
                return patterns

            content = parse_result.content

            # Extract resource patterns
            if "resources" in content:
                resource_patterns = await self._extract_resource_patterns(
                    content["resources"], repository_name, file_path
                )
                patterns.extend(resource_patterns)

            # Extract module patterns
            if "modules" in content:
                module_patterns = await self._extract_module_patterns(
                    content["modules"], repository_name, file_path
                )
                patterns.extend(module_patterns)

            # Extract data source patterns
            if "data_sources" in content:
                data_patterns = await self._extract_data_source_patterns(
                    content["data_sources"], repository_name, file_path
                )
                patterns.extend(data_patterns)

            # Extract variable patterns
            if "variables" in content:
                variable_patterns = await self._extract_variable_patterns(
                    content["variables"], repository_name, file_path
                )
                patterns.extend(variable_patterns)

        except Exception as e:
            logger.warning(f"Failed to extract patterns from {file_path}: {e}")

        return patterns

    async def _extract_resource_patterns(
        self,
        resources: List[Dict[str, Any]],
        repository_name: str,
        file_path: str
    ) -> List[TerraformPattern]:
        """Extract resource patterns from parsed resources."""
        patterns = []

        for resource in resources:
            try:
                resource_type = resource.get("type", "")
                resource_name = resource.get("name", "")

                # Generate pattern ID
                pattern_id = self._generate_pattern_id(
                    "resource", resource_type, resource_name, file_path
                )

                # Create code snippet
                code_snippet = self._create_resource_snippet(resource)

                if len(code_snippet) < self.min_pattern_length:
                    continue

                # Extract metadata
                metadata = {
                    "resource_type": resource_type,
                    "resource_name": resource_name,
                    "file_path": file_path,
                    "repository": repository_name,
                    "attributes": list(resource.get("attributes", {}).keys()),
                    "blocks": list(resource.get("blocks", {}).keys())
                }

                # Extract tags
                tags = await self._extract_pattern_tags(resource, "resource")

                pattern = TerraformPattern(
                    pattern_id=pattern_id,
                    pattern_type="resource",
                    resource_type=resource_type,
                    code_snippet=code_snippet,
                    metadata=metadata,
                    tags=tags,
                    confidence_score=0.8  # Base confidence for extracted patterns
                )

                patterns.append(pattern)

            except Exception as e:
                logger.warning(f"Failed to extract resource pattern: {e}")

        return patterns

    async def _extract_module_patterns(
        self,
        modules: List[Dict[str, Any]],
        repository_name: str,
        file_path: str
    ) -> List[TerraformPattern]:
        """Extract module patterns from parsed modules."""
        patterns = []

        for module in modules:
            try:
                module_name = module.get("name", "")
                source = module.get("source", "")

                pattern_id = self._generate_pattern_id(
                    "module", module_name, source, file_path
                )

                code_snippet = self._create_module_snippet(module)

                if len(code_snippet) < self.min_pattern_length:
                    continue

                metadata = {
                    "module_name": module_name,
                    "source": source,
                    "file_path": file_path,
                    "repository": repository_name,
                    "inputs": list(module.get("inputs", {}).keys())
                }

                tags = await self._extract_pattern_tags(module, "module")

                pattern = TerraformPattern(
                    pattern_id=pattern_id,
                    pattern_type="module",
                    code_snippet=code_snippet,
                    metadata=metadata,
                    tags=tags,
                    confidence_score=0.7
                )

                patterns.append(pattern)

            except Exception as e:
                logger.warning(f"Failed to extract module pattern: {e}")

        return patterns

    async def _extract_data_source_patterns(
        self,
        data_sources: List[Dict[str, Any]],
        repository_name: str,
        file_path: str
    ) -> List[TerraformPattern]:
        """Extract data source patterns from parsed data sources."""
        patterns = []

        for ds in data_sources:
            try:
                ds_type = ds.get("type", "")
                ds_name = ds.get("name", "")

                pattern_id = self._generate_pattern_id(
                    "data_source", ds_type, ds_name, file_path
                )

                code_snippet = self._create_data_source_snippet(ds)

                if len(code_snippet) < self.min_pattern_length:
                    continue

                metadata = {
                    "data_source_type": ds_type,
                    "data_source_name": ds_name,
                    "file_path": file_path,
                    "repository": repository_name,
                    "attributes": list(ds.get("attributes", {}).keys())
                }

                tags = await self._extract_pattern_tags(ds, "data_source")

                pattern = TerraformPattern(
                    pattern_id=pattern_id,
                    pattern_type="data_source",
                    resource_type=ds_type,
                    code_snippet=code_snippet,
                    metadata=metadata,
                    tags=tags,
                    confidence_score=0.6
                )

                patterns.append(pattern)

            except Exception as e:
                logger.warning(f"Failed to extract data source pattern: {e}")

        return patterns

    async def _extract_variable_patterns(
        self,
        variables: List[Dict[str, Any]],
        repository_name: str,
        file_path: str
    ) -> List[TerraformPattern]:
        """Extract variable patterns from parsed variables."""
        patterns = []

        for var in variables:
            try:
                var_name = var.get("name", "")
                var_type = var.get("type", "string")

                pattern_id = self._generate_pattern_id(
                    "variable", var_name, var_type, file_path
                )

                code_snippet = self._create_variable_snippet(var)

                if len(code_snippet) < self.min_pattern_length:
                    continue

                metadata = {
                    "variable_name": var_name,
                    "variable_type": var_type,
                    "file_path": file_path,
                    "repository": repository_name,
                    "has_default": "default" in var,
                    "has_validation": "validation" in var
                }

                tags = await self._extract_pattern_tags(var, "variable")

                pattern = TerraformPattern(
                    pattern_id=pattern_id,
                    pattern_type="variable",
                    code_snippet=code_snippet,
                    metadata=metadata,
                    tags=tags,
                    confidence_score=0.5
                )

                patterns.append(pattern)

            except Exception as e:
                logger.warning(f"Failed to extract variable pattern: {e}")

        return patterns

    def _generate_pattern_id(self, *components: str) -> str:
        """Generate a unique pattern ID from components."""
        content = "_".join(str(c) for c in components if c)
        return hashlib.md5(content.encode()).hexdigest()[:16]

    def _create_resource_snippet(self, resource: Dict[str, Any]) -> str:
        """Create a code snippet for a resource pattern."""
        resource_type = resource.get("type", "")
        resource_name = resource.get("name", "")

        snippet = f'resource "{resource_type}" "{resource_name}" {{\n'

        # Add key attributes (limit to avoid overly long snippets)
        attributes = resource.get("attributes", {})
        for key, value in list(attributes.items())[:5]:  # Limit attributes
            if isinstance(value, str):
                snippet += f'  {key} = "{value}"\n'
            else:
                snippet += f'  {key} = {value}\n'

        snippet += '}'
        return snippet

    def _create_module_snippet(self, module: Dict[str, Any]) -> str:
        """Create a code snippet for a module pattern."""
        module_name = module.get("name", "")
        source = module.get("source", "")

        snippet = f'module "{module_name}" {{\n'
        snippet += f'  source = "{source}"\n'

        # Add key inputs
        inputs = module.get("inputs", {})
        for key, value in list(inputs.items())[:3]:  # Limit inputs
            if isinstance(value, str):
                snippet += f'  {key} = "{value}"\n'
            else:
                snippet += f'  {key} = {value}\n'

        snippet += '}'
        return snippet

    def _create_data_source_snippet(self, ds: Dict[str, Any]) -> str:
        """Create a code snippet for a data source pattern."""
        ds_type = ds.get("type", "")
        ds_name = ds.get("name", "")

        snippet = f'data "{ds_type}" "{ds_name}" {{\n'

        # Add key attributes
        attributes = ds.get("attributes", {})
        for key, value in list(attributes.items())[:3]:
            if isinstance(value, str):
                snippet += f'  {key} = "{value}"\n'
            else:
                snippet += f'  {key} = {value}\n'

        snippet += '}'
        return snippet

    def _create_variable_snippet(self, var: Dict[str, Any]) -> str:
        """Create a code snippet for a variable pattern."""
        var_name = var.get("name", "")
        var_type = var.get("type", "string")

        snippet = f'variable "{var_name}" {{\n'
        snippet += f'  type = {var_type}\n'

        if "default" in var:
            default = var["default"]
            if isinstance(default, str):
                snippet += f'  default = "{default}"\n'
            else:
                snippet += f'  default = {default}\n'

        if "description" in var:
            snippet += f'  description = "{var["description"]}"\n'

        snippet += '}'
        return snippet

    async def _extract_pattern_tags(self, item: Dict[str, Any], pattern_type: str) -> List[str]:
        """Extract relevant tags from a pattern item."""
        tags = []

        # Add pattern type
        tags.append(pattern_type)

        # Add resource/data source type
        if "type" in item:
            tags.append(item["type"])

        # Add provider prefix if available
        if "type" in item and "_" in item["type"]:
            provider = item["type"].split("_")[0]
            tags.append(provider)

        # Add common tags based on attributes
        attributes = item.get("attributes", {})
        if "tags" in attributes:
            tags.extend(["tagged", "metadata"])
        if "security_groups" in attributes or "vpc_id" in attributes:
            tags.append("networking")
        if "instance_type" in attributes or "vm_size" in attributes:
            tags.append("compute")

        return list(set(tags))  # Remove duplicates

    async def _store_patterns(self, patterns: List[TerraformPattern]) -> int:
        """Store patterns in memory (could be extended to persistent storage)."""
        stored_count = 0

        for pattern in patterns:
            if pattern.pattern_id not in self.patterns:
                self.patterns[pattern.pattern_id] = pattern
                stored_count += 1
            else:
                # Update usage count for existing patterns
                self.patterns[pattern.pattern_id].usage_count += 1

        return stored_count

    async def _update_pattern_index(self, patterns: List[TerraformPattern]):
        """Update the pattern index for fast lookup."""
        for pattern in patterns:
            # Index by tags
            for tag in pattern.tags:
                if tag not in self.pattern_index:
                    self.pattern_index[tag] = []
                if pattern.pattern_id not in self.pattern_index[tag]:
                    self.pattern_index[tag].append(pattern.pattern_id)

            # Index by resource type
            if pattern.resource_type:
                resource_key = f"resource:{pattern.resource_type}"
                if resource_key not in self.pattern_index:
                    self.pattern_index[resource_key] = []
                if pattern.pattern_id not in self.pattern_index[resource_key]:
                    self.pattern_index[resource_key].append(pattern.pattern_id)

    async def find_matching_patterns(
        self,
        query: str,
        pattern_types: Optional[List[str]] = None,
        max_results: int = 10
    ) -> KnowledgeBaseResult:
        """
        Find patterns that match the given query.

        Args:
            query: Search query
            pattern_types: Optional filter by pattern types
            max_results: Maximum number of results to return

        Returns:
            KnowledgeBaseResult with matched patterns
        """
        import time
        start_time = time.time()

        result = KnowledgeBaseResult(query=query)

        try:
            # Check cache first
            cache_key = f"{query}_{pattern_types}_{max_results}"
            if cache_key in self.pattern_cache:
                cached_result = self.pattern_cache[cache_key]
                result.matched_patterns = cached_result
                result.total_patterns_searched = len(self.patterns)
                result.processing_time_ms = (time.time() - start_time) * 1000
                return result

            # Tokenize query
            query_terms = self._tokenize_query(query.lower())

            # Find matching patterns
            matches = []
            searched_patterns = 0

            for pattern_id, pattern in self.patterns.items():
                searched_patterns += 1

                # Filter by pattern type if specified
                if pattern_types and pattern.pattern_type not in pattern_types:
                    continue

                # Calculate similarity
                similarity_score = self._calculate_pattern_similarity(pattern, query_terms)

                if similarity_score >= self.similarity_threshold:
                    matched_terms = self._find_matched_terms(pattern, query_terms)

                    match = PatternMatch(
                        pattern=pattern,
                        similarity_score=similarity_score,
                        matched_terms=matched_terms,
                        context_relevance=self._calculate_context_relevance(pattern, query_terms)
                    )
                    matches.append(match)

            # Sort by similarity score
            matches.sort(key=lambda x: x.similarity_score, reverse=True)

            # Limit results
            result.matched_patterns = matches[:max_results]
            result.total_patterns_searched = searched_patterns

            # Cache results
            self.pattern_cache[cache_key] = result.matched_patterns

            result.processing_time_ms = (time.time() - start_time) * 1000

            logger.info(
                f"Found {len(result.matched_patterns)} matching patterns "
                f"for query '{query}' in {result.processing_time_ms:.2f}ms"
            )

        except Exception as e:
            logger.error(f"Pattern matching failed: {e}")
            result.processing_time_ms = (time.time() - start_time) * 1000

        return result

    def _tokenize_query(self, query: str) -> List[str]:
        """Tokenize the search query into terms."""
        import re

        # Split on whitespace and punctuation
        terms = re.findall(r'\b\w+\b', query)

        # Add bigrams for better matching
        bigrams = []
        for i in range(len(terms) - 1):
            bigrams.append(f"{terms[i]}_{terms[i+1]}")

        return terms + bigrams

    def _calculate_pattern_similarity(
        self,
        pattern: TerraformPattern,
        query_terms: List[str]
    ) -> float:
        """Calculate similarity between pattern and query terms."""
        score = 0.0
        total_weight = 0.0

        # Check tags (high weight)
        tag_matches = sum(1 for term in query_terms if term in pattern.tags)
        if pattern.tags:
            score += (tag_matches / len(pattern.tags)) * 0.4
        total_weight += 0.4

        # Check resource type (high weight)
        if pattern.resource_type:
            type_matches = sum(1 for term in query_terms
                             if term in pattern.resource_type.lower())
            score += (type_matches / len(query_terms)) * 0.3
        total_weight += 0.3

        # Check code snippet content (medium weight)
        snippet_text = pattern.code_snippet.lower()
        snippet_matches = sum(1 for term in query_terms if term in snippet_text)
        score += (snippet_matches / len(query_terms)) * 0.2
        total_weight += 0.2

        # Check metadata (low weight)
        metadata_text = json.dumps(pattern.metadata).lower()
        metadata_matches = sum(1 for term in query_terms if term in metadata_text)
        score += (metadata_matches / len(query_terms)) * 0.1
        total_weight += 0.1

        return score / total_weight if total_weight > 0 else 0.0

    def _find_matched_terms(
        self,
        pattern: TerraformPattern,
        query_terms: List[str]
    ) -> List[str]:
        """Find which query terms matched the pattern."""
        matched = []

        # Check tags
        for term in query_terms:
            if term in pattern.tags:
                matched.append(f"tag:{term}")

        # Check resource type
        if pattern.resource_type:
            for term in query_terms:
                if term in pattern.resource_type.lower():
                    matched.append(f"type:{term}")

        # Check code content
        snippet_lower = pattern.code_snippet.lower()
        for term in query_terms:
            if term in snippet_lower:
                matched.append(f"content:{term}")

        return list(set(matched))  # Remove duplicates

    def _calculate_context_relevance(
        self,
        pattern: TerraformPattern,
        query_terms: List[str]
    ) -> float:
        """Calculate context relevance score."""
        # Simple relevance based on usage count and confidence
        usage_score = min(pattern.usage_count / 10.0, 1.0)  # Cap at 10 uses
        confidence_score = pattern.confidence_score

        return (usage_score + confidence_score) / 2.0

    async def get_pattern_suggestions(
        self,
        context: Dict[str, Any],
        max_suggestions: int = 5
    ) -> List[TerraformPattern]:
        """
        Get pattern suggestions based on context.

        Args:
            context: Context information (e.g., current resource type, provider)
            max_suggestions: Maximum number of suggestions to return

        Returns:
            List of suggested patterns
        """
        suggestions = []

        try:
            # Find patterns by resource type
            if "resource_type" in context:
                resource_type = context["resource_type"]
                pattern_ids = self.pattern_index.get(f"resource:{resource_type}", [])

                for pattern_id in pattern_ids[:max_suggestions]:
                    if pattern_id in self.patterns:
                        suggestions.append(self.patterns[pattern_id])

            # Find patterns by tags
            if "tags" in context:
                for tag in context["tags"]:
                    if tag in self.pattern_index:
                        for pattern_id in self.pattern_index[tag]:
                            if pattern_id in self.patterns:
                                pattern = self.patterns[pattern_id]
                                if pattern not in suggestions:
                                    suggestions.append(pattern)

                                if len(suggestions) >= max_suggestions:
                                    break

                    if len(suggestions) >= max_suggestions:
                        break

            # Sort by usage count and confidence
            suggestions.sort(
                key=lambda x: (x.usage_count, x.confidence_score),
                reverse=True
            )

            return suggestions[:max_suggestions]

        except Exception as e:
            logger.error(f"Failed to get pattern suggestions: {e}")
            return []

    async def get_knowledge_base_stats(self) -> Dict[str, Any]:
        """
        Get statistics about the knowledge base.

        Returns:
            Dictionary with knowledge base statistics
        """
        try:
            pattern_types = {}
            resource_types = {}
            total_usage = 0

            for pattern in self.patterns.values():
                # Count pattern types
                pattern_types[pattern.pattern_type] = pattern_types.get(pattern.pattern_type, 0) + 1

                # Count resource types
                if pattern.resource_type:
                    resource_types[pattern.resource_type] = resource_types.get(pattern.resource_type, 0) + 1

                # Sum usage
                total_usage += pattern.usage_count

            return {
                "total_patterns": len(self.patterns),
                "pattern_types": pattern_types,
                "resource_types": resource_types,
                "total_usage_count": total_usage,
                "cache_size": len(self.pattern_cache),
                "index_size": len(self.pattern_index)
            }

        except Exception as e:
            logger.error(f"Failed to get knowledge base stats: {e}")
            return {"error": str(e)}