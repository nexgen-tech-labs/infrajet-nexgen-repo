"""
Abstract base class for embedding providers.
"""
from abc import ABC, abstractmethod
from typing import List, Sequence, Dict, Any


class EmbeddingProvider(ABC):
    """Abstract base class for embedding providers."""
    
    @abstractmethod
    def embed_texts(self, texts: Sequence[str]) -> List[List[float]]:
        """
        Generate embeddings for a sequence of texts.
        
        Args:
            texts: Sequence of text strings to embed
            
        Returns:
            List of embedding vectors (one per input text)
        """
        pass
    
    @abstractmethod
    def embed_query(self, query: str) -> List[float]:
        """
        Generate embedding for a single query text.
        
        Args:
            query: Query text to embed
            
        Returns:
            Embedding vector for the query
        """
        pass
    
    @abstractmethod
    def get_dimension(self) -> int:
        """
        Get the dimension of embeddings produced by this provider.
        
        Returns:
            Embedding dimension
        """
        pass
    
    @abstractmethod
    def is_available(self) -> bool:
        """
        Check if the provider is available and properly configured.
        
        Returns:
            True if provider is available, False otherwise
        """
        pass
    
    def get_provider_info(self) -> Dict[str, Any]:
        """
        Get information about this provider.
        
        Returns:
            Dictionary with provider information
        """
        return {
            "name": self.__class__.__name__,
            "dimension": self.get_dimension(),
            "available": self.is_available()
        }