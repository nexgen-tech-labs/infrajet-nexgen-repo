"""
RAG Retriever for context retrieval in code generation.

This module provides context retrieval capabilities using vector similarity search
to find relevant code patterns and documentation for autonomous code generation.
"""

import asyncio
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass, field
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.embedding_orchestrator import EmbeddingOrchestrator
from app.vectorstores.postgres_store import PostgresVectorStore
from app.providers.embedding.enhanced_anthropic_provider import EnhancedAnthropicEmbeddingProvider
from app.services.code_generation.config.settings import get_code_generation_settings
from logconfig.logger import get_logger

logger = get_logger()
settings = get_code_generation_settings()


@dataclass
class RetrievalContext:
    """Context retrieved for code generation."""
    query: str
    repository_name: Optional[str] = None
    file_extensions: Optional[List[str]] = None
    max_results: int = 10
    similarity_threshold: float = 0.7
    include_summaries: bool = True
    include_code_chunks: bool = True


@dataclass
class RetrievedDocument:
    """A retrieved document with metadata and similarity score."""
    content: str
    metadata: Dict[str, Any]
    similarity_score: float
    source_type: str  # "code" or "summary"
    repository_name: str
    file_path: str
    chunk_index: int


@dataclass
class RetrievalResult:
    """Result of context retrieval operation."""
    query: str
    documents: List[RetrievedDocument] = field(default_factory=list)
    total_found: int = 0
    processing_time_ms: float = 0.0
    embedding_time_ms: float = 0.0
    search_time_ms: float = 0.0


