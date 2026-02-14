"""
Enhanced embeddings API routes with LLM summarization and orchestration.
"""

from typing import List, Optional, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, status, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel

from app.db.session import get_db
from app.services.embedding_orchestrator import EmbeddingOrchestrator, RepositoryEmbeddingRequest
from app.dependencies.auth import get_current_user_id
from app.models.user import User
from logconfig.logger import get_logger

logger = get_logger()
router = APIRouter()


# Pydantic models for enhanced endpoints
class EnhancedRepositoryRequest(BaseModel):
    """Request for enhanced repository embedding processing."""
    repository_name: str
    repository_path: str
    repository_url: Optional[str] = None
    repository_description: Optional[str] = None
    file_extensions: Optional[List[str]] = None
    max_files: int = 100
    reindex: bool = False
    recursive: bool = True
    enable_summarization: bool = True
    summarization_model: str = "claude-3-haiku-20240307"


class ProcessingStatusResponse(BaseModel):
    """Response for processing status."""
    job_id: str
    status: str
    files_processed: int
    chunks_created: int
    embeddings_generated: int
    duration_ms: int
    errors: List[Dict[str, Any]]
    repository_name: Optional[str] = None
    start_time: Optional[float] = None
    end_time: Optional[float] = None


class EnhancedEmbeddingResponse(BaseModel):
    """Response for enhanced embedding operations."""
    success: bool
    message: str
    job_id: Optional[str] = None
    data: Optional[Dict[str, Any]] = None


@router.post("/orchestrate/repository", response_model=EnhancedEmbeddingResponse)
async def orchestrate_repository_embedding(
    request: EnhancedRepositoryRequest,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):
    """Orchestrate enhanced repository embedding with LLM summarization."""
    try:
        logger.info(f"Starting orchestrated embedding for repository: {request.repository_name}")

        # Create orchestrator
        orchestrator = EmbeddingOrchestrator(db)

        # Convert to internal request format
        repo_request = RepositoryEmbeddingRequest(
            repository_name=request.repository_name,
            repository_path=request.repository_path,
            repository_url=request.repository_url,
            repository_description=request.repository_description,
            file_extensions=request.file_extensions,
            max_files=request.max_files,
            reindex=request.reindex,
            recursive=request.recursive
        )

        # Process repository (this could be moved to background for large repos)
        if request.max_files > 50:  # For large repositories, run in background
            background_tasks.add_task(
                _process_repository_background,
                orchestrator,
                repo_request,
                request.enable_summarization
            )

            return EnhancedEmbeddingResponse(
                success=True,
                message=f"Repository processing started in background for {request.repository_name}",
                job_id=orchestrator.job_id
            )
        else:
            # Process synchronously for smaller repositories
            result = await orchestrator.process_repository(repo_request)

            return EnhancedEmbeddingResponse(
                success=result.status.name == "COMPLETED",
                message=f"Repository processing completed: {result.files_processed} files, "
                       f"{result.chunks_created} chunks, {result.embeddings_generated} embeddings",
                job_id=result.job_id,
                data={
                    "files_processed": result.files_processed,
                    "chunks_created": result.chunks_created,
                    "embeddings_generated": result.embeddings_generated,
                    "duration_ms": result.duration_ms,
                    "errors": result.errors
                }
            )

    except Exception as e:
        logger.error(f"Failed to orchestrate repository embedding: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to orchestrate repository embedding: {str(e)}",
        )


async def _process_repository_background(
    orchestrator: EmbeddingOrchestrator,
    request: RepositoryEmbeddingRequest,
    enable_summarization: bool
):
    """Background task for processing large repositories."""
    try:
        result = await orchestrator.process_repository(request)
        logger.info(f"Background processing completed for {request.repository_name}: "
                   f"{result.files_processed} files processed")

        # Here you could send notifications, update job status, etc.

    except Exception as e:
        logger.error(f"Background processing failed for {request.repository_name}: {e}")
        # Handle background processing errors


