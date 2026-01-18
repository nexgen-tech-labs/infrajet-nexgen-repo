"""
FAISS-based vector store implementation.
"""
import os
import json
import pickle
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple
import numpy as np

try:
    import faiss
    FAISS_AVAILABLE = True
except ImportError:
    FAISS_AVAILABLE = False

from app.vectorstores.base import VectorStore
from logconfig.logger import get_logger

logger = get_logger()


class FaissStore(VectorStore):
    """FAISS-based vector store for efficient similarity search."""
    
    def __init__(self, index_path: str, dimension: int):
        """
        Initialize FAISS vector store.
        
        Args:
            index_path: Directory path to store FAISS index files
            dimension: Dimension of embedding vectors
        """
        if not FAISS_AVAILABLE:
            raise ImportError("FAISS is not available. Install with: pip install faiss-cpu")
        
        self.index_path = Path(index_path)
        self.dimension = dimension
        
        # Create directory if it doesn't exist
        self.index_path.mkdir(parents=True, exist_ok=True)
        
        # File paths
        self.faiss_index_file = self.index_path / "index.faiss"
        self.metadata_file = self.index_path / "metadata.pkl"
        self.id_mapping_file = self.index_path / "id_mapping.json"
        
        # Initialize or load index
        self.index = self._load_or_create_index()
        self.metadata = self._load_metadata()
        self.id_to_idx = self._load_id_mapping()
        self.next_idx = len(self.metadata)
    
    def _load_or_create_index(self) -> 'faiss.Index':
        """Load existing FAISS index or create a new one."""
        if self.faiss_index_file.exists():
            try:
                logger.info(f"Loading existing FAISS index from {self.faiss_index_file}")
                return faiss.read_index(str(self.faiss_index_file))
            except Exception as e:
                logger.warning(f"Failed to load existing index: {e}. Creating new index.")
        
        logger.info(f"Creating new FAISS index with dimension {self.dimension}")
        # Use IndexFlatIP for cosine similarity (after L2 normalization)
        index = faiss.IndexFlatIP(self.dimension)
        return index
    
    def _load_metadata(self) -> List[Dict[str, Any]]:
        """Load metadata from disk."""
        if self.metadata_file.exists():
            try:
                with open(self.metadata_file, 'rb') as f:
                    return pickle.load(f)
            except Exception as e:
                logger.warning(f"Failed to load metadata: {e}")
        return []
    
    def _load_id_mapping(self) -> Dict[str, int]:
        """Load ID to index mapping from disk."""
        if self.id_mapping_file.exists():
            try:
                with open(self.id_mapping_file, 'r') as f:
                    return json.load(f)
            except Exception as e:
                logger.warning(f"Failed to load ID mapping: {e}")
        return {}
    
    def _save_index(self) -> None:
        """Save FAISS index to disk."""
        try:
            faiss.write_index(self.index, str(self.faiss_index_file))
        except Exception as e:
            logger.error(f"Failed to save FAISS index: {e}")
            raise
    
    def _save_metadata(self) -> None:
        """Save metadata to disk."""
        try:
            with open(self.metadata_file, 'wb') as f:
                pickle.dump(self.metadata, f)
        except Exception as e:
            logger.error(f"Failed to save metadata: {e}")
            raise
    
    def _save_id_mapping(self) -> None:
        """Save ID mapping to disk."""
        try:
            with open(self.id_mapping_file, 'w') as f:
                json.dump(self.id_to_idx, f)
        except Exception as e:
            logger.error(f"Failed to save ID mapping: {e}")
            raise
    
    def upsert(self, vectors: List[List[float]], metadatas: List[Dict[str, Any]], ids: Optional[List[str]] = None) -> None:
        """
        Insert or update vectors with metadata.
        
        Args:
            vectors: List of embedding vectors
            metadatas: List of metadata dictionaries
            ids: Optional list of unique IDs for the vectors
        """
        if not vectors:
            return
        
        if len(vectors) != len(metadatas):
            raise ValueError("Number of vectors must match number of metadata entries")
        
        if ids and len(ids) != len(vectors):
            raise ValueError("Number of IDs must match number of vectors")
        
        # Convert to numpy array and normalize for cosine similarity
        vectors_array = np.array(vectors, dtype=np.float32)
        faiss.normalize_L2(vectors_array)
        
        # Generate IDs if not provided
        if not ids:
            ids = [f"vec_{self.next_idx + i}" for i in range(len(vectors))]
        
        # Handle updates (remove existing vectors with same IDs)
        existing_indices = []
        for vec_id in ids:
            if vec_id in self.id_to_idx:
                existing_indices.append(self.id_to_idx[vec_id])
        
        if existing_indices:
            # For simplicity, we'll rebuild the index without the existing vectors
            # In production, consider using IndexIDMap for more efficient updates
            self._remove_vectors_by_indices(existing_indices)
        
        # Add new vectors
        start_idx = self.index.ntotal
        self.index.add(vectors_array)
        
        # Update metadata and ID mapping
        for i, (vec_id, metadata) in enumerate(zip(ids, metadatas)):
            idx = start_idx + i
            
            # Ensure metadata list is large enough
            while len(self.metadata) <= idx:
                self.metadata.append({})
            
            self.metadata[idx] = metadata
            self.id_to_idx[vec_id] = idx
        
        self.next_idx = self.index.ntotal
        
        # Save to disk
        self._save_index()
        self._save_metadata()
        self._save_id_mapping()
        
        logger.info(f"Upserted {len(vectors)} vectors. Total vectors: {self.index.ntotal}")
    
    def _remove_vectors_by_indices(self, indices: List[int]) -> None:
        """Remove vectors by their indices (requires rebuilding index)."""
        if not indices:
            return
        
        # Get all vectors and metadata except the ones to remove
        all_vectors = []
        new_metadata = []
        new_id_mapping = {}
        
        indices_set = set(indices)
        new_idx = 0
        
        for old_idx in range(self.index.ntotal):
            if old_idx not in indices_set:
                # Get vector from index
                vector = self.index.reconstruct(old_idx)
                all_vectors.append(vector)
                
                # Copy metadata
                if old_idx < len(self.metadata):
                    new_metadata.append(self.metadata[old_idx])
                else:
                    new_metadata.append({})
                
                # Update ID mapping
                for vec_id, mapped_idx in self.id_to_idx.items():
                    if mapped_idx == old_idx:
                        new_id_mapping[vec_id] = new_idx
                        break
                
                new_idx += 1
        
        # Rebuild index
        self.index = faiss.IndexFlatIP(self.dimension)
        if all_vectors:
            vectors_array = np.array(all_vectors, dtype=np.float32)
            self.index.add(vectors_array)
        
        self.metadata = new_metadata
        self.id_to_idx = new_id_mapping
        self.next_idx = len(new_metadata)
    
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
        if self.index.ntotal == 0:
            return []
        
        # Normalize query vector for cosine similarity
        query_array = np.array([query_vector], dtype=np.float32)
        faiss.normalize_L2(query_array)
        
        # Search
        similarities, indices = self.index.search(query_array, min(top_k, self.index.ntotal))
        
        results = []
        for similarity, idx in zip(similarities[0], indices[0]):
            if idx == -1:  # FAISS returns -1 for invalid indices
                continue
            
            if similarity < threshold:
                continue
            
            # Get metadata
            metadata = self.metadata[idx] if idx < len(self.metadata) else {}
            results.append((metadata, float(similarity)))
        
        return results
    
    def delete(self, ids: List[str]) -> None:
        """
        Delete vectors by IDs.
        
        Args:
            ids: List of vector IDs to delete
        """
        indices_to_remove = []
        for vec_id in ids:
            if vec_id in self.id_to_idx:
                indices_to_remove.append(self.id_to_idx[vec_id])
        
        if indices_to_remove:
            self._remove_vectors_by_indices(indices_to_remove)
            self._save_index()
            self._save_metadata()
            self._save_id_mapping()
            
            logger.info(f"Deleted {len(indices_to_remove)} vectors")
    
    def clear(self) -> None:
        """Clear all vectors from the store."""
        self.index = faiss.IndexFlatIP(self.dimension)
        self.metadata = []
        self.id_to_idx = {}
        self.next_idx = 0
        
        # Remove files
        for file_path in [self.faiss_index_file, self.metadata_file, self.id_mapping_file]:
            if file_path.exists():
                file_path.unlink()
        
        logger.info("Cleared all vectors from store")
    
    def get_stats(self) -> Dict[str, Any]:
        """Get statistics about the vector store."""
        index_size = 0
        if self.faiss_index_file.exists():
            index_size = self.faiss_index_file.stat().st_size
        
        return {
            "total_vectors": self.index.ntotal,
            "dimension": self.dimension,
            "index_size_bytes": index_size,
            "index_size_mb": round(index_size / (1024 * 1024), 2),
            "metadata_entries": len(self.metadata),
            "id_mappings": len(self.id_to_idx)
        }
    
    def exists(self) -> bool:
        """Check if the vector store exists and is initialized."""
        return (self.faiss_index_file.exists() and 
                self.metadata_file.exists() and 
                self.index.ntotal > 0)