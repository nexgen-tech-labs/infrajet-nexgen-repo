"""
Anthropic Claude embedding provider implementation.
"""
import json
from typing import List, Sequence, Dict, Any
from anthropic import Anthropic
from app.providers.embedding.base import EmbeddingProvider
from logconfig.logger import get_logger

logger = get_logger()


class AnthropicEmbeddingProvider(EmbeddingProvider):
    """Anthropic Claude embedding provider using text analysis for semantic embeddings."""
    
    def __init__(self, api_key: str, model: str = "claude-3-haiku-20240307"):
        """
        Initialize Anthropic embedding provider.
        
        Args:
            api_key: Anthropic API key
            model: Claude model to use for text analysis
        """
        self.api_key = api_key
        self.model = model
        self.client = Anthropic(api_key=api_key) if api_key else None
        self._dimension = 1536  # Standard embedding dimension
        
    def embed_texts(self, texts: Sequence[str]) -> List[List[float]]:
        """
        Generate embeddings for multiple texts using Claude's text analysis.
        
        Args:
            texts: Sequence of text strings to embed
            
        Returns:
            List of embedding vectors
        """
        if not self.is_available():
            raise ValueError("Anthropic provider is not available. Check API key.")
        
        embeddings = []
        for text in texts:
            try:
                embedding = self._generate_embedding(text)
                embeddings.append(embedding)
            except Exception as e:
                logger.error(f"Failed to generate embedding for text: {e}")
                # Return zero vector as fallback
                embeddings.append([0.0] * self._dimension)
        
        return embeddings
    
    def embed_query(self, query: str) -> List[float]:
        """
        Generate embedding for a single query.
        
        Args:
            query: Query text to embed
            
        Returns:
            Embedding vector for the query
        """
        if not self.is_available():
            raise ValueError("Anthropic provider is not available. Check API key.")
        
        return self._generate_embedding(query)
    
    def _generate_embedding(self, text: str) -> List[float]:
        """
        Generate embedding for a single text using Claude's semantic analysis.
        
        This is a simplified approach that uses Claude to analyze text semantically
        and generate a consistent vector representation.
        """
        try:
            # Use Claude to analyze the text and extract semantic features
            prompt = f"""Analyze the following Terraform/HCL code and extract its key semantic features.
Focus on:
1. Resource types and their purposes
2. Configuration patterns
3. Infrastructure components
4. Dependencies and relationships
5. Security and compliance aspects

Text to analyze:
{text[:2000]}  # Limit text length

Provide a structured analysis as JSON with numerical scores (0-1) for different semantic dimensions:
- infrastructure_complexity
- security_focus  
- networking_components
- storage_components
- compute_components
- monitoring_logging
- automation_level
- compliance_focus
- cost_optimization
- scalability_design

Return only valid JSON."""

            response = self.client.messages.create(
                model=self.model,
                max_tokens=1000,
                messages=[{"role": "user", "content": prompt}]
            )
            
            # Parse Claude's response to extract semantic features
            analysis = self._parse_semantic_analysis(response.content[0].text)
            
            # Convert semantic analysis to embedding vector
            embedding = self._analysis_to_vector(analysis, text)
            
            return embedding
            
        except Exception as e:
            logger.error(f"Error generating embedding with Claude: {e}")
            # Return a hash-based fallback embedding
            return self._fallback_embedding(text)
    
    def _parse_semantic_analysis(self, response_text: str) -> Dict[str, float]:
        """Parse Claude's semantic analysis response."""
        try:
            # Try to extract JSON from the response
            start_idx = response_text.find('{')
            end_idx = response_text.rfind('}') + 1
            
            if start_idx >= 0 and end_idx > start_idx:
                json_str = response_text[start_idx:end_idx]
                analysis = json.loads(json_str)
                
                # Ensure all expected dimensions are present
                default_dimensions = {
                    "infrastructure_complexity": 0.5,
                    "security_focus": 0.5,
                    "networking_components": 0.5,
                    "storage_components": 0.5,
                    "compute_components": 0.5,
                    "monitoring_logging": 0.5,
                    "automation_level": 0.5,
                    "compliance_focus": 0.5,
                    "cost_optimization": 0.5,
                    "scalability_design": 0.5
                }
                
                # Merge with defaults
                for key, default_val in default_dimensions.items():
                    if key not in analysis:
                        analysis[key] = default_val
                
                return analysis
            
        except (json.JSONDecodeError, KeyError) as e:
            logger.warning(f"Failed to parse semantic analysis: {e}")
        
        # Return default analysis if parsing fails
        return {
            "infrastructure_complexity": 0.5,
            "security_focus": 0.5,
            "networking_components": 0.5,
            "storage_components": 0.5,
            "compute_components": 0.5,
            "monitoring_logging": 0.5,
            "automation_level": 0.5,
            "compliance_focus": 0.5,
            "cost_optimization": 0.5,
            "scalability_design": 0.5
        }
    
    def _analysis_to_vector(self, analysis: Dict[str, float], text: str) -> List[float]:
        """Convert semantic analysis to embedding vector."""
        import hashlib
        import math
        
        # Start with semantic dimensions
        vector = list(analysis.values())
        
        # Add text-based features
        text_lower = text.lower()
        
        # Resource type features (expand vector)
        aws_resources = ["aws_", "s3", "ec2", "rds", "lambda", "vpc", "iam"]
        azure_resources = ["azurerm_", "azure", "resource_group"]
        gcp_resources = ["google_", "gcp", "project"]
        
        for resource_list in [aws_resources, azure_resources, gcp_resources]:
            score = sum(1 for r in resource_list if r in text_lower) / len(resource_list)
            vector.append(min(score, 1.0))
        
        # Configuration complexity features
        brace_count = text.count('{') + text.count('}')
        vector.append(min(brace_count / 100.0, 1.0))
        
        # Security-related keywords
        security_keywords = ["security", "policy", "role", "permission", "encrypt", "ssl", "tls"]
        security_score = sum(1 for kw in security_keywords if kw in text_lower) / len(security_keywords)
        vector.append(min(security_score, 1.0))
        
        # Add hash-based features for uniqueness
        text_hash = hashlib.md5(text.encode()).hexdigest()
        for i in range(0, len(text_hash), 2):
            hex_val = int(text_hash[i:i+2], 16)
            vector.append(hex_val / 255.0)
        
        # Pad or truncate to target dimension
        while len(vector) < self._dimension:
            # Add derived features based on existing ones
            if len(vector) >= 2:
                vector.append((vector[-1] + vector[-2]) / 2)
            else:
                vector.append(0.5)
        
        vector = vector[:self._dimension]
        
        # Normalize vector
        magnitude = math.sqrt(sum(x * x for x in vector))
        if magnitude > 0:
            vector = [x / magnitude for x in vector]
        
        return vector
    
    def _fallback_embedding(self, text: str) -> List[float]:
        """Generate a fallback embedding based on text hash."""
        import hashlib
        import math
        
        # Create a deterministic embedding based on text content
        text_hash = hashlib.sha256(text.encode()).hexdigest()
        
        # Convert hash to vector
        vector = []
        for i in range(0, len(text_hash), 2):
            if len(vector) >= self._dimension:
                break
            hex_val = int(text_hash[i:i+2], 16)
            vector.append((hex_val - 127.5) / 127.5)  # Normalize to [-1, 1]
        
        # Pad if necessary
        while len(vector) < self._dimension:
            vector.append(0.0)
        
        # Normalize vector
        magnitude = math.sqrt(sum(x * x for x in vector))
        if magnitude > 0:
            vector = [x / magnitude for x in vector]
        
        return vector
    
    def get_dimension(self) -> int:
        """Get embedding dimension."""
        return self._dimension
    
    def is_available(self) -> bool:
        """Check if provider is available."""
        return self.client is not None and self.api_key is not None
    
    def get_provider_info(self) -> Dict[str, Any]:
        """Get provider information."""
        return {
            "name": "AnthropicEmbeddingProvider",
            "model": self.model,
            "dimension": self._dimension,
            "available": self.is_available()
        }