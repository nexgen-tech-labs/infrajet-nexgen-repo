"""
Autonomous Chat Service for intelligent conversation flow.

This service provides LLM-driven prompt analysis, clarification question generation,
and integration with the code generation orchestrator for autonomous chat conversations.
"""

import json
import uuid
from datetime import datetime
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, field
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.code_generation.llm_providers.provider_factory import ProviderFactory
from app.services.code_generation.config.settings import get_code_generation_settings
from app.services.code_generation.orchestrator import CodeGenerationOrchestrator
from app.services.chat.conversation_context_manager import ConversationContextManager
from logconfig.logger import get_logger

logger = get_logger()
settings = get_code_generation_settings()


@dataclass
class PromptAnalysis:
    """Result of prompt completeness analysis."""
    is_complete: bool
    confidence_score: float
    missing_elements: List[str] = field(default_factory=list)
    clarification_needed: bool = False
    suggested_questions: List[str] = field(default_factory=list)
    intent_classification: Optional[str] = None
    analysis_metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ClarificationRequest:
    """Represents a clarification request to the user."""
    request_id: str
    thread_id: str
    questions: List[str]
    context_summary: str
    created_at: datetime
    status: str = "pending"  # pending, answered, expired
    user_responses: Dict[str, str] = field(default_factory=dict)
    answered_at: Optional[datetime] = None


class AutonomousChatServiceError(Exception):
    """Base exception for autonomous chat service operations."""
    pass