class RAGRetriever:
    """
    RAG Retriever for context retrieval using vector similarity search.

    This class orchestrates the retrieval of relevant context from the vector store
    using query embeddings and similarity search with configurable parameters.
    """

    def __init__(self, db_session: AsyncSession):
        """
        Initialize the RAG retriever.

        Args:
            db_session: Database session for vector store operations
        """
        self.db = db_session
        self.vector_store = PostgresVectorStore(db_session)
        self.embedding_provider = EnhancedAnthropicEmbeddingProvider(
            api_key=settings.LLM_API_KEY
        )

        # Configuration
        self.max_concurrent_searches = 5
        self.embedding_batch_size = 10

        logger.info("RAGRetriever initialized")

    async def retrieve_context(self, context: RetrievalContext) -> RetrievalResult:
        """
        Retrieve relevant context for the given query.

        Args:
            context: Retrieval context with query and parameters

        Returns:
            RetrievalResult with retrieved documents and metadata
        """
        import time
        start_time = time.time()

        result = RetrievalResult(query=context.query)

        try:
            # Generate embedding for the query
            embedding_start = time.time()
            query_embedding = await self._generate_query_embedding(context.query)
            result.embedding_time_ms = (time.time() - embedding_start) * 1000

            if not query_embedding:
                logger.warning("Failed to generate query embedding")
                return result

            # Perform similarity search
            search_start = time.time()
            search_results = await self._perform_similarity_search(
                query_embedding=query_embedding,
                context=context
            )
            result.search_time_ms = (time.time() - search_start) * 1000

            # Process and rank results
            result.documents = await self._process_search_results(
                search_results=search_results,
                context=context
            )
            result.total_found = len(result.documents)

            result.processing_time_ms = (time.time() - start_time) * 1000

            logger.info(
                f"Retrieved {result.total_found} documents for query '{context.query[:50]}...' "
                f"in {result.processing_time_ms:.2f}ms"
            )

        except Exception as e:
            logger.error(f"Error during context retrieval: {e}")
            result.processing_time_ms = (time.time() - start_time) * 1000

        return result

    async def _generate_query_embedding(self, query: str) -> Optional[List[float]]:
        """
        Generate embedding vector for the query.

        Args:
            query: Query text to embed

        Returns:
            Embedding vector or None if generation fails
        """
        try:
            # Use the embedding provider to generate query embedding
            embeddings = self.embedding_provider.embed_texts([query])
            if embeddings and len(embeddings) > 0:
                return embeddings[0]
            else:
                logger.error("No embeddings generated for query")
                return None

        except Exception as e:
            logger.error(f"Failed to generate query embedding: {e}")
            return None

    async def _perform_similarity_search(
        self,
        query_embedding: List[float],
        context: RetrievalContext
    ) -> List[Tuple[Dict[str, Any], float]]:
        """
        Perform similarity search in the vector store.

        Args:
            query_embedding: Query embedding vector
            context: Retrieval context with search parameters

        Returns:
            List of (metadata, similarity_score) tuples
        """
        try:
            # Use the vector store's search method
            results = await self.vector_store.search_similar_files(
                query_vector=query_embedding,
                top_k=context.max_results * 2,  # Get more results for filtering
                threshold=context.similarity_threshold,
                repository_name=context.repository_name,
                file_extensions=context.file_extensions
            )

            logger.debug(f"Vector search returned {len(results)} results")
            return results

        except Exception as e:
            logger.error(f"Similarity search failed: {e}")
            return []

    async def _process_search_results(
        self,
        search_results: List[Tuple[Dict[str, Any], float]],
        context: RetrievalContext
    ) -> List[RetrievedDocument]:
        """
        Process and rank search results into RetrievedDocument objects.

        Args:
            search_results: Raw search results from vector store
            context: Retrieval context

        Returns:
            List of processed RetrievedDocument objects
        """
        documents = []

        for metadata, similarity_score in search_results:
            try:
                # Determine source type based on metadata
                source_type = "summary" if metadata.get("summary_text") else "code"

                # Get content based on source type and context preferences
                content = self._extract_content(metadata, source_type, context)

                if not content:
                    continue

                # Create RetrievedDocument
                document = RetrievedDocument(
                    content=content,
                    metadata=metadata,
                    similarity_score=similarity_score,
                    source_type=source_type,
                    repository_name=metadata.get("repository_name", "unknown"),
                    file_path=metadata.get("file_path", ""),
                    chunk_index=metadata.get("chunk_index", 0)
                )

                documents.append(document)

            except Exception as e:
                logger.warning(f"Failed to process search result: {e}")
                continue

        # Sort by similarity score (highest first)
        documents.sort(key=lambda x: x.similarity_score, reverse=True)

        # Limit to max_results
        if len(documents) > context.max_results:
            documents = documents[:context.max_results]

        return documents

    def _extract_content(
        self,
        metadata: Dict[str, Any],
        source_type: str,
        context: RetrievalContext
    ) -> Optional[str]:
        """
        Extract content from metadata based on source type and preferences.

        Args:
            metadata: Document metadata
            source_type: Type of content source ("code" or "summary")
            context: Retrieval context with preferences

        Returns:
            Extracted content or None
        """
        if source_type == "summary" and context.include_summaries:
            return metadata.get("summary_text")
        elif source_type == "code" and context.include_code_chunks:
            return metadata.get("content_chunk")

        return None

    async def retrieve_repository_context(
        self,
        query: str,
        repository_name: str,
        max_results: int = 5,
        similarity_threshold: float = 0.7
    ) -> RetrievalResult:
        """
        Retrieve context specific to a repository.

        Args:
            query: Search query
            repository_name: Name of the repository to search in
            max_results: Maximum number of results to return
            similarity_threshold: Minimum similarity threshold

        Returns:
            RetrievalResult with repository-specific context
        """
        context = RetrievalContext(
            query=query,
            repository_name=repository_name,
            max_results=max_results,
            similarity_threshold=similarity_threshold
        )

        return await self.retrieve_context(context)

    async def retrieve_multi_repository_context(
        self,
        query: str,
        repository_names: List[str],
        max_results_per_repo: int = 3,
        similarity_threshold: float = 0.7
    ) -> Dict[str, RetrievalResult]:
        """
        Retrieve context from multiple repositories concurrently.

        Args:
            query: Search query
            repository_names: List of repository names to search in
            max_results_per_repo: Maximum results per repository
            similarity_threshold: Minimum similarity threshold

        Returns:
            Dictionary mapping repository names to their RetrievalResults
        """
        async def retrieve_for_repo(repo_name: str) -> Tuple[str, RetrievalResult]:
            result = await self.retrieve_repository_context(
                query=query,
                repository_name=repo_name,
                max_results=max_results_per_repo,
                similarity_threshold=similarity_threshold
            )
            return repo_name, result

        # Execute concurrent searches
        tasks = [retrieve_for_repo(repo) for repo in repository_names]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Process results
        repo_results = {}
        for result in results:
            if isinstance(result, Exception):
                logger.error(f"Error in multi-repository retrieval: {result}")
                continue

            repo_name, retrieval_result = result
            repo_results[repo_name] = retrieval_result

        return repo_results

    async def get_retrieval_stats(self) -> Dict[str, Any]:
        """
        Get statistics about the retrieval system.

        Returns:
            Dictionary with retrieval statistics
        """
        try:
            stats = await self.vector_store.get_repository_stats()
            return {
                "vector_store_stats": stats,
                "embedding_provider": "enhanced_anthropic",
                "max_concurrent_searches": self.max_concurrent_searches,
                "embedding_batch_size": self.embedding_batch_size
            }
        except Exception as e:
            logger.error(f"Failed to get retrieval stats: {e}")
            return {"error": str(e)}