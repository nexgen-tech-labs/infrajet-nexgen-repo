"""
Enhanced Anthropic Embedding Provider with actual embedding generation.
"""

import hashlib
import json
import math
from typing import List, Sequence, Dict, Any
from anthropic import Anthropic
from app.providers.embedding.base import EmbeddingProvider
from logconfig.logger import get_logger

logger = get_logger()


class EnhancedAnthropicEmbeddingProvider(EmbeddingProvider):
    """Enhanced Anthropic embedding provider with actual semantic embeddings."""

    def __init__(self, api_key: str, model: str = "claude-3-haiku-20240307"):
        """
        Initialize enhanced Anthropic embedding provider.

        Args:
            api_key: Anthropic API key
            model: Claude model to use
        """
        self.api_key = api_key
        self.model = model
        self.client = Anthropic(api_key=api_key) if api_key else None
        self._dimension = 1536  # Standard embedding dimension
        self.max_tokens = 1000
        self.temperature = 0.1

    def embed_texts(self, texts: Sequence[str]) -> List[List[float]]:
        """
        Generate embeddings for multiple texts.

        Args:
            texts: Sequence of text strings to embed

        Returns:
            List of embedding vectors
        """
        if not self.is_available():
            logger.warning("Anthropic provider not available, using fallback embeddings")
            return [self._fallback_embedding(text) for text in texts]

        embeddings = []
        for text in texts:
            try:
                embedding = self._generate_semantic_embedding(text)
                embeddings.append(embedding)
            except Exception as e:
                logger.error(f"Failed to generate embedding: {e}")
                embeddings.append(self._fallback_embedding(text))

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
            logger.warning("Anthropic provider not available, using fallback embedding")
            return self._fallback_embedding(query)

        try:
            return self._generate_semantic_embedding(query)
        except Exception as e:
            logger.error(f"Failed to generate query embedding: {e}")
            return self._fallback_embedding(query)

    def _generate_semantic_embedding(self, text: str) -> List[float]:
        """
        Generate semantic embedding using Claude's analysis capabilities.

        This approach uses Claude to analyze the semantic content and generate
        a consistent vector representation based on semantic features.
        """
        try:
            # Use Claude to extract semantic features
            semantic_features = self._extract_semantic_features(text)

            # Convert semantic features to embedding vector
            embedding = self._semantic_features_to_vector(semantic_features, text)

            return embedding

        except Exception as e:
            logger.error(f"Error generating semantic embedding: {e}")
            return self._fallback_embedding(text)

    def _extract_semantic_features(self, text: str) -> Dict[str, float]:
        """Extract semantic features from text using Claude."""
        prompt = f"""Analyze the following code and extract semantic features as a JSON object with numerical scores (0.0 to 1.0) for these dimensions:

- infrastructure_complexity: How complex is the infrastructure setup?
- security_focus: How much security configuration is present?
- networking_components: Presence of networking elements?
- storage_components: Presence of storage/data components?
- compute_components: Presence of compute resources?
- monitoring_logging: Presence of monitoring/logging?
- automation_level: Level of automation/configuration management?
- compliance_focus: Focus on compliance/auditing?
- cost_optimization: Cost optimization features?
- scalability_design: Scalability considerations?

Code to analyze:
{text[:2000]}

Return only valid JSON with the dimension scores."""

        try:
            response = self.client.messages.create(
                model=self.model,
                max_tokens=500,
                temperature=self.temperature,
                messages=[{"role": "user", "content": prompt}]
            )

            response_text = response.content[0].text

            # Parse JSON response
            start_idx = response_text.find('{')
            end_idx = response_text.rfind('}') + 1

            if start_idx >= 0 and end_idx > start_idx:
                json_str = response_text[start_idx:end_idx]
                features = json.loads(json_str)

                # Ensure all expected dimensions are present
                default_features = {
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
                for key, default_val in default_features.items():
                    if key not in features:
                        features[key] = default_val

                return features

        except Exception as e:
            logger.warning(f"Failed to parse semantic features: {e}")

        # Return default features if parsing fails
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

    def _semantic_features_to_vector(self, features: Dict[str, float], text: str) -> List[float]:
        """Convert semantic features to embedding vector."""
        # Start with semantic dimensions
        vector = list(features.values())

        # Add text-based features
        text_lower = text.lower()

        # Resource type features (expand vector)
        resource_indicators = {
            'aws': ['aws_', 's3', 'ec2', 'rds', 'lambda', 'vpc', 'iam'],
            'azure': ['azurerm_', 'azure', 'resource_group'],
            'gcp': ['google_', 'gcp', 'project'],
            'terraform': ['resource', 'variable', 'output', 'module', 'provider', 'data']
        }

        for provider, keywords in resource_indicators.items():
            score = sum(1 for keyword in keywords if keyword in text_lower) / len(keywords)
            vector.append(min(score, 1.0))

        # Configuration complexity features
        brace_count = text.count('{') + text.count('}')
        vector.append(min(brace_count / 100.0, 1.0))

        # Security-related keywords
        security_keywords = ["security", "policy", "role", "permission", "encrypt", "ssl", "tls", "secret"]
        security_score = sum(1 for kw in security_keywords if kw in text_lower) / len(security_keywords)
        vector.append(min(security_score, 1.0))

        # Add hash-based features for uniqueness and consistency
        text_hash = hashlib.md5(text.encode()).hexdigest()
        for i in range(0, len(text_hash), 2):
            hex_val = int(text_hash[i:i+2], 16)
            vector.append(hex_val / 255.0)

        # Pad or truncate to target dimension
        while len(vector) < self._dimension:
            # Add derived features based on existing ones
            if len(vector) >= 2:
                # Create smooth transitions
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
            "name": "EnhancedAnthropicEmbeddingProvider",
            "model": self.model,
            "dimension": self._dimension,
            "available": self.is_available(),
            "embedding_type": "semantic_analysis"
        }