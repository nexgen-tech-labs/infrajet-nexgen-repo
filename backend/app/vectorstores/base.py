"""
Abstract base class for vector stores.
"""
from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional, Tuple


class VectorStore(ABC):
    """Abstract base class for vector stores."""
    
    @abstractmethod
    def upsert(self, vectors: List[List[float]], metadatas: List[Dict[str, Any]], ids: Optional[List[str]] = None) -> None:
        """
        Insert or update vectors with metadata.
        
        Args:
            vectors: List of embedding vectors
            metadatas: List of metadata dictionaries (one per vector)
            ids: Optional list of unique IDs for the vectors
        """
        pass
    
    @abstractmethod
    def search(self, query_vector: List[float], top_k: int = 5, threshold: float = 0.0) -> List[Tuple[Dict[str, Any], float]]:
        """
        Search for similar vectors.
        
        Args:
            query_vector: Query embedding vector
            top_k: Number of top results to return
            threshold: Minimum similarity threshold
            
        Returns:
            List of (metadata, similarity_score) tuples
        """
        pass
    
    @abstractmethod
    def delete(self, ids: List[str]) -> None:
        """
        Delete vectors by IDs.
        
        Args:
            ids: List of vector IDs to delete
        """
        pass
    
    @abstractmethod
    def clear(self) -> None:
        """Clear all vectors from the store."""
        pass
    
    @abstractmethod
    def get_stats(self) -> Dict[str, Any]:
        """
        Get statistics about the vector store.
        
        Returns:
            Dictionary with store statistics
        """
        pass
    
    @abstractmethod
    def exists(self) -> bool:
        """
        Check if the vector store exists and is initialized.
        
        Returns:
            True if store exists, False otherwise
        """
        pass