"""
LLM Summarization Service for generating semantic summaries of code chunks.
"""

import json
from typing import Dict, Any, List, Optional
from dataclasses import dataclass
from anthropic import Anthropic
from logconfig.logger import get_logger

logger = get_logger()


@dataclass
class CodeChunk:
    """Represents a code chunk to be summarized."""
    content: str
    file_path: str
    chunk_index: int
    language: str
    metadata: Dict[str, Any]


@dataclass
class ChunkSummary:
    """Represents a summarized code chunk."""
    original_chunk: CodeChunk
    summary_text: str
    summary_type: str
    confidence_score: float
    processing_metadata: Dict[str, Any]


class LLMSummarizationService:
    """Service for generating semantic summaries of code chunks using LLM."""

    def __init__(self, api_key: str, model: str = "claude-3-haiku-20240307"):
        """
        Initialize the LLM summarization service.

        Args:
            api_key: Anthropic API key
            model: Claude model to use for summarization
        """
        self.api_key = api_key
        self.model = model
        self.client = Anthropic(api_key=api_key) if api_key else None
        self.max_tokens = 1000
        self.temperature = 0.3

    async def summarize_chunk(self, chunk: CodeChunk) -> ChunkSummary:
        """
        Generate a semantic summary of a code chunk.

        Args:
            chunk: Code chunk to summarize

        Returns:
            ChunkSummary with semantic summary
        """
        try:
            if not self.is_available():
                return self._create_fallback_summary(chunk)

            # Generate summary using Claude
            summary_text = await self._generate_summary_with_claude(chunk)

            # Classify summary type
            summary_type = self._classify_summary_type(summary_text, chunk)

            # Calculate confidence score
            confidence_score = self._calculate_confidence_score(chunk, summary_text)

            # Create processing metadata
            processing_metadata = {
                "model": self.model,
                "input_tokens": len(chunk.content.split()),
                "output_tokens": len(summary_text.split()),
                "processing_method": "claude_analysis"
            }

            return ChunkSummary(
                original_chunk=chunk,
                summary_text=summary_text,
                summary_type=summary_type,
                confidence_score=confidence_score,
                processing_metadata=processing_metadata
            )

        except Exception as e:
            logger.error(f"Failed to summarize chunk: {e}")
            return self._create_fallback_summary(chunk)

    async def _generate_summary_with_claude(self, chunk: CodeChunk) -> str:
        """Generate summary using Claude."""
        prompt = self._build_summarization_prompt(chunk)

        response = self.client.messages.create(
            model=self.model,
            max_tokens=self.max_tokens,
            temperature=self.temperature,
            messages=[{"role": "user", "content": prompt}]
        )

        return response.content[0].text.strip()

    def _build_summarization_prompt(self, chunk: CodeChunk) -> str:
        """Build the summarization prompt for Claude."""
        language = chunk.language or "code"

        prompt = f"""Analyze the following {language} code and provide a concise semantic summary.

Focus on:
1. What this code does (functionality)
2. Key components and their relationships
3. Important patterns or configurations
4. Security or compliance implications (if any)
5. Dependencies or prerequisites

Code to analyze:
```{language}
{chunk.content[:3000]}  # Limit content length
```

Provide a summary in 2-3 sentences that captures the essential functionality and purpose.
Be specific and technical, but avoid unnecessary details."""

        return prompt

    def _classify_summary_type(self, summary: str, chunk: CodeChunk) -> str:
        """Classify the type of summary generated."""
        summary_lower = summary.lower()

        # Infrastructure patterns
        if any(keyword in summary_lower for keyword in ['resource', 'infrastructure', 'deployment', 'provisioning']):
            return 'infrastructure'

        # Configuration patterns
        elif any(keyword in summary_lower for keyword in ['config', 'variable', 'parameter', 'setting']):
            return 'configuration'

        # Security patterns
        elif any(keyword in summary_lower for keyword in ['security', 'policy', 'permission', 'access', 'encryption']):
            return 'security'

        # Data patterns
        elif any(keyword in summary_lower for keyword in ['data', 'storage', 'database', 'bucket']):
            return 'data'

        # Network patterns
        elif any(keyword in summary_lower for keyword in ['network', 'vpc', 'subnet', 'firewall', 'routing']):
            return 'network'

        # Compute patterns
        elif any(keyword in summary_lower for keyword in ['compute', 'instance', 'lambda', 'function', 'container']):
            return 'compute'

        # Monitoring patterns
        elif any(keyword in summary_lower for keyword in ['monitor', 'log', 'metric', 'alert', 'dashboard']):
            return 'monitoring'

        else:
            return 'general'

    def _calculate_confidence_score(self, chunk: CodeChunk, summary: str) -> float:
        """Calculate confidence score for the summary."""
        # Base confidence
        confidence = 0.5

        # Increase confidence based on summary length (too short = low confidence)
        summary_length = len(summary.split())
        if 10 <= summary_length <= 50:
            confidence += 0.2
        elif summary_length < 5:
            confidence -= 0.3

        # Increase confidence for specific technical terms
        technical_terms = ['resource', 'configuration', 'function', 'service', 'component']
        technical_count = sum(1 for term in technical_terms if term in summary.lower())
        confidence += min(technical_count * 0.1, 0.3)

        # Decrease confidence for generic terms
        generic_terms = ['code', 'does', 'provides', 'handles', 'manages']
        generic_count = sum(1 for term in generic_terms if term in summary.lower())
        if generic_count > 3:
            confidence -= 0.1

        # Ensure confidence is between 0 and 1
        return max(0.0, min(1.0, confidence))

    def _create_fallback_summary(self, chunk: CodeChunk) -> ChunkSummary:
        """Create a fallback summary when LLM is unavailable."""
        # Simple extractive summary based on first few lines
        lines = chunk.content.strip().split('\n')[:3]
        fallback_text = ' '.join(line.strip() for line in lines if line.strip())

        if len(fallback_text) > 200:
            fallback_text = fallback_text[:200] + "..."

        return ChunkSummary(
            original_chunk=chunk,
            summary_text=fallback_text or "Code chunk summary unavailable",
            summary_type="fallback",
            confidence_score=0.3,
            processing_metadata={
                "processing_method": "fallback",
                "reason": "LLM_unavailable"
            }
        )

    def is_available(self) -> bool:
        """Check if the service is available."""
        return self.client is not None and self.api_key is not None

    async def batch_summarize(self, chunks: List[CodeChunk]) -> List[ChunkSummary]:
        """Summarize multiple chunks in batch."""
        summaries = []
        for chunk in chunks:
            summary = await self.summarize_chunk(chunk)
            summaries.append(summary)
        return summaries