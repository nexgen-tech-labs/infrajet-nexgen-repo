"""
Embedding-related Pydantic schemas for request/response validation.
"""
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field


class EmbedFolderRequest(BaseModel):
    """Request schema for embedding a folder of Terraform files."""
    folder_path: str = Field(..., description="Absolute or workspace-relative path to Terraform directory")
    provider: str = Field("anthropic", description="Embedding provider: anthropic")
    reindex: bool = Field(False, description="Whether to clear existing embeddings and reindex")
    recursive: bool = Field(True, description="Whether to recursively process subdirectories")
    max_files: int = Field(100, description="Maximum number of files to process")

    class Config:
        json_schema_extra = {
            "example": {
                "folder_path": "/path/to/terraform/project",
                "provider": "anthropic",
                "reindex": False,
                "recursive": True,
                "max_files": 100
            }
        }


class EmbedFileRequest(BaseModel):
    """Request schema for embedding a single Terraform file."""
    file_path: str = Field(..., description="Path to Terraform file")
    provider: str = Field("anthropic", description="Embedding provider: anthropic")

    class Config:
        json_schema_extra = {
            "example": {
                "file_path": "/path/to/main.tf",
                "provider": "anthropic"
            }
        }


class EmbeddingStats(BaseModel):
    """Statistics about the embedding process."""
    files_processed: int = Field(..., description="Number of files processed")
    chunks_created: int = Field(..., description="Number of text chunks created")
    embeddings_generated: int = Field(..., description="Number of embeddings generated")
    duration_ms: int = Field(..., description="Processing duration in milliseconds")
    errors: List[str] = Field(default_factory=list, description="Any errors encountered")


class EmbedFolderResponse(BaseModel):
    """Response schema for folder embedding operation."""
    success: bool = Field(..., description="Whether the operation was successful")
    stats: EmbeddingStats = Field(..., description="Processing statistics")
    message: str = Field(..., description="Human-readable status message")

    class Config:
        json_schema_extra = {
            "example": {
                "success": True,
                "stats": {
                    "files_processed": 15,
                    "chunks_created": 45,
                    "embeddings_generated": 45,
                    "duration_ms": 2500,
                    "errors": []
                },
                "message": "Successfully embedded 15 Terraform files"
            }
        }


class EmbedFileResponse(BaseModel):
    """Response schema for single file embedding operation."""
    success: bool = Field(..., description="Whether the operation was successful")
    file_path: str = Field(..., description="Path of the processed file")
    chunks_created: int = Field(..., description="Number of text chunks created")
    embeddings_generated: int = Field(..., description="Number of embeddings generated")
    duration_ms: int = Field(..., description="Processing duration in milliseconds")
    errors: List[str] = Field(default_factory=list, description="Any errors encountered")


class SearchRequest(BaseModel):
    """Request schema for semantic search in embeddings."""
    query: str = Field(..., description="Search query text")
    top_k: int = Field(5, description="Number of top results to return")
    threshold: float = Field(0.7, description="Minimum similarity threshold")
    file_types: Optional[List[str]] = Field(None, description="Filter by file types")

    class Config:
        json_schema_extra = {
            "example": {
                "query": "AWS S3 bucket configuration",
                "top_k": 5,
                "threshold": 0.7,
                "file_types": [".tf"]
            }
        }


class SearchResult(BaseModel):
    """Individual search result."""
    content: str = Field(..., description="The matched text content")
    file_path: str = Field(..., description="Path to the source file")
    chunk_index: int = Field(..., description="Index of the chunk within the file")
    similarity_score: float = Field(..., description="Similarity score (0-1)")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Additional metadata")


class SearchResponse(BaseModel):
    """Response schema for semantic search."""
    success: bool = Field(..., description="Whether the search was successful")
    query: str = Field(..., description="The original search query")
    results: List[SearchResult] = Field(..., description="Search results")
    total_results: int = Field(..., description="Total number of results found")
    duration_ms: int = Field(..., description="Search duration in milliseconds")

    class Config:
        json_schema_extra = {
            "example": {
                "success": True,
                "query": "AWS S3 bucket configuration",
                "results": [
                    {
                        "content": "resource \"aws_s3_bucket\" \"example\" {\n  bucket = \"my-tf-test-bucket\"\n}",
                        "file_path": "/path/to/s3.tf",
                        "chunk_index": 0,
                        "similarity_score": 0.95,
                        "metadata": {"language": "terraform", "resource_type": "aws_s3_bucket"}
                    }
                ],
                "total_results": 1,
                "duration_ms": 150
            }
        }


class EmbeddingStatus(BaseModel):
    """Status information about the embedding system."""
    index_exists: bool = Field(..., description="Whether the FAISS index exists")
    total_embeddings: int = Field(..., description="Total number of embeddings in the index")
    index_size_mb: float = Field(..., description="Size of the index in MB")
    last_updated: Optional[str] = Field(None, description="Last update timestamp")
    provider: str = Field(..., description="Current embedding provider")