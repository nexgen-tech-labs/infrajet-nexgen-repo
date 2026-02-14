"""
Embeddings API routes.
"""

from typing import List, Optional, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File, Form
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel

from app.db.session import get_db
from app.services.embedding_service import EmbeddingService
from app.services.embedding_orchestrator import EmbeddingOrchestrator, RepositoryEmbeddingRequest
from app.services.monitoring_service import EmbeddingMonitoringService
from app.dependencies.auth import get_current_user_id
from app.models.user import User
from logconfig.logger import get_logger

logger = get_logger()
router = APIRouter()


# Pydantic models for request/response
class EmbedFileRequest(BaseModel):
    repository_name: str
    file_path: str
    content: str
    repository_url: Optional[str] = None
    repository_description: Optional[str] = None


class EmbedRepositoryRequest(BaseModel):
    repository_name: str
    repository_path: str
    repository_url: Optional[str] = None
    repository_description: Optional[str] = None
    file_extensions: Optional[List[str]] = None


class SearchRequest(BaseModel):
    query: str
    top_k: int = 5
    threshold: float = 0.7
    repository_name: Optional[str] = None
    file_extensions: Optional[List[str]] = None


class EmbeddingResponse(BaseModel):
    success: bool
    message: str
    data: Optional[Dict[str, Any]] = None


@router.post("/embed/file", response_model=EmbeddingResponse)
async def embed_file(
    request: EmbedFileRequest,
    db: AsyncSession = Depends(get_db),
    # #user_id: str = Depends(get_current_user_id),
):
    """Embed a single file."""
    try:
        embedding_service = EmbeddingService(db)

        result = await embedding_service.embed_file(
            repository_name=request.repository_name,
            file_path=request.file_path,
            content=request.content,
            repository_url=request.repository_url,
            repository_description=request.repository_description,
        )

        return EmbeddingResponse(
            success=True, message="File embedded successfully", data=result
        )

    except Exception as e:
        logger.error(f"Failed to embed file: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to embed file: {str(e)}",
        )


@router.post("/embed/repository", response_model=EmbeddingResponse)
async def embed_repository(
    request: EmbedRepositoryRequest,
    db: AsyncSession = Depends(get_db),
    #user_id: str = Depends(get_current_user_id),
):
    """Embed all files in a repository."""
    try:
        embedding_service = EmbeddingService(db)

        result = await embedding_service.embed_repository(
            repository_name=request.repository_name,
            repository_path=request.repository_path,
            repository_url=request.repository_url,
            repository_description=request.repository_description,
            file_extensions=request.file_extensions,
        )

        return EmbeddingResponse(
            success=True, message="Repository embedded successfully", data=result
        )

    except Exception as e:
        logger.error(f"Failed to embed repository: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to embed repository: {str(e)}",
        )


@router.post("/embed/upload", response_model=EmbeddingResponse)
async def embed_uploaded_file(
    repository_name: str = Form(...),
    file: UploadFile = File(...),
    repository_url: Optional[str] = Form(None),
    repository_description: Optional[str] = Form(None),
    db: AsyncSession = Depends(get_db),
    #user_id: str = Depends(get_current_user_id),
):
    """Embed an uploaded file."""
    try:
        # Read file content
        content = await file.read()
        content_str = content.decode("utf-8")

        embedding_service = EmbeddingService(db)

        result = await embedding_service.embed_file(
            repository_name=repository_name,
            file_path=file.filename or "uploaded_file",
            content=content_str,
            repository_url=repository_url,
            repository_description=repository_description,
        )

        return EmbeddingResponse(
            success=True, message="Uploaded file embedded successfully", data=result
        )

    except UnicodeDecodeError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="File must be a text file (UTF-8 encoded)",
        )
    except Exception as e:
        logger.error(f"Failed to embed uploaded file: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to embed uploaded file: {str(e)}",
        )


@router.post("/search", response_model=EmbeddingResponse)
async def search_similar_code(
    request: SearchRequest,
    db: AsyncSession = Depends(get_db),
    #user_id: str = Depends(get_current_user_id),
):
    """Search for similar code chunks."""
    try:
        embedding_service = EmbeddingService(db)

        results = await embedding_service.search_similar_code(
            query=request.query,
            top_k=request.top_k,
            threshold=request.threshold,
            repository_name=request.repository_name,
            file_extensions=request.file_extensions,
        )

        return EmbeddingResponse(
            success=True,
            message=f"Found {len(results)} similar code chunks",
            data={"results": results},
        )

    except Exception as e:
        logger.error(f"Failed to search similar code: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to search similar code: {str(e)}",
        )


@router.delete("/repository/{repository_name}", response_model=EmbeddingResponse)
async def delete_repository_embeddings(
    repository_name: str,
    db: AsyncSession = Depends(get_db),
    #user_id: str = Depends(get_current_user_id),
):
    """Delete all embeddings for a repository."""
    try:
        embedding_service = EmbeddingService(db)

        await embedding_service.delete_repository(repository_name)

        return EmbeddingResponse(
            success=True, message=f"Deleted embeddings for repository {repository_name}"
        )

    except Exception as e:
        logger.error(f"Failed to delete repository embeddings: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to delete repository embeddings: {str(e)}",
        )


@router.get("/stats", response_model=EmbeddingResponse)
async def get_embedding_stats(
    repository_name: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
    #user_id: str = Depends(get_current_user_id),
):
    """Get embedding statistics."""
    try:
        embedding_service = EmbeddingService(db)

        stats = await embedding_service.get_repository_stats(repository_name)

        return EmbeddingResponse(
            success=True, message="Statistics retrieved successfully", data=stats
        )

    except Exception as e:
        logger.error(f"Failed to get embedding stats: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get embedding stats: {str(e)}",
        )


