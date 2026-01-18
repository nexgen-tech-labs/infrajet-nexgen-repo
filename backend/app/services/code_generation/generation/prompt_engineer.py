"""
Prompt Engineer for dynamic prompt construction in code generation.

This module provides intelligent prompt engineering capabilities that construct
context-aware prompts for Terraform code generation based on user queries
and retrieved context from the RAG system.
"""

from typing import List, Dict, Any, Optional, Union
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path

from app.services.code_generation.rag.retriever import RetrievedDocument
from logconfig.logger import get_logger

logger = get_logger()


class GenerationScenario(Enum):
    """Types of code generation scenarios."""
    NEW_RESOURCE = "new_resource"
    MODIFY_RESOURCE = "modify_resource"
    NEW_MODULE = "new_module"
    MODIFY_MODULE = "modify_module"
    NEW_VARIABLES = "new_variables"
    MODIFY_VARIABLES = "modify_variables"
    NEW_OUTPUTS = "new_outputs"
    MODIFY_OUTPUTS = "modify_outputs"
    COMPLETE_FILE = "complete_file"
    FIX_ISSUES = "fix_issues"


@dataclass
class PromptContext:
    """Context information for prompt construction."""
    user_query: str
    retrieved_documents: List[RetrievedDocument] = field(default_factory=list)
    scenario: GenerationScenario = GenerationScenario.NEW_RESOURCE
    existing_code: Optional[str] = None
    target_file_path: Optional[str] = None
    repository_context: Optional[str] = None
    terraform_version: str = "1.0"
    provider_requirements: Dict[str, str] = field(default_factory=dict)
    cloud_provider: str = "AWS"  # Cloud provider for infrastructure generation


@dataclass
class EngineeredPrompt:
    """Engineered prompt with system and user messages."""
    system_message: str
    user_message: str
    context_summary: str = ""
    generation_metadata: Dict[str, Any] = field(default_factory=dict)


