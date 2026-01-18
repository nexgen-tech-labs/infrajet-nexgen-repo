"""
Anthropic Project Intelligence Service.

This module provides intelligent project naming and description generation
using Anthropic's Claude model to enhance the user experience when creating
projects through the /generate endpoint.
"""

import asyncio
from typing import Optional, Dict, Any
from dataclasses import dataclass
from datetime import datetime

from app.services.code_generation.llm_providers.provider_factory import ProviderFactory
from app.services.code_generation.generation.prompt_engineer import GenerationScenario
from logconfig.logger import get_logger

logger = get_logger()


@dataclass
class ProjectIntelligenceResult:
    """Result from project intelligence analysis."""
    suggested_name: Optional[str] = None
    generated_description: Optional[str] = None
    confidence_score: float = 0.0
    reasoning: Optional[str] = None
    processing_time_ms: float = 0.0


class AnthropicProjectIntelligence:
    """
    Service for intelligent project naming and description generation.
    
    Uses Anthropic's Claude model to analyze code generation queries and
    automatically generate meaningful project names and descriptions.
    """

    def __init__(self):
        """Initialize the project intelligence service."""
        self.provider_factory = ProviderFactory()
        self.default_provider = "claude"
        logger.info("AnthropicProjectIntelligence service initialized")

    async def generate_project_intelligence(
        self,
        query: str,
        scenario: GenerationScenario,
        user_provided_name: Optional[str] = None,
        existing_code: Optional[str] = None,
        repository_name: Optional[str] = None
    ) -> ProjectIntelligenceResult:
        """
        Generate intelligent project name and description based on the code generation query.

        Args:
            query: User's code generation request
            scenario: Type of generation scenario
            user_provided_name: Optional user-provided project name
            existing_code: Optional existing code context
            repository_name: Optional repository context

        Returns:
            ProjectIntelligenceResult with generated name and description
        """
        start_time = datetime.now()
        
        try:
            # Build context for the intelligence generation
            context = self._build_intelligence_context(
                query=query,
                scenario=scenario,
                user_provided_name=user_provided_name,
                existing_code=existing_code,
                repository_name=repository_name
            )

            # Generate project intelligence using Claude
            result = await self._generate_with_claude(context)
            
            processing_time = (datetime.now() - start_time).total_seconds() * 1000
            result.processing_time_ms = processing_time
            
            logger.info(
                f"Project intelligence generated successfully. "
                f"Name: {result.suggested_name}, "
                f"Confidence: {result.confidence_score:.2f}, "
                f"Time: {processing_time:.2f}ms"
            )
            
            return result

        except Exception as e:
            processing_time = (datetime.now() - start_time).total_seconds() * 1000
            logger.error(f"Failed to generate project intelligence: {str(e)}")
            
            # Return fallback result
            return ProjectIntelligenceResult(
                suggested_name=self._generate_fallback_name(query, user_provided_name),
                generated_description=self._generate_fallback_description(query, scenario),
                confidence_score=0.3,
                reasoning="Fallback generation due to service error",
                processing_time_ms=processing_time
            )

    def _build_intelligence_context(
        self,
        query: str,
        scenario: GenerationScenario,
        user_provided_name: Optional[str] = None,
        existing_code: Optional[str] = None,
        repository_name: Optional[str] = None
    ) -> Dict[str, Any]:
        """Build context for project intelligence generation."""
        context = {
            "query": query,
            "scenario": scenario.value,
            "user_provided_name": user_provided_name,
            "repository_name": repository_name,
            "has_existing_code": existing_code is not None,
            "existing_code_snippet": existing_code[:500] if existing_code else None
        }
        
        return context

    async def _generate_with_claude(self, context: Dict[str, Any]) -> ProjectIntelligenceResult:
        """Generate project intelligence using Claude."""
        prompt = self._build_intelligence_prompt(context)
        
        try:
            # Get Claude provider
            provider = await self.provider_factory.get_provider(self.default_provider)
            
            # Generate response
            response = await provider.generate_completion(
                prompt=prompt,
                temperature=0.3,  # Lower temperature for more consistent results
                max_tokens=500
            )
            
            # Parse the response
            return self._parse_claude_response(response, context)
            
        except Exception as e:
            logger.error(f"Claude generation failed: {str(e)}")
            raise

    def _build_intelligence_prompt(self, context: Dict[str, Any]) -> str:
        """Build the prompt for Claude to generate project intelligence."""
        user_name_context = ""
        if context.get("user_provided_name"):
            user_name_context = f"\nUser provided project name: {context['user_provided_name']}"
        
        existing_code_context = ""
        if context.get("has_existing_code"):
            existing_code_context = f"\nExisting code context: {context.get('existing_code_snippet', 'Available')}"
        
        repo_context = ""
        if context.get("repository_name"):
            repo_context = f"\nRepository context: {context['repository_name']}"

        prompt = f"""You are an expert at analyzing Terraform infrastructure code generation requests and creating meaningful project names and descriptions.

Given the following code generation request, generate a suitable project name and description:

Query: {context['query']}
Scenario: {context['scenario']}{user_name_context}{existing_code_context}{repo_context}

Please provide your response in the following JSON format:
{{
    "suggested_name": "project-name-in-kebab-case",
    "description": "A clear, concise description of what this project does",
    "confidence": 0.85,
    "reasoning": "Brief explanation of why this name and description were chosen"
}}

Guidelines:
1. Project names should be in kebab-case (lowercase with hyphens)
2. Names should be descriptive but concise (2-4 words max)
3. Descriptions should be 1-2 sentences explaining the project's purpose
4. If user provided a name, use it as inspiration but ensure it follows conventions
5. Consider the infrastructure type (AWS, Azure, GCP) if mentioned
6. Focus on the main resource or service being created
7. Confidence should be 0.7-0.95 based on how clear the request is

Examples:
- "Create an S3 bucket for storing logs" → "s3-log-storage"
- "Set up a VPC with subnets" → "vpc-network-setup"
- "Deploy a Lambda function for processing" → "lambda-processor"
"""

        return prompt

    def _parse_claude_response(self, response: str, context: Dict[str, Any]) -> ProjectIntelligenceResult:
        """Parse Claude's response into a ProjectIntelligenceResult."""
        try:
            import json
            
            # Extract JSON from response
            response_text = response.strip()
            if response_text.startswith("```json"):
                response_text = response_text[7:]
            if response_text.endswith("```"):
                response_text = response_text[:-3]
            
            parsed = json.loads(response_text.strip())
            
            return ProjectIntelligenceResult(
                suggested_name=parsed.get("suggested_name"),
                generated_description=parsed.get("description"),
                confidence_score=float(parsed.get("confidence", 0.7)),
                reasoning=parsed.get("reasoning")
            )
            
        except (json.JSONDecodeError, KeyError, ValueError) as e:
            logger.warning(f"Failed to parse Claude response: {str(e)}")
            
            # Fallback parsing - extract name and description from text
            return self._fallback_parse_response(response, context)

    def _fallback_parse_response(self, response: str, context: Dict[str, Any]) -> ProjectIntelligenceResult:
        """Fallback parsing when JSON parsing fails."""
        # Simple text extraction
        lines = response.strip().split('\n')
        suggested_name = None
        description = None
        
        for line in lines:
            line = line.strip()
            if 'name' in line.lower() and ':' in line:
                suggested_name = line.split(':', 1)[1].strip().strip('"')
            elif 'description' in line.lower() and ':' in line:
                description = line.split(':', 1)[1].strip().strip('"')
        
        return ProjectIntelligenceResult(
            suggested_name=suggested_name or self._generate_fallback_name(context['query']),
            generated_description=description or self._generate_fallback_description(context['query'], context['scenario']),
            confidence_score=0.5,
            reasoning="Fallback parsing used"
        )

    def _generate_fallback_name(self, query: str, user_provided_name: Optional[str] = None) -> str:
        """Generate a fallback project name when AI generation fails."""
        if user_provided_name:
            # Clean up user provided name
            return user_provided_name.lower().replace(' ', '-').replace('_', '-')
        
        # Extract key terms from query
        query_lower = query.lower()
        
        # Common infrastructure terms mapping
        term_mappings = {
            's3': 's3-bucket',
            'bucket': 's3-bucket',
            'vpc': 'vpc-network',
            'lambda': 'lambda-function',
            'ec2': 'ec2-instance',
            'rds': 'rds-database',
            'api gateway': 'api-gateway',
            'load balancer': 'load-balancer',
            'cloudfront': 'cloudfront-cdn',
            'iam': 'iam-roles',
            'security group': 'security-groups'
        }
        
        for term, name in term_mappings.items():
            if term in query_lower:
                return name
        
        # Generic fallback
        return "terraform-project"

    def _generate_fallback_description(self, query: str, scenario: str) -> str:
        """Generate a fallback description when AI generation fails."""
        scenario_descriptions = {
            "NEW_RESOURCE": "Creates new infrastructure resources",
            "MODIFY_RESOURCE": "Modifies existing infrastructure resources", 
            "NEW_MODULE": "Creates a new Terraform module",
            "NEW_VARIABLES": "Defines new Terraform variables",
            "NEW_OUTPUTS": "Defines new Terraform outputs"
        }
        
        base_description = scenario_descriptions.get(scenario, "Terraform infrastructure project")
        return f"{base_description} based on: {query[:100]}{'...' if len(query) > 100 else ''}"

    async def enhance_project_name(self, user_provided_name: str) -> str:
        """
        Enhance a user-provided project name to follow conventions.
        
        Args:
            user_provided_name: The name provided by the user
            
        Returns:
            Enhanced project name following kebab-case conventions
        """
        if not user_provided_name:
            return "terraform-project"
        
        # Convert to kebab-case
        enhanced_name = user_provided_name.lower()
        enhanced_name = enhanced_name.replace(' ', '-').replace('_', '-')
        
        # Remove special characters except hyphens
        import re
        enhanced_name = re.sub(r'[^a-z0-9-]', '', enhanced_name)
        
        # Remove multiple consecutive hyphens
        enhanced_name = re.sub(r'-+', '-', enhanced_name)
        
        # Remove leading/trailing hyphens
        enhanced_name = enhanced_name.strip('-')
        
        # Ensure it's not empty
        if not enhanced_name:
            return "terraform-project"
        
        return enhanced_name