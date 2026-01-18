"""
PostgreSQL-based vector store implementation using pgvector extension.
"""

from typing import List, Dict, Any, Optional, Tuple
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy import func, text, and_, or_
from sqlalchemy.orm import selectinload

from app.vectorstores.base import VectorStore
from app.models.embedding import Repository, FileEmbedding
from logconfig.logger import get_logger

logger = get_logger()


class PostgresVectorStore(VectorStore):
    """PostgreSQL-based vector store for embedding storage and retrieval."""

    def __init__(
        self, db_session: AsyncSession, embedding_model: str = "claude-3-haiku-20240307"
    ):
        """
        Initialize PostgreSQL vector store.

        Args:
            db_session: Async database session
            embedding_model: Name of the embedding model used
        """
        self.db = db_session
        self.embedding_model = embedding_model

    async def upsert_file_embedding(
        self,
        repository_name: str,
        file_path: str,
        vectors: List[List[float]],
        content_chunks: List[str],
        file_metadata: Dict[str, Any],
        repository_url: Optional[str] = None,
        repository_description: Optional[str] = None,
        embedding_type: str = "code",
        summary_texts: Optional[List[str]] = None,
        summary_vectors: Optional[List[List[float]]] = None,
        summary_metadata: Optional[List[Dict[str, Any]]] = None,
    ) -> None:
        """
        Insert or update file embeddings with metadata.

        Args:
            repository_name: Name of the repository
            file_path: Path to the file within the repository
            vectors: List of embedding vectors (one per chunk)
            content_chunks: List of content chunks corresponding to vectors
            file_metadata: Metadata about the file (size, hash, extension, etc.)
            repository_url: Optional repository URL
            repository_description: Optional repository description
        """
        if not vectors or not content_chunks:
            return

        if len(vectors) != len(content_chunks):
            raise ValueError("Number of vectors must match number of content chunks")

        try:
            # Get or create repository
            repository = await self._get_or_create_repository(
                repository_name, repository_url, repository_description
            )

            # Remove existing embeddings for this file
            await self._remove_file_embeddings(repository.id, file_path)

            # Create new embeddings
            file_name = file_path.split("/")[-1]
            file_extension = file_name.split(".")[-1] if "." in file_name else None

            # Store code embeddings
            for chunk_index, (vector, content_chunk) in enumerate(
                zip(vectors, content_chunks)
            ):
                embedding = FileEmbedding(
                    file_path=file_path,
                    file_name=file_name,
                    file_extension=file_extension,
                    file_size=file_metadata.get("size"),
                    file_hash=file_metadata.get("hash"),
                    repository_id=repository.id,
                    content_chunk=content_chunk,
                    chunk_index=chunk_index,
                    total_chunks=len(content_chunks),
                    embedding_vector=vector,
                    embedding_model=self.embedding_model,
                    embedding_dimension=len(vector),
                    embedding_type=embedding_type,
                    language=file_metadata.get("language"),
                    tokens_count=file_metadata.get("tokens_count"),
                    chunk_strategy=file_metadata.get("chunk_strategy", "line_based"),
                )
                self.db.add(embedding)

            # Store summary embeddings if provided
            if summary_texts and summary_vectors and summary_metadata:
                for chunk_index, (summary_vector, summary_text, summary_meta) in enumerate(
                    zip(summary_vectors, summary_texts, summary_metadata)
                ):
                    summary_embedding = FileEmbedding(
                        file_path=file_path,
                        file_name=file_name,
                        file_extension=file_extension,
                        file_size=file_metadata.get("size"),
                        file_hash=file_metadata.get("hash"),
                        repository_id=repository.id,
                        content_chunk=summary_meta.get("original_content", ""),
                        chunk_index=chunk_index,
                        total_chunks=len(summary_texts),
                        embedding_vector=summary_vector,
                        embedding_model=self.embedding_model,
                        embedding_dimension=len(summary_vector),
                        embedding_type="summary",
                        summary_text=summary_text,
                        summary_embedding_vector=summary_vector,
                        summary_confidence=summary_meta.get("confidence_score"),
                        summary_type=summary_meta.get("summary_type"),
                        language=file_metadata.get("language"),
                        tokens_count=summary_meta.get("tokens_count"),
                        processing_metadata=summary_meta.get("processing_metadata"),
                        summarization_model=summary_meta.get("summarization_model"),
                        chunk_strategy=file_metadata.get("chunk_strategy", "line_based"),
                    )
                    self.db.add(summary_embedding)

            await self.db.commit()

            total_embeddings = len(vectors)
            if summary_vectors:
                total_embeddings += len(summary_vectors)

            logger.info(
                f"Upserted {total_embeddings} embeddings ({len(vectors)} code, "
                f"{len(summary_vectors) if summary_vectors else 0} summary) "
                f"for file {file_path} in repository {repository_name}"
            )

        except Exception as e:
            await self.db.rollback()
            logger.error(f"Failed to upsert embeddings for {file_path}: {e}")
            raise

    async def _get_or_create_repository(
        self, name: str, url: Optional[str] = None, description: Optional[str] = None
    ) -> Repository:
        """Get existing repository or create a new one."""
        # Try to find existing repository
        result = await self.db.execute(
            select(Repository).where(Repository.name == name)
        )
        repository = result.scalars().first()

        if not repository:
            repository = Repository(name=name, url=url, description=description)
            self.db.add(repository)
            await self.db.flush()  # Get the ID without committing

        return repository

    async def _remove_file_embeddings(self, repository_id: int, file_path: str) -> None:
        """Remove existing embeddings for a specific file."""
        result = await self.db.execute(
            select(FileEmbedding).where(
                and_(
                    FileEmbedding.repository_id == repository_id,
                    FileEmbedding.file_path == file_path,
                )
            )
        )
        existing_embeddings = result.scalars().all()

        for embedding in existing_embeddings:
            await self.db.delete(embedding)

    async def search_similar_files(
        self,
        query_vector: List[float],
        top_k: int = 5,
        threshold: float = 0.0,
        repository_name: Optional[str] = None,
        file_extensions: Optional[List[str]] = None,
    ) -> List[Tuple[Dict[str, Any], float]]:
        """
        Search for similar file chunks using pgvector cosine similarity.

        Args:
            query_vector: Query embedding vector
            top_k: Number of top results to return
            threshold: Minimum similarity threshold (0.0 to 1.0, where 1.0 is most similar)
            repository_name: Optional filter by repository name
            file_extensions: Optional filter by file extensions

        Returns:
            List of (metadata, similarity_score) tuples
        """
        try:
            # Convert similarity threshold to distance threshold
            # pgvector cosine distance: 0 = identical, 2 = opposite
            # similarity: 1 = identical, 0 = orthogonal, -1 = opposite
            # distance = 1 - similarity, so similarity = 1 - distance
            distance_threshold = 1.0 - threshold

            # Build the query with pgvector cosine distance
            query = select(
                FileEmbedding,
                Repository.name.label("repository_name"),
                Repository.url.label("repository_url"),
                FileEmbedding.embedding_vector.cosine_distance(query_vector).label(
                    "distance"
                ),
            ).join(Repository)

            # Add filters
            if repository_name:
                query = query.where(Repository.name == repository_name)

            if file_extensions:
                query = query.where(FileEmbedding.file_extension.in_(file_extensions))

            # Filter by distance threshold and order by similarity (ascending distance)
            query = (
                query.where(
                    FileEmbedding.embedding_vector.cosine_distance(query_vector)
                    <= distance_threshold
                )
                .order_by(FileEmbedding.embedding_vector.cosine_distance(query_vector))
                .limit(top_k)
            )

            # Execute query
            result = await self.db.execute(query)
            rows = result.all()

            if not rows:
                return []

            similarities = []
            for row in rows:
                embedding = row.FileEmbedding
                repo_name = row.repository_name
                repo_url = row.repository_url
                distance = row.distance

                # Convert distance back to similarity score
                similarity = 1.0 - distance

                metadata = {
                    "id": embedding.id,
                    "file_path": embedding.file_path,
                    "file_name": embedding.file_name,
                    "file_extension": embedding.file_extension,
                    "file_size": embedding.file_size,
                    "file_hash": embedding.file_hash,
                    "repository_name": repo_name,
                    "repository_url": repo_url,
                    "content_chunk": embedding.content_chunk,
                    "chunk_index": embedding.chunk_index,
                    "total_chunks": embedding.total_chunks,
                    "language": embedding.language,
                    "tokens_count": embedding.tokens_count,
                    "embedding_model": embedding.embedding_model,
                    "created_at": (
                        embedding.created_at.isoformat()
                        if embedding.created_at
                        else None
                    ),
                }
                similarities.append((metadata, similarity))

            return similarities

        except Exception as e:
            logger.error(f"Failed to search similar files: {e}")
            raise

    async def delete_repository_embeddings(self, repository_name: str) -> None:
        """Delete all embeddings for a repository."""
        try:
            # Find repository
            result = await self.db.execute(
                select(Repository).where(Repository.name == repository_name)
            )
            repository = result.scalars().first()

            if repository:
                # Delete all file embeddings for this repository
                result = await self.db.execute(
                    select(FileEmbedding).where(
                        FileEmbedding.repository_id == repository.id
                    )
                )
                embeddings = result.scalars().all()

                for embedding in embeddings:
                    await self.db.delete(embedding)

                # Delete the repository
                await self.db.delete(repository)
                await self.db.commit()

                logger.info(
                    f"Deleted {len(embeddings)} embeddings for repository {repository_name}"
                )

        except Exception as e:
            await self.db.rollback()
            logger.error(f"Failed to delete repository embeddings: {e}")
            raise

    async def delete_file_embeddings(
        self, repository_name: str, file_path: str
    ) -> None:
        """Delete embeddings for a specific file."""
        try:
            # Find repository
            result = await self.db.execute(
                select(Repository).where(Repository.name == repository_name)
            )
            repository = result.scalars().first()

            if repository:
                await self._remove_file_embeddings(repository.id, file_path)
                await self.db.commit()
                logger.info(
                    f"Deleted embeddings for file {file_path} in repository {repository_name}"
                )

        except Exception as e:
            await self.db.rollback()
            logger.error(f"Failed to delete file embeddings: {e}")
            raise

    async def get_repository_stats(
        self, repository_name: Optional[str] = None
    ) -> Dict[str, Any]:
        """Get statistics about embeddings in the database."""
        try:
            if repository_name:
                # Stats for specific repository
                result = await self.db.execute(
                    select(Repository).where(Repository.name == repository_name)
                )
                repository = result.scalars().first()

                if not repository:
                    return {"error": f"Repository {repository_name} not found"}

                # Count embeddings for this repository
                result = await self.db.execute(
                    select(func.count(FileEmbedding.id)).where(
                        FileEmbedding.repository_id == repository.id
                    )
                )
                embedding_count = result.scalar()

                # Count unique files
                result = await self.db.execute(
                    select(func.count(func.distinct(FileEmbedding.file_path))).where(
                        FileEmbedding.repository_id == repository.id
                    )
                )
                file_count = result.scalar()

                return {
                    "repository_name": repository.name,
                    "repository_url": repository.url,
                    "total_embeddings": embedding_count,
                    "unique_files": file_count,
                    "created_at": (
                        repository.created_at.isoformat()
                        if repository.created_at
                        else None
                    ),
                }
            else:
                # Global stats
                result = await self.db.execute(select(func.count(Repository.id)))
                repo_count = result.scalar()

                result = await self.db.execute(select(func.count(FileEmbedding.id)))
                embedding_count = result.scalar()

                result = await self.db.execute(
                    select(func.count(func.distinct(FileEmbedding.file_path)))
                )
                file_count = result.scalar()

                return {
                    "total_repositories": repo_count,
                    "total_embeddings": embedding_count,
                    "unique_files": file_count,
                }

        except Exception as e:
            logger.error(f"Failed to get repository stats: {e}")
            raise

    # Implement abstract methods from VectorStore base class
    def upsert(
        self,
        vectors: List[List[float]],
        metadatas: List[Dict[str, Any]],
        ids: Optional[List[str]] = None,
    ) -> None:
        """Legacy method - use upsert_file_embedding instead."""
        raise NotImplementedError(
            "Use upsert_file_embedding for PostgreSQL vector store"
        )

    def search(
        self, query_vector: List[float], top_k: int = 5, threshold: float = 0.0
    ) -> List[Tuple[Dict[str, Any], float]]:
        """Legacy method - use search_similar_files instead."""
        raise NotImplementedError(
            "Use search_similar_files for PostgreSQL vector store"
        )

    def delete(self, ids: List[str]) -> None:
        """Legacy method - use delete_file_embeddings or delete_repository_embeddings instead."""
        raise NotImplementedError(
            "Use delete_file_embeddings or delete_repository_embeddings"
        )

    def clear(self) -> None:
        """Legacy method - not implemented for safety."""
        raise NotImplementedError("Clear operation not implemented for safety")

    def get_stats(self) -> Dict[str, Any]:
        """Legacy method - use get_repository_stats instead."""
        raise NotImplementedError(
            "Use get_repository_stats for PostgreSQL vector store"
        )

    def exists(self) -> bool:
        """Check if the vector store is properly initialized."""
        return self.db is not None