class PromptEngineer:
    """
    Intelligent prompt engineering for Terraform code generation.

    This class constructs context-aware prompts that incorporate retrieved
    context, best practices, and scenario-specific guidance for optimal
    code generation results.
    """

    def __init__(self):
        """Initialize the prompt engineer."""
        self.max_context_length = 8000  # Maximum context length in characters
        self.max_documents = 5  # Maximum documents to include in context

        # Initialize prompt templates
        self._init_templates()

        logger.info("PromptEngineer initialized")

    def _init_templates(self):
        """Initialize prompt templates for different scenarios."""
        self.templates = {
            "system_base": """
You are an expert Terraform infrastructure engineer with deep knowledge of:
- Terraform best practices and HCL syntax
- Cloud provider resources (AWS, Azure, GCP)
- Infrastructure as Code patterns
- Security and compliance standards
- Cost optimization strategies

Your task is to generate high-quality, production-ready Terraform code that follows industry standards.

IMPORTANT: Generate ONLY clean HCL code without any markdown formatting, code blocks, headers, explanatory text, or additional commentary. Output should be pure Terraform configuration that can be directly used in .tf files.
""",

            "user_base": """
Generate Terraform code for the following requirement:

Requirement: {user_query}

Context Information:
{context_summary}

Guidelines:
- Use Terraform 1.0+ syntax and features
- Follow resource naming conventions
- Include appropriate variables and outputs
- Add comments for complex logic
- Ensure security best practices
- Use data sources when appropriate
- Include error handling where relevant

Existing Code (if modifying):
{existing_code}

Generate the complete Terraform code:
""",

            "new_resource": """
Resource Creation Guidelines:
- Use descriptive resource names with proper prefixes
- Include all required arguments
- Add lifecycle blocks for resource management
- Use depends_on when necessary
- Include validation rules in variables
""",

            "modify_resource": """
Resource Modification Guidelines:
- Preserve existing resource configuration
- Only modify specified attributes
- Maintain backward compatibility
- Update dependencies if needed
- Add migration considerations
""",

            "module_creation": """
Module Creation Guidelines:
- Create reusable, parameterized modules
- Include comprehensive input validation
- Provide clear documentation
- Use consistent naming conventions
- Include examples in comments
""",

            "security_focus": """
Security Best Practices:
- Use least privilege principles
- Implement proper encryption
- Add security groups and network ACLs
- Use secrets management (Vault, SSM, etc.)
- Include compliance tags
- Implement monitoring and logging
""",

            "cost_optimization": """
Cost Optimization:
- Use appropriate instance types
- Implement auto-scaling where applicable
- Use reserved instances or savings plans
- Implement resource tagging for cost tracking
- Consider spot instances for non-critical workloads
"""
        }

    async def engineer_prompt(self, context: PromptContext) -> EngineeredPrompt:
        """
        Engineer a comprehensive prompt based on the context.

        Args:
            context: Prompt context with query and retrieved documents

        Returns:
            EngineeredPrompt with system and user messages
        """
        try:
            # Build context summary from retrieved documents
            context_summary = await self._build_context_summary(context)

            # Select appropriate template based on scenario
            system_message = await self._build_system_message(context)
            user_message = await self._build_user_message(context, context_summary)

            # Create metadata
            metadata = {
                "scenario": context.scenario.value,
                "documents_used": len(context.retrieved_documents),
                "context_length": len(context_summary),
                "has_existing_code": context.existing_code is not None,
                "target_file": context.target_file_path
            }

            engineered_prompt = EngineeredPrompt(
                system_message=system_message,
                user_message=user_message,
                context_summary=context_summary,
                generation_metadata=metadata
            )

            logger.info(
                f"Engineered prompt for scenario {context.scenario.value} "
                f"using {len(context.retrieved_documents)} documents"
            )

            return engineered_prompt

        except Exception as e:
            logger.error(f"Error engineering prompt: {e}")
            # Return a basic prompt as fallback
            return self._create_fallback_prompt(context)

    async def _build_context_summary(self, context: PromptContext) -> str:
        """
        Build a summary of retrieved context for inclusion in prompts.

        Args:
            context: Prompt context

        Returns:
            Formatted context summary
        """
        if not context.retrieved_documents:
            return "No relevant context found in the codebase."

        # Sort documents by relevance score
        sorted_docs = sorted(
            context.retrieved_documents,
            key=lambda x: x.similarity_score,
            reverse=True
        )

        # Limit number of documents
        docs_to_use = sorted_docs[:self.max_documents]

        context_parts = []
        total_length = 0

        for i, doc in enumerate(docs_to_use):
            # Check if adding this document would exceed context length
            doc_content = f"Example {i+1} (Relevance: {doc.similarity_score:.2f})\n{doc.content}\n"
            if total_length + len(doc_content) > self.max_context_length:
                break

            context_parts.append(doc_content)
            total_length += len(doc_content)

            # Add metadata if available
            if doc.metadata:
                meta_info = []
                if doc.file_path:
                    meta_info.append(f"File: {doc.file_path}")
                if doc.repository_name:
                    meta_info.append(f"Repository: {doc.repository_name}")
                if doc.source_type:
                    meta_info.append(f"Type: {doc.source_type}")

                if meta_info:
                    context_parts.append(f"Source: {', '.join(meta_info)}\n")

        if not context_parts:
            return "Context available but exceeded length limits."

        summary = "\n".join(context_parts)

        # Add repository context if provided
        if context.repository_context:
            summary = f"Repository Context:\n{context.repository_context}\n\nRelevant Code Examples:\n{summary}"

        return summary

    async def _build_system_message(self, context: PromptContext) -> str:
        """
        Build the system message based on the scenario.

        Args:
            context: Prompt context

        Returns:
            System message string
        """
        system_parts = [self.templates["system_base"]]

        # Add scenario-specific guidance
        if context.scenario == GenerationScenario.NEW_RESOURCE:
            system_parts.append(self.templates["new_resource"])
        elif context.scenario == GenerationScenario.MODIFY_RESOURCE:
            system_parts.append(self.templates["modify_resource"])
        elif context.scenario in [GenerationScenario.NEW_MODULE, GenerationScenario.MODIFY_MODULE]:
            system_parts.append(self.templates["module_creation"])

        # Add security and cost optimization for production scenarios
        if context.scenario in [GenerationScenario.COMPLETE_FILE, GenerationScenario.NEW_MODULE]:
            system_parts.append(self.templates["security_focus"])
            system_parts.append(self.templates["cost_optimization"])

        # Add provider-specific guidance
        if context.provider_requirements:
            provider_info = "\nProvider Requirements:\n"
            for provider, version in context.provider_requirements.items():
                provider_info += f"- {provider}: {version}\n"
            system_parts.append(provider_info)

        return "\n".join(system_parts)

    async def _build_user_message(
        self,
        context: PromptContext,
        context_summary: str
    ) -> str:
        """
        Build the user message with query and context.

        Args:
            context: Prompt context
            context_summary: Summary of retrieved context

        Returns:
            User message string
        """
        # Format existing code if provided
        existing_code = ""
        if context.existing_code:
            existing_code = context.existing_code
        else:
            existing_code = "None"

        # Build the user message
        user_message = self.templates["user_base"].format(
            user_query=context.user_query,
            context_summary=context_summary,
            existing_code=existing_code
        )

        # Add cloud provider information
        if context.cloud_provider and context.cloud_provider.upper() != "AWS":
            user_message += f"\n\nCloud Provider: {context.cloud_provider.upper()}"
            user_message += f"\nPlease generate infrastructure code specifically for {context.cloud_provider.upper()}."
        else:
            user_message += f"\n\nCloud Provider: AWS"
            user_message += f"\nPlease generate infrastructure code for Amazon Web Services (AWS)."

        # Add scenario-specific instructions
        scenario_instructions = await self._get_scenario_instructions(context)
        if scenario_instructions:
            user_message += f"\nScenario-Specific Instructions:\n{scenario_instructions}"

        # Add file path information if available
        if context.target_file_path:
            user_message += f"\nTarget File: {context.target_file_path}"

        return user_message

    async def _get_scenario_instructions(self, context: PromptContext) -> str:
        """
        Get scenario-specific instructions.

        Args:
            context: Prompt context

        Returns:
            Scenario-specific instruction string
        """
        instructions = []

        if context.scenario == GenerationScenario.NEW_RESOURCE:
            instructions.append("- Create a new resource block with all required arguments")
            instructions.append("- Use appropriate resource types and naming conventions")
            instructions.append("- Include variables for configurable values")

        elif context.scenario == GenerationScenario.MODIFY_RESOURCE:
            instructions.append("- Modify the existing resource configuration as specified")
            instructions.append("- Preserve existing working configuration")
            instructions.append("- Add new arguments or modify existing ones carefully")

        elif context.scenario == GenerationScenario.NEW_MODULE:
            instructions.append("- Create a complete, reusable module structure")
            instructions.append("- Include variables.tf, outputs.tf, and main.tf")
            instructions.append("- Add comprehensive documentation and examples")

        elif context.scenario == GenerationScenario.MODIFY_MODULE:
            instructions.append("- Update the module while maintaining backward compatibility")
            instructions.append("- Add new variables or outputs as needed")
            instructions.append("- Update documentation accordingly")

        elif context.scenario == GenerationScenario.FIX_ISSUES:
            instructions.append("- Identify and fix syntax or logical errors")
            instructions.append("- Improve code quality and follow best practices")
            instructions.append("- Add error handling and validation")

        return "\n".join(instructions) if instructions else ""

    def _create_fallback_prompt(self, context: PromptContext) -> EngineeredPrompt:
        """
        Create a basic fallback prompt when engineering fails.

        Args:
            context: Prompt context

        Returns:
            Basic EngineeredPrompt
        """
        return EngineeredPrompt(
            system_message=self.templates["system_base"],
            user_message=f"Please generate Terraform code for: {context.user_query}\n\nIMPORTANT: Generate ONLY clean HCL code without any markdown formatting, code blocks, headers, explanatory text, or additional commentary.",
            context_summary="Fallback mode - limited context available",
            generation_metadata={"fallback": True, "error": "Prompt engineering failed"}
        )

    async def engineer_prompt_for_file_creation(
        self,
        user_query: str,
        retrieved_documents: List[RetrievedDocument],
        file_type: str = "resource",
        repository_context: Optional[str] = None
    ) -> EngineeredPrompt:
        """
        Convenience method for file creation scenarios.

        Args:
            user_query: User's generation request
            retrieved_documents: Retrieved context documents
            file_type: Type of file to create ("resource", "module", "variables", etc.)
            repository_context: Additional repository context

        Returns:
            EngineeredPrompt for file creation
        """
        # Map file type to scenario
        scenario_map = {
            "resource": GenerationScenario.NEW_RESOURCE,
            "module": GenerationScenario.NEW_MODULE,
            "variables": GenerationScenario.NEW_VARIABLES,
            "outputs": GenerationScenario.NEW_OUTPUTS
        }

        scenario = scenario_map.get(file_type, GenerationScenario.NEW_RESOURCE)

        context = PromptContext(
            user_query=user_query,
            retrieved_documents=retrieved_documents,
            scenario=scenario,
            repository_context=repository_context
        )

        return await self.engineer_prompt(context)

    async def engineer_prompt_for_modification(
        self,
        user_query: str,
        existing_code: str,
        retrieved_documents: List[RetrievedDocument],
        modification_type: str = "resource"
    ) -> EngineeredPrompt:
        """
        Convenience method for code modification scenarios.

        Args:
            user_query: User's modification request
            existing_code: Current code to modify
            retrieved_documents: Retrieved context documents
            modification_type: Type of modification ("resource", "module", etc.)

        Returns:
            EngineeredPrompt for modification
        """
        # Map modification type to scenario
        scenario_map = {
            "resource": GenerationScenario.MODIFY_RESOURCE,
            "module": GenerationScenario.MODIFY_MODULE,
            "variables": GenerationScenario.MODIFY_VARIABLES,
            "outputs": GenerationScenario.MODIFY_OUTPUTS
        }

        scenario = scenario_map.get(modification_type, GenerationScenario.MODIFY_RESOURCE)

        context = PromptContext(
            user_query=user_query,
            retrieved_documents=retrieved_documents,
            scenario=scenario,
            existing_code=existing_code
        )

        return await self.engineer_prompt(context)