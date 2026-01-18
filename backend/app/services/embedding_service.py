"""
Embedding service for managing file embeddings in PostgreSQL.
"""

import hashlib
import os
from typing import List, Dict, Any, Optional, Tuple
from pathlib import Path

from sqlalchemy.ext.asyncio import AsyncSession
from anthropic import Anthropic

from app.vectorstores.postgres_store import PostgresVectorStore
from app.core.config import get_settings
from logconfig.logger import get_logger

logger = get_logger()
settings = get_settings()


class EmbeddingService:
    """Service for managing file embeddings."""

    def __init__(self, db_session: AsyncSession):
        """Initialize the embedding service."""
        self.db = db_session
        self.vector_store = PostgresVectorStore(db_session)
        self.anthropic_client = Anthropic(api_key=settings.ANTHROPIC_API_KEY)
        self.embedding_model = settings.EMBEDDING_MODEL
        self.max_chunk_tokens = settings.MAX_CHUNK_TOKENS
        self.overlap_tokens = settings.OVERLAP_TOKENS

    async def embed_file(
        self,
        repository_name: str,
        file_path: str,
        content: str,
        repository_url: Optional[str] = None,
        repository_description: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Embed a single file and store in the database.

        Args:
            repository_name: Name of the repository
            file_path: Path to the file within the repository
            content: File content to embed
            repository_url: Optional repository URL
            repository_description: Optional repository description

        Returns:
            Dictionary with embedding results
        """
        try:
            # Calculate file metadata
            file_metadata = self._calculate_file_metadata(file_path, content)

            # Split content into chunks
            chunks = self._split_content(content)

            # Generate embeddings for each chunk
            embeddings = []
            for chunk in chunks:
                embedding = await self._generate_embedding(chunk)
                embeddings.append(embedding)

            # Store embeddings in database
            await self.vector_store.upsert_file_embedding(
                repository_name=repository_name,
                file_path=file_path,
                vectors=embeddings,
                content_chunks=chunks,
                file_metadata=file_metadata,
                repository_url=repository_url,
                repository_description=repository_description,
            )

            logger.info(
                f"Successfully embedded file {file_path} with {len(chunks)} chunks"
            )

            return {
                "file_path": file_path,
                "repository_name": repository_name,
                "chunks_count": len(chunks),
                "embedding_dimension": len(embeddings[0]) if embeddings else 0,
                "file_size": len(content),
                "file_hash": file_metadata["hash"],
            }

        except Exception as e:
            logger.error(f"Failed to embed file {file_path}: {e}")
            raise

    async def embed_repository(
        self,
        repository_name: str,
        repository_path: str,
        repository_url: Optional[str] = None,
        repository_description: Optional[str] = None,
        file_extensions: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """
        Embed all files in a repository.

        Args:
            repository_name: Name of the repository
            repository_path: Local path to the repository
            repository_url: Optional repository URL
            repository_description: Optional repository description
            file_extensions: List of file extensions to include (e.g., ['.py', '.js'])

        Returns:
            Dictionary with embedding results
        """
        if file_extensions is None:
            file_extensions = list(settings.get_allowed_extensions())

        try:
            repo_path = Path(repository_path)
            if not repo_path.exists():
                raise ValueError(f"Repository path does not exist: {repository_path}")

            embedded_files = []
            skipped_files = []

            # Walk through all files in the repository
            for file_path in repo_path.rglob("*"):
                if file_path.is_file():
                    # Check if file extension is allowed
                    if file_extensions and file_path.suffix not in file_extensions:
                        continue

                    # Skip hidden files and directories
                    if any(part.startswith(".") for part in file_path.parts):
                        continue

                    try:
                        # Read file content
                        with open(file_path, "r", encoding="utf-8") as f:
                            content = f.read()

                        # Get relative path from repository root
                        relative_path = str(file_path.relative_to(repo_path))

                        # Embed the file
                        result = await self.embed_file(
                            repository_name=repository_name,
                            file_path=relative_path,
                            content=content,
                            repository_url=repository_url,
                            repository_description=repository_description,
                        )

                        embedded_files.append(result)

                    except Exception as e:
                        logger.warning(f"Skipped file {file_path}: {e}")
                        skipped_files.append(str(file_path))

            logger.info(
                f"Embedded repository {repository_name}: {len(embedded_files)} files processed, {len(skipped_files)} skipped"
            )

            return {
                "repository_name": repository_name,
                "embedded_files": len(embedded_files),
                "skipped_files": len(skipped_files),
                "files": embedded_files,
            }

        except Exception as e:
            logger.error(f"Failed to embed repository {repository_name}: {e}")
            raise

    async def search_similar_code(
        self,
        query: str,
        top_k: int = 5,
        threshold: float = 0.7,
        repository_name: Optional[str] = None,
        file_extensions: Optional[List[str]] = None,
    ) -> List[Dict[str, Any]]:
        """
        Search for similar code chunks.

        Args:
            query: Search query
            top_k: Number of results to return
            threshold: Minimum similarity threshold
            repository_name: Optional filter by repository
            file_extensions: Optional filter by file extensions

        Returns:
            List of similar code chunks with metadata
        """
        try:
            # Generate embedding for the query
            query_embedding = await self._generate_embedding(query)

            # Search in vector store
            results = await self.vector_store.search_similar_files(
                query_vector=query_embedding,
                top_k=top_k,
                threshold=threshold,
                repository_name=repository_name,
                file_extensions=file_extensions,
            )

            # Format results
            formatted_results = []
            for metadata, similarity in results:
                formatted_results.append(
                    {
                        "similarity": similarity,
                        "file_path": metadata["file_path"],
                        "repository_name": metadata["repository_name"],
                        "content_chunk": metadata["content_chunk"],
                        "chunk_index": metadata["chunk_index"],
                        "total_chunks": metadata["total_chunks"],
                        "language": metadata["language"],
                        "file_extension": metadata["file_extension"],
                        "created_at": metadata["created_at"],
                    }
                )

            return formatted_results

        except Exception as e:
            logger.error(f"Failed to search similar code: {e}")
            raise

    async def delete_repository(self, repository_name: str) -> None:
        """Delete all embeddings for a repository."""
        try:
            await self.vector_store.delete_repository_embeddings(repository_name)
            logger.info(f"Deleted embeddings for repository {repository_name}")
        except Exception as e:
            logger.error(f"Failed to delete repository {repository_name}: {e}")
            raise

    async def get_repository_stats(
        self, repository_name: Optional[str] = None
    ) -> Dict[str, Any]:
        """Get statistics about embeddings."""
        try:
            return await self.vector_store.get_repository_stats(repository_name)
        except Exception as e:
            logger.error(f"Failed to get repository stats: {e}")
            raise

    def _calculate_file_metadata(self, file_path: str, content: str) -> Dict[str, Any]:
        """Calculate metadata for a file."""
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

        return {
            "size": len(content),
            "hash": file_hash,
            "language": language_map.get(file_extension, "unknown"),
            "tokens_count": len(content.split()),  # Simple token count
        }

    def _split_content(self, content: str) -> List[str]:
        """Split content into chunks for embedding."""
        # Simple chunking by lines - can be improved with more sophisticated methods
        lines = content.split("\n")
        chunks = []
        current_chunk = []
        current_tokens = 0

        for line in lines:
            line_tokens = len(line.split())

            if current_tokens + line_tokens > self.max_chunk_tokens and current_chunk:
                # Save current chunk
                chunks.append("\n".join(current_chunk))

                # Start new chunk with overlap
                overlap_lines = (
                    current_chunk[-self.overlap_tokens :]
                    if len(current_chunk) > self.overlap_tokens
                    else current_chunk
                )
                current_chunk = overlap_lines + [line]
                current_tokens = sum(len(l.split()) for l in current_chunk)
            else:
                current_chunk.append(line)
                current_tokens += line_tokens

        # Add the last chunk
        if current_chunk:
            chunks.append("\n".join(current_chunk))

        return chunks if chunks else [content]

    async def _generate_embedding(self, text: str) -> List[float]:
        """Generate embedding for text using Anthropic."""
        try:
            # For now, we'll use a simple approach - in production, you might want to use
            # a dedicated embedding model or service
            # This is a placeholder - Anthropic doesn't provide embeddings directly
            # You would typically use OpenAI embeddings, Sentence Transformers, or similar

            # For demonstration, we'll create a simple hash-based embedding
            # In production, replace this with actual embedding generation
            import numpy as np

            # Create a deterministic "embedding" based on text hash
            text_hash = hashlib.md5(text.encode()).hexdigest()
            # Convert hex to numbers and normalize
            embedding = []
            for i in range(0, len(text_hash), 2):
                hex_pair = text_hash[i : i + 2]
                embedding.append(int(hex_pair, 16) / 255.0)

            # Pad or truncate to desired dimension
            target_dim = settings.EMBEDDING_DIMENSION
            if len(embedding) < target_dim:
                embedding.extend([0.0] * (target_dim - len(embedding)))
            else:
                embedding = embedding[:target_dim]

            # Normalize the vector
            embedding = np.array(embedding, dtype=np.float32)
            norm = np.linalg.norm(embedding)
            if norm > 0:
                embedding = embedding / norm

            return embedding.tolist()

        except Exception as e:
            logger.error(f"Failed to generate embedding: {e}")
            raise