class AutonomousChatService:
    """
    Service for autonomous chat functionality with LLM-driven analysis.

    Provides intelligent prompt analysis, clarification question generation,
    and seamless integration with code generation orchestrator.
    """

    def __init__(self, db_session: AsyncSession):
        """
        Initialize the autonomous chat service.

        Args:
            db_session: Database session for operations
        """
        self.db = db_session
        self.provider_factory = ProviderFactory()
        self.code_orchestrator = CodeGenerationOrchestrator(db_session)
        self.context_manager = ConversationContextManager(db_session)

        # Active clarification requests
        self.active_clarifications: Dict[str, ClarificationRequest] = {}

        logger.info("AutonomousChatService initialized")

    async def analyze_prompt_completeness(
        self,
        prompt: str,
        thread_id: Optional[str] = None,
        context_history: Optional[List[Dict[str, Any]]] = None
    ) -> PromptAnalysis:
        """
        Analyze if a user prompt has sufficient information for code generation.

        Args:
            prompt: The user's prompt to analyze
            thread_id: Optional conversation thread ID for context
            context_history: Optional previous conversation history

        Returns:
            PromptAnalysis: Analysis result with completeness assessment

        Raises:
            AutonomousChatServiceError: If analysis fails
        """
        try:
            # Get conversation context if available
            context_summary = ""
            if thread_id:
                context_summary = await self.context_manager.summarize_context(thread_id)

            # Prepare analysis prompt for LLM
            analysis_prompt = self._build_analysis_prompt(prompt, context_summary, context_history)

            # Create LLM provider config (use Claude for analysis)
            from app.services.code_generation.llm_providers.base import LLMConfig
            config = LLMConfig(
                api_key=settings.LLM_API_KEY,
                model="claude-3-haiku-20240307",  # Fast model for analysis
                temperature=0.1,  # Low temperature for consistent analysis
                max_tokens=1000,
                timeout=30
            )
            provider = self.provider_factory.create_provider("claude", config)

            from app.services.code_generation.llm_providers.base import LLMRequest
            request = LLMRequest(
                prompt=analysis_prompt,
                config=config,
                system_message="You are an expert at analyzing software development prompts for completeness and clarity."
            )

            # Get analysis from LLM
            response = await provider.generate(request)
            analysis_result = self._parse_analysis_response(response.content)

            # Update context with intent if detected
            if thread_id and analysis_result.intent_classification:
                await self.context_manager.update_context(
                    thread_id,
                    {"intent": analysis_result.intent_classification}
                )

            logger.info(f"Analyzed prompt completeness: complete={analysis_result.is_complete}, confidence={analysis_result.confidence_score}")
            return analysis_result

        except Exception as e:
            logger.error(f"Failed to analyze prompt completeness: {e}")
            raise AutonomousChatServiceError(f"Failed to analyze prompt: {e}")

    async def generate_clarification_questions(
        self,
        prompt: str,
        analysis: PromptAnalysis,
        thread_id: Optional[str] = None
    ) -> List[str]:
        """
        Generate targeted clarification questions based on prompt analysis.

        Args:
            prompt: The original user prompt
            analysis: Result from prompt analysis
            thread_id: Optional conversation thread ID

        Returns:
            List[str]: List of clarification questions

        Raises:
            AutonomousChatServiceError: If question generation fails
        """
        try:
            if not analysis.clarification_needed or not analysis.missing_elements:
                return []

            # Build question generation prompt
            question_prompt = self._build_question_generation_prompt(
                prompt, analysis.missing_elements, thread_id
            )

            # Create LLM provider config
            from app.services.code_generation.llm_providers.base import LLMConfig
            config = LLMConfig(
                api_key=settings.LLM_API_KEY,
                model="claude-3-haiku-20240307",
                temperature=0.3,  # Slightly higher temperature for creative questions
                max_tokens=800,
                timeout=30
            )
            provider = self.provider_factory.create_provider("claude", config)

            from app.services.code_generation.llm_providers.base import LLMRequest
            request = LLMRequest(
                prompt=question_prompt,
                config=config,
                system_message="You are an expert at asking clear, specific questions to gather missing information for software development tasks."
            )

            # Generate questions
            response = await provider.generate(request)
            questions = self._parse_question_response(response.content)

            # Limit to 3 most important questions
            questions = questions[:3]

            logger.info(f"Generated {len(questions)} clarification questions")
            return questions

        except Exception as e:
            logger.error(f"Failed to generate clarification questions: {e}")
            raise AutonomousChatServiceError(f"Failed to generate questions: {e}")

    async def process_user_response(
        self,
        thread_id: str,
        clarification_id: str,
        responses: Dict[str, str]
    ) -> Dict[str, Any]:
        """
        Process user responses to clarification questions.

        Args:
            thread_id: Conversation thread ID
            clarification_id: ID of the clarification request
            responses: Dictionary mapping question indices to user answers

        Returns:
            Dict[str, Any]: Processing result with next steps

        Raises:
            AutonomousChatServiceError: If processing fails
        """
        try:
            # Get the clarification request
            if clarification_id not in self.active_clarifications:
                raise AutonomousChatServiceError(f"Clarification request {clarification_id} not found")

            clarification = self.active_clarifications[clarification_id]

            # Update clarification with responses
            clarification.user_responses.update(responses)
            clarification.status = "answered"
            clarification.answered_at = datetime.utcnow()

            # Combine original prompt with clarification responses
            enriched_prompt = await self._enrich_prompt_with_clarifications(
                clarification, responses
            )

            # Re-analyze the enriched prompt
            analysis = await self.analyze_prompt_completeness(
                enriched_prompt, thread_id
            )

            result = {
                "clarification_processed": True,
                "enriched_prompt": enriched_prompt,
                "is_now_complete": analysis.is_complete,
                "confidence_score": analysis.confidence_score,
                "next_action": "ready_for_generation" if analysis.is_complete else "needs_more_clarification",
                "additional_questions": analysis.suggested_questions if not analysis.is_complete else []
            }

            # Update context with enriched information
            await self.context_manager.update_context(thread_id, {
                "intent": analysis.intent_classification,
                "last_clarification": clarification_id
            })

            logger.info(f"Processed user response for clarification {clarification_id}: complete={result['is_now_complete']}")
            return result

        except Exception as e:
            logger.error(f"Failed to process user response: {e}")
            raise AutonomousChatServiceError(f"Failed to process response: {e}")

    async def trigger_code_generation(
        self,
        thread_id: str,
        enriched_prompt: str,
        user_id: str,
        project_id: Optional[str] = None,
        generation_options: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Trigger code generation using the enriched prompt.

        Args:
            thread_id: Conversation thread ID
            enriched_prompt: The enriched prompt ready for generation
            user_id: User ID requesting generation
            project_id: Optional project ID for context
            generation_options: Optional generation parameters

        Returns:
            Dict[str, Any]: Generation result information

        Raises:
            AutonomousChatServiceError: If generation trigger fails
        """
        try:
            # Determine generation scenario from context
            context = await self.context_manager.load_context(thread_id)
            scenario = self._determine_generation_scenario(enriched_prompt, context)

            # Prepare generation options
            options = generation_options or {}
            options.setdefault("provider_type", "claude")
            options.setdefault("temperature", 0.7)
            options.setdefault("max_tokens", 4000)

            # Get cloud provider from context and include it in the enriched prompt
            cloud_provider = "AWS"  # default
            if context and context.context_metadata and "cloud_provider" in context.context_metadata:
                cloud_provider = context.context_metadata["cloud_provider"]

            # Enhance the prompt with cloud provider information
            if cloud_provider and cloud_provider.upper() != "AWS":
                enriched_prompt = f"Using {cloud_provider.upper()} as the cloud provider: {enriched_prompt}"
            else:
                enriched_prompt = f"Using AWS as the cloud provider: {enriched_prompt}"

            # Pass cloud provider in options for the orchestrator
            options["cloud_provider"] = cloud_provider

            # Add lineage tracking
            generation_id = str(uuid.uuid4())
            await self.context_manager.add_generation_lineage(
                thread_id=thread_id,
                generation_id=generation_id,
                prompt=enriched_prompt,
                response="",  # Will be filled when generation completes
                model_used=options.get("provider_type", "claude"),
                metadata={
                    "scenario": scenario,
                    "user_id": user_id,
                    "project_id": project_id,
                    "thread_id": thread_id
                }
            )

            # Trigger async generation
            job_id = await self.code_orchestrator.generate_code_async(
                query=enriched_prompt,
                scenario=scenario,
                repository_name=options.get("repository_name"),
                existing_code=options.get("existing_code"),
                target_file_path=options.get("target_file_path"),
                **options
            )

            result = {
                "generation_triggered": True,
                "job_id": job_id,
                "generation_id": generation_id,
                "scenario": scenario.value,
                "estimated_completion": "30-120 seconds"
            }

            logger.info(f"Triggered code generation for thread {thread_id}: job_id={job_id}")
            return result

        except Exception as e:
            logger.error(f"Failed to trigger code generation: {e}")
            raise AutonomousChatServiceError(f"Failed to trigger generation: {e}")

    async def create_clarification_request(
        self,
        thread_id: str,
        questions: List[str],
        context_summary: str
    ) -> ClarificationRequest:
        """
        Create a new clarification request.

        Args:
            thread_id: Conversation thread ID
            questions: List of clarification questions
            context_summary: Summary of conversation context

        Returns:
            ClarificationRequest: The created clarification request
        """
        request = ClarificationRequest(
            request_id=str(uuid.uuid4()),
            thread_id=thread_id,
            questions=questions,
            context_summary=context_summary,
            created_at=datetime.utcnow()
        )

        self.active_clarifications[request.request_id] = request

        logger.info(f"Created clarification request {request.request_id} for thread {thread_id}")
        return request

    def _build_analysis_prompt(
        self,
        prompt: str,
        context_summary: str,
        context_history: Optional[List[Dict[str, Any]]] = None
    ) -> str:
        """Build the prompt for LLM analysis of prompt completeness."""
        history_text = ""
        if context_history:
            history_text = "\nPrevious conversation:\n" + "\n".join([
                f"User: {msg.get('content', '')}" for msg in context_history[-3:]  # Last 3 messages
            ])

        return f"""Analyze this infrastructure-as-code generation request for completeness and technical requirements.

Request: "{prompt}"

Context Summary: {context_summary}
{history_text}

Please analyze if this request contains sufficient technical details for generating working Terraform/infrastructure code. Consider:

ESSENTIAL ELEMENTS for Infrastructure Code Generation:
1. Cloud provider (AWS, Azure, GCP) and region
2. Resource specifications (instance types, storage, networking)
3. Infrastructure architecture (VPC, subnets, security groups)
4. Service integrations and dependencies
5. Naming conventions and tagging requirements
6. Compliance and security requirements
7. Deployment and scaling configurations

Respond with a JSON object containing:
{{
    "is_complete": boolean,
    "confidence_score": float (0.0-1.0),
    "missing_elements": ["list", "of", "missing", "technical", "details"],
    "clarification_needed": boolean,
    "suggested_questions": ["technical question1", "technical question2"],
    "intent_classification": "brief description of infrastructure intent",
    "analysis_metadata": {{"any": "additional insights"}}
}}

Focus on technical details needed for immediate code generation, not general requirements."""

    def _parse_analysis_response(self, response: str) -> PromptAnalysis:
        """Parse the LLM response into a PromptAnalysis object."""
        try:
            # Clean the response by removing markdown code blocks if present
            response = response.strip()
            if response.startswith('```json'):
                response = response[7:]
            if response.startswith('```'):
                response = response[3:]
            if response.endswith('```'):
                response = response[:-3]
            response = response.strip()

            # Try to find JSON object boundaries more carefully
            json_start = response.find('{')
            json_end = response.rfind('}') + 1

            if json_start == -1:
                raise ValueError("No JSON object start found in response")

            # Extract potential JSON
            json_str = response[json_start:json_end]

            # Try to parse the JSON
            try:
                data = json.loads(json_str)
            except json.JSONDecodeError as json_error:
                # If direct parsing fails, try to fix common issues
                logger.warning(f"Initial JSON parse failed: {json_error}, attempting to fix...")

                # Try to find a complete JSON object by looking for balanced braces
                brace_count = 0
                start_idx = json_start
                end_idx = json_start

                for i, char in enumerate(response[json_start:], json_start):
                    if char == '{':
                        brace_count += 1
                    elif char == '}':
                        brace_count -= 1
                        if brace_count == 0:
                            end_idx = i + 1
                            break

                if brace_count == 0:
                    json_str = response[start_idx:end_idx]
                    data = json.loads(json_str)
                else:
                    raise json_error

            return PromptAnalysis(
                is_complete=data.get("is_complete", False),
                confidence_score=data.get("confidence_score", 0.0),
                missing_elements=data.get("missing_elements", []),
                clarification_needed=data.get("clarification_needed", False),
                suggested_questions=data.get("suggested_questions", []),
                intent_classification=data.get("intent_classification"),
                analysis_metadata=data.get("analysis_metadata", {})
            )

        except (json.JSONDecodeError, KeyError, ValueError) as e:
            logger.warning(f"Failed to parse analysis response: {e}, response: {response}")
            # Return a default analysis indicating clarification needed
            return PromptAnalysis(
                is_complete=False,
                confidence_score=0.3,
                missing_elements=["Unable to analyze prompt - please provide more details"],
                clarification_needed=True,
                suggested_questions=["Can you provide more specific details about what you want to build?"]
            )

    def _build_question_generation_prompt(
        self,
        prompt: str,
        missing_elements: List[str],
        thread_id: Optional[str] = None
    ) -> str:
        """Build prompt for generating clarification questions."""
        elements_str = "\n".join(f"- {elem}" for elem in missing_elements)

        return f"""Generate specific, actionable clarification questions for this infrastructure-as-code generation request.

Original Request: "{prompt}"

Missing Elements Identified:
{elements_str}

Generate 2-3 targeted questions that will help gather the specific information needed for generating working Terraform/infrastructure code. Each question should be:

CRITICAL REQUIREMENTS for code generation:
- Cloud provider and region details
- Resource specifications (instance types, storage sizes, etc.)
- Network configuration (VPC, subnets, security groups)
- Naming conventions and resource identifiers
- Specific versions or configurations needed
- Integration requirements with other services

Each question should be:
- Focused on technical details needed for code generation
- Specific enough to enable immediate code creation
- Actionable (user can provide concrete answers)
- Essential for producing deployable infrastructure

Respond with a JSON array of question strings:
["What specific instance type do you need for the EC2 instances?", "What CIDR block should be used for the VPC?", "Do you need any specific security group rules?"]"""

    def _parse_question_response(self, response: str) -> List[str]:
        """Parse the question generation response."""
        try:
            # Clean the response
            response = response.strip()

            # Remove markdown code blocks if present
            if response.startswith('```json'):
                response = response[7:]
            if response.startswith('```'):
                response = response[3:]
            if response.endswith('```'):
                response = response[:-3]
            response = response.strip()

            # Try to parse as JSON array
            questions = json.loads(response)
            if isinstance(questions, list):
                return [q for q in questions if isinstance(q, str)]
            else:
                # Fallback: extract questions from text
                return self._extract_questions_from_text(response)
        except json.JSONDecodeError:
            # Try to extract JSON array from text
            import re

            # Look for JSON array pattern in the text
            array_match = re.search(r'\[.*\]', response, re.DOTALL)
            if array_match:
                try:
                    questions = json.loads(array_match.group())
                    if isinstance(questions, list):
                        return [q for q in questions if isinstance(q, str)]
                except json.JSONDecodeError:
                    pass

            # Final fallback: extract questions from text
            return self._extract_questions_from_text(response)

    def _extract_questions_from_text(self, text: str) -> List[str]:
        """Extract questions from plain text response."""
        import re
        # Find sentences ending with question marks
        questions = re.findall(r'[^.!?]*\?', text)
        return [q.strip() for q in questions if len(q.strip()) > 10][:3]

    async def _enrich_prompt_with_clarifications(
        self,
        clarification: ClarificationRequest,
        responses: Dict[str, str]
    ) -> str:
        """Enrich the original prompt with clarification responses."""
        # This is a placeholder - in a real implementation, you'd reconstruct
        # the full prompt from the original + clarifications
        # For now, we'll use the context summary + responses
        enriched_parts = [clarification.context_summary]

        for i, question in enumerate(clarification.questions):
            if str(i) in responses:
                enriched_parts.append(f"Clarification: {question}")
                enriched_parts.append(f"Answer: {responses[str(i)]}")

        return "\n".join(enriched_parts)

    def _determine_generation_scenario(self, prompt: str, context: Optional[Any]) -> Any:
        """Determine the appropriate generation scenario."""
        from app.services.code_generation.generation.prompt_engineer import GenerationScenario

        prompt_lower = prompt.lower()

        # Check for modification keywords
        if any(word in prompt_lower for word in ["modify", "update", "change", "edit", "fix"]):
            return GenerationScenario.MODIFY_RESOURCE

        # Check for module keywords
        if "module" in prompt_lower:
            return GenerationScenario.NEW_MODULE

        # Check for variable keywords
        if "variable" in prompt_lower:
            return GenerationScenario.NEW_VARIABLES

        # Check for output keywords
        if "output" in prompt_lower:
            return GenerationScenario.NEW_OUTPUTS

        # Default to new resource
        return GenerationScenario.NEW_RESOURCE