@router.get("/processing/status/{job_id}", response_model=ProcessingStatusResponse)
async def get_processing_status(
    job_id: str,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):
    """Get the status of a processing job."""
    try:
        orchestrator = EmbeddingOrchestrator(db)
        result = await orchestrator.get_processing_status(job_id)

        if result is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Processing job {job_id} not found"
            )

        return ProcessingStatusResponse(
            job_id=result.job_id,
            status=result.status.value,
            files_processed=result.files_processed,
            chunks_created=result.chunks_created,
            embeddings_generated=result.embeddings_generated,
            duration_ms=result.duration_ms,
            errors=result.errors,
            repository_name=result.repository_name,
            start_time=result.start_time,
            end_time=result.end_time
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get processing status: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get processing status: {str(e)}",
        )


@router.delete("/processing/cancel/{job_id}", response_model=EnhancedEmbeddingResponse)
async def cancel_processing(
    job_id: str,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):
    """Cancel a processing job."""
    try:
        orchestrator = EmbeddingOrchestrator(db)
        cancelled = await orchestrator.cancel_processing(job_id)

        if cancelled:
            return EnhancedEmbeddingResponse(
                success=True,
                message=f"Processing job {job_id} cancelled successfully"
            )
        else:
            return EnhancedEmbeddingResponse(
                success=False,
                message=f"Failed to cancel processing job {job_id} or job not found"
            )

    except Exception as e:
        logger.error(f"Failed to cancel processing: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to cancel processing: {str(e)}",
        )


@router.post("/search/hybrid", response_model=EnhancedEmbeddingResponse)
async def hybrid_search(
    query: str,
    top_k: int = 10,
    threshold: float = 0.7,
    repository_name: Optional[str] = None,
    search_code: bool = True,
    search_summaries: bool = True,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):
    """Perform hybrid search across both code and summary embeddings."""
    try:
        orchestrator = EmbeddingOrchestrator(db)

        # Generate query embedding
        query_embedding = orchestrator.embedding_provider.embed_query(query)

        results = []

        # Search code embeddings if enabled
        if search_code:
            code_results = await orchestrator.vector_store.search_similar_files(
                query_vector=query_embedding,
                top_k=top_k,
                threshold=threshold,
                repository_name=repository_name,
                # Filter for code embeddings
            )
            results.extend([("code", metadata, score) for metadata, score in code_results])

        # Search summary embeddings if enabled
        if search_summaries:
            summary_results = await orchestrator.vector_store.search_similar_files(
                query_vector=query_embedding,
                top_k=top_k,
                threshold=threshold,
                repository_name=repository_name,
                # Filter for summary embeddings
            )
            results.extend([("summary", metadata, score) for metadata, score in summary_results])

        # Sort by similarity score and deduplicate
        results.sort(key=lambda x: x[2], reverse=True)
        seen_chunks = set()
        deduplicated_results = []

        for result_type, metadata, score in results:
            chunk_key = f"{metadata['file_path']}_{metadata['chunk_index']}"
            if chunk_key not in seen_chunks:
                seen_chunks.add(chunk_key)
                deduplicated_results.append({
                    "type": result_type,
                    "content": metadata.get("summary_text") if result_type == "summary" else metadata.get("content_chunk"),
                    "file_path": metadata["file_path"],
                    "chunk_index": metadata["chunk_index"],
                    "similarity_score": score,
                    "metadata": metadata
                })

        return EnhancedEmbeddingResponse(
            success=True,
            message=f"Found {len(deduplicated_results)} relevant results",
            data={
                "query": query,
                "results": deduplicated_results[:top_k],
                "total_results": len(deduplicated_results)
            }
        )

    except Exception as e:
        logger.error(f"Failed to perform hybrid search: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to perform hybrid search: {str(e)}",
        )


@router.get("/stats/enhanced", response_model=EnhancedEmbeddingResponse)
async def get_enhanced_stats(
    repository_name: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):
    """Get enhanced statistics including dual embedding information."""
    try:
        orchestrator = EmbeddingOrchestrator(db)

        # Get basic stats
        basic_stats = await orchestrator.vector_store.get_repository_stats(repository_name)

        # Get enhanced stats (code vs summary breakdown)
        # This would require additional queries to count by embedding_type

        return EnhancedEmbeddingResponse(
            success=True,
            message="Enhanced statistics retrieved successfully",
            data={
                "basic_stats": basic_stats,
                "enhanced_features": {
                    "llm_summarization": True,
                    "dual_embeddings": True,
                    "orchestrated_processing": True
                }
            }
        )

    except Exception as e:
        logger.error(f"Failed to get enhanced stats: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get enhanced stats: {str(e)}",
        )
