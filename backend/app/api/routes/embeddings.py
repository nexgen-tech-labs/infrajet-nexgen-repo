"""
FastAPI routes for embedding operations on Terraform files.
"""
import time
from typing import Dict, Any
from fastapi import APIRouter, HTTPException, Depends, BackgroundTasks
from fastapi.responses import JSONResponse

from app.schemas.embedding import (
    EmbedFolderRequest, EmbedFolderResponse, EmbedFileRequest, EmbedFileResponse,
    SearchRequest, SearchResponse, EmbeddingStatus, EmbeddingStats
)
from app.services.embedding_service import EmbeddingService
from app.core.config import get_settings
from logconfig.logger import get_logger

logger = get_logger()
router = APIRouter()


def get_embedding_service() -> EmbeddingService:
    """Dependency to get embedding service instance."""
    return EmbeddingService()


@router.post("/folder", response_model=EmbedFolderResponse)
async def embed_folder(
    request: EmbedFolderRequest,
    background_tasks: BackgroundTasks,
    embedding_service: EmbeddingService = Depends(get_embedding_service)
):
    """
    Embed all Terraform files in a folder.
    
    This endpoint processes all Terraform files (.tf, .tfvars, .hcl) in the specified
    folder, chunks them semantically, generates embeddings, and stores them in a
    vector database for semantic search.
    """
    start_time = time.time()
    
    try:
        logger.info(f"Starting folder embedding: {request.folder_path}")
        
        # Validate provider
        if request.provider not in ["anthropic"]:
            raise HTTPException(
                status_code=400, 
                detail=f"Unsupported provider: {request.provider}. Supported: anthropic"
            )
        
        # Process embeddings
        stats = await embedding_service.embed_folder(
            folder_path=request.folder_path,
            provider_name=request.provider,
            reindex=request.reindex,
            recursive=request.recursive,
            max_files=request.max_files
        )
        
        # Create response
        embedding_stats = EmbeddingStats(
            files_processed=stats['files_processed'],
            chunks_created=stats['chunks_created'],
            embeddings_generated=stats['embeddings_generated'],
            duration_ms=stats['duration_ms'],
            errors=stats.get('errors', [])
        )
        
        success = stats['files_processed'] > 0
        message = f"Successfully embedded {stats['files_processed']} Terraform files"
        
        if stats.get('errors'):
            message += f" with {len(stats['errors'])} errors"
        
        if not success:
            message = "No files were processed"
        
        return EmbedFolderResponse(
            success=success,
            stats=embedding_stats,
            message=message
        )
        
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail=f"Folder not found: {request.folder_path}")
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error embedding folder {request.folder_path}: {e}")
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")


@router.post("/file", response_model=EmbedFileResponse)
async def embed_file(
    request: EmbedFileRequest,
    embedding_service: EmbeddingService = Depends(get_embedding_service)
):
    """
    Embed a single Terraform file.
    
    This endpoint processes a single Terraform file, chunks it semantically,
    generates embeddings, and stores them in the vector database.
    """
    try:
        logger.info(f"Starting file embedding: {request.file_path}")
        
        # Validate provider
        if request.provider not in ["anthropic"]:
            raise HTTPException(
                status_code=400, 
                detail=f"Unsupported provider: {request.provider}. Supported: anthropic"
            )
        
        # Process file
        stats = await embedding_service.embed_file(
            file_path=request.file_path,
            provider_name=request.provider
        )
        
        success = stats['chunks_created'] > 0
        
        return EmbedFileResponse(
            success=success,
            file_path=stats['file_path'],
            chunks_created=stats['chunks_created'],
            embeddings_generated=stats['embeddings_generated'],
            duration_ms=stats['duration_ms'],
            errors=stats.get('errors', [])
        )
        
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail=f"File not found: {request.file_path}")
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error embedding file {request.file_path}: {e}")
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")


@router.post("/search", response_model=SearchResponse)
async def search_embeddings(
    request: SearchRequest,
    embedding_service: EmbeddingService = Depends(get_embedding_service)
):
    """
    Search for similar Terraform code using semantic search.
    
    This endpoint takes a natural language query and finds the most similar
    Terraform code chunks based on semantic similarity.
    """
    try:
        logger.info(f"Starting semantic search: '{request.query[:100]}...'")
        
        # Perform search
        search_result = embedding_service.search(
            query=request.query,
            top_k=request.top_k,
            threshold=request.threshold,
            provider_name="anthropic"  # Default to anthropic for now
        )
        
        if not search_result['success']:
            raise HTTPException(status_code=400, detail=search_result.get('error', 'Search failed'))
        
        return SearchResponse(
            success=True,
            query=request.query,
            results=search_result['results'],
            total_results=search_result['total_results'],
            duration_ms=search_result['duration_ms']
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error searching embeddings: {e}")
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")


@router.get("/status", response_model=EmbeddingStatus)
async def get_embedding_status(
    embedding_service: EmbeddingService = Depends(get_embedding_service)
):
    """
    Get status information about the embedding system.
    
    Returns information about the current state of the vector database,
    including number of embeddings, index size, and provider information.
    """
    try:
        status = embedding_service.get_embedding_status(provider_name="anthropic")
        
        return EmbeddingStatus(
            index_exists=status['index_exists'],
            total_embeddings=status['total_embeddings'],
            index_size_mb=status['index_size_mb'],
            provider=status['provider'],
            last_updated=status.get('last_updated')
        )
        
    except Exception as e:
        logger.error(f"Error getting embedding status: {e}")
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")


@router.delete("/clear")
async def clear_embeddings(
    embedding_service: EmbeddingService = Depends(get_embedding_service)
):
    """
    Clear all embeddings from the vector database.
    
    This endpoint removes all stored embeddings and resets the vector database.
    Use with caution as this operation cannot be undone.
    """
    try:
        logger.info("Clearing all embeddings")
        
        vector_store = embedding_service.get_vector_store("anthropic")
        vector_store.clear()
        
        return JSONResponse(
            content={
                "success": True,
                "message": "All embeddings cleared successfully"
            }
        )
        
    except Exception as e:
        logger.error(f"Error clearing embeddings: {e}")
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")


@router.get("/providers")
async def get_supported_providers():
    """
    Get list of supported embedding providers.
    
    Returns information about available embedding providers and their capabilities.
    """
    return {
        "providers": [
            {
                "name": "anthropic",
                "display_name": "Anthropic Claude",
                "description": "Uses Claude for semantic analysis and embedding generation",
                "dimension": 1536,
                "requires_api_key": True
            }
        ]
    }


@router.get("/health")
async def health_check(
    embedding_service: EmbeddingService = Depends(get_embedding_service)
):
    """
    Health check endpoint for the embedding service.
    
    Verifies that the embedding service and its dependencies are working correctly.
    """
    try:
        # Check if provider is available
        provider = embedding_service.get_provider("anthropic")
        provider_available = provider.is_available()
        
        # Check vector store
        vector_store = embedding_service.get_vector_store("anthropic")
        vector_store_stats = vector_store.get_stats()
        
        return {
            "status": "healthy" if provider_available else "degraded",
            "provider_available": provider_available,
            "vector_store_initialized": True,
            "total_embeddings": vector_store_stats['total_vectors'],
            "timestamp": time.time()
        }
        
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        return JSONResponse(
            status_code=503,
            content={
                "status": "unhealthy",
                "error": str(e),
                "timestamp": time.time()
            }
        )