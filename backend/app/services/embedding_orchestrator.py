"""
Enhanced Embedding Orchestrator for managing the complete embedding workflow.
"""

import asyncio
import time
import uuid
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path

from sqlalchemy.ext.asyncio import AsyncSession

from app.services.llm_summarization_service import LLMSummarizationService, CodeChunk, ChunkSummary
from app.services.monitoring_service import EmbeddingMonitoringService
from app.services.error_handling_service import ComprehensiveErrorHandlingService, create_default_error_handler
from app.services.tree_sitter_service import TreeSitterService
from app.providers.embedding.enhanced_anthropic_provider import EnhancedAnthropicEmbeddingProvider
from app.utils.chunking import TerraformChunker
from app.vectorstores.postgres_store import PostgresVectorStore
from app.core.settings import get_settings
from logconfig.logger import get_logger

logger = get_logger()
settings = get_settings()


class ProcessingStatus(Enum):
    """Status of embedding processing."""
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class ProcessingResult:
    """Result of embedding processing."""
    job_id: str
    status: ProcessingStatus
    files_processed: int = 0
    chunks_created: int = 0
    embeddings_generated: int = 0
    duration_ms: int = 0
    errors: List[Dict[str, Any]] = field(default_factory=list)
    repository_name: Optional[str] = None
    start_time: Optional[float] = None
    end_time: Optional[float] = None


@dataclass
class RepositoryEmbeddingRequest:
    """Request for repository embedding processing."""
    repository_name: str
    repository_path: str
    repository_url: Optional[str] = None
    repository_description: Optional[str] = None
    file_extensions: Optional[List[str]] = None
    max_files: int = 100
    reindex: bool = False
    recursive: bool = True