# Enhanced routes with LLM summarization and orchestration
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


@router.post("/orchestrate/repository", response_model=EmbeddingResponse)
async def orchestrate_repository_embedding(
    request: EnhancedRepositoryRequest,
    db: AsyncSession = Depends(get_db),
    #user_id: str = Depends(get_current_user_id),
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

        # Process repository
        result = await orchestrator.process_repository(repo_request)

        return EmbeddingResponse(
            success=result.status.name == "COMPLETED",
            message=f"Enhanced repository processing completed: {result.files_processed} files, "
                   f"{result.chunks_created} chunks, {result.embeddings_generated} embeddings",
            data={
                "job_id": result.job_id,
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


@router.post("/search/enhanced", response_model=EmbeddingResponse)
async def enhanced_search(
    query: str,
    top_k: int = 10,
    threshold: float = 0.7,
    repository_name: Optional[str] = None,
    search_type: str = "hybrid",  # 'code', 'summary', or 'hybrid'
    db: AsyncSession = Depends(get_db),
    #user_id: str = Depends(get_current_user_id),
):
    """Perform enhanced search with dual embeddings support."""
    try:
        orchestrator = EmbeddingOrchestrator(db)

        # Generate query embedding
        query_embedding = orchestrator.embedding_provider.embed_query(query)

        results = []

        # Search based on type
        if search_type in ['code', 'hybrid']:
            code_results = await orchestrator.vector_store.search_similar_files(
                query_vector=query_embedding,
                top_k=top_k,
                threshold=threshold,
                repository_name=repository_name,
            )
            results.extend([("code", metadata, score) for metadata, score in code_results])

        if search_type in ['summary', 'hybrid']:
            # For summary search, we need to filter by embedding_type
            # This would require modifying the search method to support filtering
            summary_results = await orchestrator.vector_store.search_similar_files(
                query_vector=query_embedding,
                top_k=top_k,
                threshold=threshold,
                repository_name=repository_name,
            )
            results.extend([("summary", metadata, score) for metadata, score in summary_results])

        # Sort and deduplicate results
        results.sort(key=lambda x: x[2], reverse=True)
        seen_chunks = set()
        deduplicated_results = []

        for result_type, metadata, score in results:
            chunk_key = f"{metadata['file_path']}_{metadata['chunk_index']}"
            if chunk_key not in seen_chunks:
                seen_chunks.add(chunk_key)
                deduplicated_results.append({
                    "type": result_type,
                    "content": metadata.get("content_chunk", ""),
                    "file_path": metadata["file_path"],
                    "similarity_score": score,
                    "metadata": metadata
                })

        return EmbeddingResponse(
            success=True,
            message=f"Found {len(deduplicated_results)} relevant results using {search_type} search",
            data={
                "query": query,
                "search_type": search_type,
                "results": deduplicated_results[:top_k]
            }
        )

    except Exception as e:
        logger.error(f"Failed to perform enhanced search: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to perform enhanced search: {str(e)}",
        )


@router.get("/health", response_model=EmbeddingResponse)
async def get_system_health(
    db: AsyncSession = Depends(get_db),
    #user_id: str = Depends(get_current_user_id),
):
    """Get comprehensive system health status."""
    try:
        # Create monitoring service for health check
        monitoring = EmbeddingMonitoringService()
        await monitoring.start_monitoring()

        # Get health status
        health_status = monitoring.get_health_status()

        # Add service availability checks
        orchestrator = EmbeddingOrchestrator(db)
        services_status = {
            "llm_summarization": orchestrator.summarization_service.is_available(),
            "embedding_provider": orchestrator.embedding_provider.is_available(),
            "database": True,  # Assume DB is available if we got here
            "vector_store": orchestrator.vector_store.exists()
        }

        health_status["services"] = services_status

        # Determine overall status
        all_services_healthy = all(services_status.values())
        health_status["all_services_healthy"] = all_services_healthy

        if health_status["status"] == "healthy" and all_services_healthy:
            overall_status = "healthy"
        elif health_status["status"] == "critical" or not all_services_healthy:
            overall_status = "critical"
        else:
            overall_status = "warning"

        health_status["overall_status"] = overall_status

        await monitoring.stop_monitoring()

        return EmbeddingResponse(
            success=overall_status == "healthy",
            message=f"System health: {overall_status}",
            data=health_status
        )

    except Exception as e:
        logger.error(f"Failed to get system health: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get system health: {str(e)}",
        )


@router.get("/metrics", response_model=EmbeddingResponse)
async def get_system_metrics(
    db: AsyncSession = Depends(get_db),
    #user_id: str = Depends(get_current_user_id),
):
    """Get detailed system metrics."""
    try:
        # Create monitoring service
        monitoring = EmbeddingMonitoringService()
        await monitoring.start_monitoring()

        # Get various metrics
        processing_stats = monitoring.get_processing_stats()
        system_stats = monitoring.get_system_stats()
        recent_errors = monitoring.get_recent_errors()

        metrics_data = {
            "processing_stats": processing_stats,
            "system_stats": system_stats,
            "recent_errors": recent_errors,
            "timestamp": time.time()
        }

        await monitoring.stop_monitoring()

        return EmbeddingResponse(
            success=True,
            message="System metrics retrieved successfully",
            data=metrics_data
        )

    except Exception as e:
        logger.error(f"Failed to get system metrics: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get system metrics: {str(e)}",
        )