class EmbeddingOrchestrator:
    """Central orchestrator for embedding workflows with LLM summarization."""

    def __init__(self, db_session: AsyncSession):
        """Initialize the embedding orchestrator."""
        self.db = db_session
        self.job_id = str(uuid.uuid4())

        # Initialize services
        self.summarization_service = LLMSummarizationService(
            api_key=settings.ANTHROPIC_API_KEY
        )
        self.embedding_provider = EnhancedAnthropicEmbeddingProvider(
            api_key=settings.ANTHROPIC_API_KEY
        )
        self.chunker = TerraformChunker()
        self.vector_store = PostgresVectorStore(db_session)
        self.monitoring_service = EmbeddingMonitoringService()
        self.error_handler = create_default_error_handler()
        self.tree_sitter_service = TreeSitterService()

        # Processing configuration
        self.max_concurrent_files = 5
        self.max_concurrent_chunks = 20
        self.batch_size = 100

        # Rate limiting
        self.requests_per_minute = 50
        self.burst_limit = 10
        self._rate_limiter = asyncio.Semaphore(self.requests_per_minute)

        logger.info(f"Initialized EmbeddingOrchestrator with job_id: {self.job_id}")

    async def process_repository(self, request: RepositoryEmbeddingRequest) -> ProcessingResult:
        """
        Orchestrate complete repository embedding workflow.

        Args:
            request: Repository embedding request

        Returns:
            ProcessingResult with comprehensive results
        """
        start_time = time.time()

        # Start monitoring
        await self.monitoring_service.start_monitoring()
        metric_id = self.monitoring_service.record_processing_start(
            "repository_processing",
            {"repository_name": request.repository_name, "job_id": self.job_id}
        )

        result = ProcessingResult(
            job_id=self.job_id,
            status=ProcessingStatus.PROCESSING,
            repository_name=request.repository_name,
            start_time=start_time
        )

        try:
            logger.info(f"Starting repository processing: {request.repository_name}")

            # Validate repository with error handling
            await self.error_handler.execute_with_retry(
                "file_processing",
                self._validate_repository,
                request
            )

            # Discover files with error handling
            files_to_process = await self.error_handler.execute_with_retry(
                "file_processing",
                self._discover_files,
                request
            )
            logger.info(f"Discovered {len(files_to_process)} files to process")

            # Process files with concurrency control and error handling
            semaphore = asyncio.Semaphore(self.max_concurrent_files)

            async def process_file_with_semaphore(file_path: str):
                async with semaphore:
                    return await self.error_handler.execute_with_retry(
                        "file_processing",
                        self._process_single_file,
                        request.repository_name,
                        file_path,
                        request.repository_url,
                        request.repository_description
                    )

            # Process files concurrently
            tasks = [process_file_with_semaphore(file_path) for file_path in files_to_process]
            file_results = await asyncio.gather(*tasks, return_exceptions=True)

            # Aggregate results
            for file_result in file_results:
                if isinstance(file_result, Exception):
                    result.errors.append({
                        "type": "processing_error",
                        "message": str(file_result),
                        "timestamp": time.time()
                    })
                    self.monitoring_service.increment_counter(
                        "file_processing_errors",
                        {"repository": request.repository_name}
                    )
                elif isinstance(file_result, dict):
                    result.files_processed += file_result.get("files_processed", 0)
                    result.chunks_created += file_result.get("chunks_created", 0)
                    result.embeddings_generated += file_result.get("embeddings_generated", 0)
                    if "errors" in file_result:
                        result.errors.extend(file_result["errors"])

            # Update final status
            result.status = ProcessingStatus.COMPLETED
            result.end_time = time.time()
            result.duration_ms = int((result.end_time - start_time) * 1000)

            # Record success
            self.monitoring_service.record_processing_end(metric_id, success=True)

            logger.info(f"Completed repository processing: {result.files_processed} files, "
                       f"{result.chunks_created} chunks, {result.embeddings_generated} embeddings")

        except Exception as e:
            logger.error(f"Repository processing failed: {e}")
            result.status = ProcessingStatus.FAILED
            result.errors.append({
                "type": "orchestrator_error",
                "message": str(e),
                "timestamp": time.time()
            })
            result.end_time = time.time()
            result.duration_ms = int((result.end_time - start_time) * 1000)

            # Record failure
            self.monitoring_service.record_processing_end(metric_id, success=False, error_message=str(e))

        # Stop monitoring
        await self.monitoring_service.stop_monitoring()

        return result

    async def _validate_repository(self, request: RepositoryEmbeddingRequest) -> None:
        """Validate repository exists and is accessible."""
        repo_path = Path(request.repository_path)
        if not repo_path.exists():
            raise ValueError(f"Repository path does not exist: {request.repository_path}")

        if not repo_path.is_dir():
            raise ValueError(f"Repository path is not a directory: {request.repository_path}")

    async def _discover_files(self, request: RepositoryEmbeddingRequest) -> List[str]:
        """Discover files to process in the repository."""
        repo_path = Path(request.repository_path)
        file_extensions = request.file_extensions or list(settings.get_allowed_extensions())

        discovered_files = []

        def should_process_file(file_path: Path) -> bool:
            # Check extension
            if file_extensions and file_path.suffix not in file_extensions:
                return False

            # Skip hidden files and directories
            if any(part.startswith(".") for part in file_path.parts):
                return False

            # Skip common non-code files
            skip_patterns = [".git", "node_modules", "__pycache__", ".terraform"]
            if any(pattern in str(file_path) for pattern in skip_patterns):
                return False

            return True

        # Walk through repository
        if request.recursive:
            for file_path in repo_path.rglob("*"):
                if file_path.is_file() and should_process_file(file_path):
                    discovered_files.append(str(file_path))
        else:
            for file_path in repo_path.iterdir():
                if file_path.is_file() and should_process_file(file_path):
                    discovered_files.append(str(file_path))

        # Limit number of files
        if len(discovered_files) > request.max_files:
            logger.warning(f"Limiting processing to {request.max_files} files out of {len(discovered_files)}")
            discovered_files = discovered_files[:request.max_files]

        return discovered_files

    async def _process_single_file(
        self,
        repository_name: str,
        file_path: str,
        repository_url: Optional[str] = None,
        repository_description: Optional[str] = None
    ) -> Dict[str, Any]:
        """Process a single file through the complete embedding pipeline."""
        try:
            # Read file content
            with open(file_path, "r", encoding="utf-8") as f:
                content = f.read()

            # Parse file with tree-sitter for structured data
            parsed_result = await self.tree_sitter_service.parse_file(file_path)
            parsed_data = parsed_result.content if parsed_result.success else None

            # Calculate file metadata
            file_metadata = self._calculate_file_metadata(file_path, content, parsed_data)

            # Create chunks using parsed data if available
            chunks_data = self.chunker.chunk_terraform_content(
                content=content,
                file_path=file_path,
                parsed_data=parsed_data
            )

            if not chunks_data:
                return {
                    "files_processed": 1,
                    "chunks_created": 0,
                    "embeddings_generated": 0,
                    "errors": [{
                        "type": "chunking_error",
                        "message": "No chunks created",
                        "file_path": file_path
                    }]
                }

            # Convert to CodeChunk objects for summarization
            code_chunks = []
            for i, chunk_data in enumerate(chunks_data):
                code_chunk = CodeChunk(
                    content=chunk_data["content"],
                    file_path=file_path,
                    chunk_index=i,
                    language=chunk_data["metadata"].get("language", "terraform"),
                    metadata=chunk_data["metadata"]
                )
                code_chunks.append(code_chunk)

            # Generate summaries
            logger.info(f"Generating summaries for {len(code_chunks)} chunks")
            summaries = await self.summarization_service.batch_summarize(code_chunks)
            logger.info(f"Generated {len(summaries)} summaries")

            # Filter out failed or empty summaries
            valid_summaries = []
            for i, summary in enumerate(summaries):
                if summary and summary.summary_text and summary.summary_text.strip():
                    valid_summaries.append(summary)
                    logger.debug(f"Valid summary {i}: {summary.summary_text[:100]}...")
                else:
                    logger.warning(f"Skipping empty or failed summary for chunk {i}")

            logger.info(f"Filtered to {len(valid_summaries)} valid summaries")

            # Generate embeddings for both code and summaries
            code_texts = [chunk.content for chunk in code_chunks]
            summary_texts = [summary.summary_text for summary in valid_summaries] if valid_summaries else []

            code_embeddings = self.embedding_provider.embed_texts(code_texts)
            summary_embeddings = self.embedding_provider.embed_texts(summary_texts) if summary_texts else []

            # Store embeddings with dual structure
            await self._store_dual_embeddings(
                repository_name=repository_name,
                file_path=file_path,
                code_chunks=code_chunks,
                summaries=valid_summaries,
                code_embeddings=code_embeddings,
                summary_embeddings=summary_embeddings,
                file_metadata=file_metadata,
                repository_url=repository_url,
                repository_description=repository_description
            )

            logger.info(f"Processed file {file_path}: {len(code_chunks)} chunks, "
                        f"{len(code_embeddings)} code embeddings, {len(summary_embeddings)} summary embeddings")

            return {
                "files_processed": 1,
                "chunks_created": len(code_chunks),
                "embeddings_generated": len(code_embeddings) + len(summary_embeddings),
                "errors": []
            }

        except Exception as e:
            logger.error(f"Failed to process file {file_path}: {e}")
            return {
                "files_processed": 1,
                "chunks_created": 0,
                "embeddings_generated": 0,
                "errors": [{
                    "type": "file_processing_error",
                    "message": str(e),
                    "file_path": file_path
                }]
            }

    async def _store_dual_embeddings(
        self,
        repository_name: str,
        file_path: str,
        code_chunks: List[CodeChunk],
        summaries: List[ChunkSummary],
        code_embeddings: List[List[float]],
        summary_embeddings: List[List[float]],
        file_metadata: Dict[str, Any],
        repository_url: Optional[str] = None,
        repository_description: Optional[str] = None
    ) -> None:
        """Store both code and summary embeddings with relationships."""
        # Prepare summary metadata
        summary_texts = [summary.summary_text for summary in summaries]
        summary_metadata = []

        for i, summary in enumerate(summaries):
            summary_metadata.append({
                "original_content": summary.original_chunk.content,
                "confidence_score": summary.confidence_score,
                "summary_type": summary.summary_type,
                "tokens_count": len(summary.summary_text.split()),
                "processing_metadata": summary.processing_metadata,
                "summarization_model": summary.processing_metadata.get("model", "claude-3-haiku")
            })

        # Store both code and summary embeddings using the enhanced vector store
        await self.vector_store.upsert_file_embedding(
            repository_name=repository_name,
            file_path=file_path,
            vectors=code_embeddings,
            content_chunks=[chunk.content for chunk in code_chunks],
            file_metadata=file_metadata,
            repository_url=repository_url,
            repository_description=repository_description,
            embedding_type="code",
            summary_texts=summary_texts,
            summary_vectors=summary_embeddings,
            summary_metadata=summary_metadata
        )

    def _calculate_file_metadata(self, file_path: str, content: str, parsed_data: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Calculate metadata for a file."""
        import hashlib

        # Calculate SHA-256 hash
        file_hash = hashlib.sha256(content.encode("utf-8")).hexdigest()

        # Detect language from file extension
        file_extension = Path(file_path).suffix.lower()
        language_map = {
            ".py": "python",
            ".js": "javascript",
            ".ts": "typescript",
            ".java": "java",
            ".cpp": "cpp",
            ".c": "c",
            ".h": "c",
            ".go": "go",
            ".rs": "rust",
            ".rb": "ruby",
            ".php": "php",
            ".tf": "terraform",
            ".hcl": "hcl",
        }

        # Determine chunk strategy based on parsing success
        chunk_strategy = "line_based"  # Default fallback
        if parsed_data:
            # Check if parsed data contains meaningful Terraform/HCL structures
            terraform_keys = ['resources', 'variables', 'outputs', 'modules', 'providers', 'data_sources']
            if any(key in parsed_data and parsed_data[key] for key in terraform_keys):
                chunk_strategy = "tree_sitter_based"
            else:
                # Check if we have HCL block patterns
                if 'terraform_blocks' in parsed_data or 'locals' in parsed_data:
                    chunk_strategy = "tree_sitter_based"

        return {
            "size": len(content),
            "hash": file_hash,
            "language": language_map.get(file_extension, "unknown"),
            "tokens_count": len(content.split()),
            "extension": file_extension,
            "chunk_strategy": chunk_strategy
        }

    async def get_processing_status(self, job_id: str) -> Optional[ProcessingResult]:
        """Get the status of a processing job."""
        # In a real implementation, this would query a job status store
        # For now, return None as we don't have persistent job tracking
        return None

    async def cancel_processing(self, job_id: str) -> bool:
        """Cancel a processing job."""
        # Implementation would depend on the job management system
        logger.info(f"Cancelling processing job: {job_id}")
        return True