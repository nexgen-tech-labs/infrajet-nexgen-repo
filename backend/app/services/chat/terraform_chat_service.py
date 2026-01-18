"""
Terraform Chat Service for conversational Terraform code generation.

This service provides a simple, chat-like interface for generating Terraform code
with real-time updates and optional clarification questions.
"""

import asyncio
import json
import uuid
from datetime import datetime
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, text

from app.services.code_generation.realtime_orchestrator import RealtimeCodeGenerationOrchestrator
from app.services.websocket_manager import websocket_manager
from app.services.code_generation.generation.prompt_engineer import GenerationScenario
from app.services.code_generation.llm_providers.provider_factory import ProviderFactory
from app.services.code_generation.config.settings import get_code_generation_settings
from app.services.code_generation.llm_providers.base import LLMConfig, LLMRequest
from app.models.chat import ProjectChat, ConversationThread, MessageType
from logconfig.logger import get_logger

logger = get_logger()


@dataclass
class TerraformChatRequest:
    """Request for Terraform chat generation."""
    user_id: str
    project_id: str
    message: str
    thread_id: Optional[str] = None
    cloud_provider: str = "AWS"


@dataclass
class TerraformChatResponse:
    """Response from Terraform chat service."""
    thread_id: str
    status: str  # "clarification_needed", "generating", "completed", "error"
    clarification_questions: List[str] = field(default_factory=list)
    generation_job_id: Optional[str] = None
    message: str = ""


class TerraformChatService:
    """
    Simple chat service for conversational Terraform generation.

    Features:
    - Conversational interface for Terraform code generation
    - Optional clarification questions for missing parameters
    - Real-time WebSocket updates
    - Integration with existing code generation pipeline
    """

    def __init__(self, db_session: AsyncSession):
        """Initialize the Terraform chat service."""
        self.db = db_session
        self.code_orchestrator = RealtimeCodeGenerationOrchestrator(db_session)
        self.provider_factory = ProviderFactory()
        self.settings = get_code_generation_settings()

        logger.info("TerraformChatService initialized")

    async def process_message(self, request: TerraformChatRequest) -> TerraformChatResponse:
        """
        Process a user message for Terraform generation.

        Args:
            request: Terraform chat request

        Returns:
            TerraformChatResponse with status and next steps
        """
        try:
            # Get or create internal user ID from Supabase user ID
            internal_user_id = await self._get_internal_user_id(request.user_id)

            # Create or get thread
            thread = await self._get_or_create_thread(request.project_id, request.user_id, request.thread_id, request.cloud_provider)

            # Save user message
            await self._save_message(
                project_id=request.project_id,
                user_id=request.user_id,
                thread_id=thread.id,
                message_content=request.message,
                message_type=MessageType.USER
            )

            # Send processing started notification
            await websocket_manager.send_to_user(
                request.user_id,
                {
                    "type": "terraform_chat_processing",
                    "thread_id": thread.id,
                    "message": "Analyzing your Terraform request...",
                    "timestamp": datetime.utcnow().isoformat()
                }
            )

            # Check if clarification is needed
            clarification_needed, questions = await self._analyze_request_for_clarification(
                request.message
            )

            if clarification_needed:
                # Save clarification request message
                clarification_content = f"I need some additional information: {', '.join(questions)}"
                await self._save_message(
                    project_id=request.project_id,
                    user_id=request.user_id,
                    thread_id=thread.id,
                    message_content=clarification_content,
                    message_type=MessageType.CLARIFICATION_REQUEST
                )

                # Send clarification request
                await websocket_manager.send_to_user(
                    request.user_id,
                    {
                        "type": "terraform_clarification_needed",
                        "thread_id": thread.id,
                        "questions": questions,
                        "message": "I need some additional information to generate the best Terraform code for you.",
                        "timestamp": datetime.utcnow().isoformat()
                    }
                )

                return TerraformChatResponse(
                    thread_id=thread.id,
                    status="clarification_needed",
                    clarification_questions=questions,
                    message="Clarification needed before generating Terraform code."
                )

            # No clarification needed, proceed with generation
            await websocket_manager.send_to_user(
                request.user_id,
                {
                    "type": "terraform_generation_starting",
                    "thread_id": thread.id,
                    "message": "Starting Terraform code generation...",
                    "timestamp": datetime.utcnow().isoformat()
                }
            )

            # Start async generation with progress monitoring
            job_id = await self._start_generation_with_progress_tracking(
                query=request.message,
                user_id=internal_user_id,
                project_id=request.project_id,
                thread_id=thread.id,
                supabase_user_id=request.user_id,
                cloud_provider=request.cloud_provider
            )

            return TerraformChatResponse(
                thread_id=thread.id,
                status="generating",
                generation_job_id=job_id,
                message="Terraform generation started successfully."
            )

        except Exception as e:
            logger.error(f"Error processing Terraform chat message: {e}")

            await websocket_manager.send_to_user(
                request.user_id,
                {
                    "type": "terraform_chat_error",
                    "thread_id": request.thread_id,
                    "error": str(e),
                    "message": "An error occurred while processing your request.",
                    "timestamp": datetime.utcnow().isoformat()
                }
            )

            return TerraformChatResponse(
                thread_id=request.thread_id or str(uuid.uuid4()),
                status="error",
                message=f"Error: {str(e)}"
            )

    async def process_clarification_response(
        self,
        project_id: str,
        user_id: str,
        thread_id: str,
        responses: Dict[str, str]
    ) -> TerraformChatResponse:
        """
        Process user responses to clarification questions.

        Args:
            project_id: Project ID
            user_id: User ID
            thread_id: Conversation thread ID
            responses: Dictionary mapping question indices to answers

        Returns:
            TerraformChatResponse with generation status
        """
        try:
            # Get internal user ID
            internal_user_id = await self._get_internal_user_id(user_id)

            # Save clarification responses as user message
            response_content = "Clarification responses: " + ", ".join([f"{k}: {v}" for k, v in responses.items()])
            await self._save_message(
                project_id=project_id,
                user_id=user_id,
                thread_id=thread_id,
                message_content=response_content,
                message_type=MessageType.USER
            )

            # Combine original message with clarification responses
            # Get the original user message from the thread
            original_messages = await self.get_message_history(project_id, user_id, thread_id, limit=10)
            original_message = ""
            for msg in reversed(original_messages):
                if msg["is_user_message"] and not msg["message_content"].startswith("Clarification"):
                    original_message = msg["message_content"]
                    break

            combined_prompt = f"Original request: {original_message}\n\nClarifications:\n"
            for i, answer in responses.items():
                combined_prompt += f"- {answer}\n"

            # Send generation starting notification
            await websocket_manager.send_to_user(
                user_id,
                {
                    "type": "terraform_generation_starting",
                    "thread_id": thread_id,
                    "message": "Starting Terraform code generation with your clarifications...",
                    "timestamp": datetime.utcnow().isoformat()
                }
            )

            # Start generation with combined prompt
            job_id = await self._start_generation_with_progress_tracking(
                query=combined_prompt,
                user_id=internal_user_id,
                project_id=project_id,
                thread_id=thread_id,
                supabase_user_id=user_id,
                cloud_provider="AWS"  # Default, could be stored in thread
            )

            return TerraformChatResponse(
                thread_id=thread_id,
                status="generating",
                generation_job_id=job_id,
                message="Terraform generation started with clarifications."
            )

        except Exception as e:
            logger.error(f"Error processing clarification response: {e}")

            await websocket_manager.send_to_user(
                user_id,
                {
                    "type": "terraform_chat_error",
                    "thread_id": thread_id,
                    "error": str(e),
                    "message": "An error occurred while processing your clarifications.",
                    "timestamp": datetime.utcnow().isoformat()
                }
            )

            return TerraformChatResponse(
                thread_id=thread_id,
                status="error",
                message=f"Error processing clarifications: {str(e)}"
            )

    async def _get_or_create_thread(self, project_id: str, user_id: str, thread_id: Optional[str], cloud_provider: str) -> ConversationThread:
        """Get existing thread or create new one."""
        # Check if we're already in a transaction
        if self.db.in_transaction():
            # We're already in a transaction, just operate without starting a new one
            if thread_id:
                # Try to find existing thread
                result = await self.db.execute(
                    select(ConversationThread).filter(
                        ConversationThread.id == thread_id,
                        ConversationThread.project_id == project_id,
                        ConversationThread.user_id == user_id
                    )
                )
                thread = result.scalar_one_or_none()
                if thread:
                    # Update last activity
                    thread.last_message_at = datetime.utcnow()
                    await self.db.flush()
                    return thread

            # Create new thread
            thread = ConversationThread(
                project_id=project_id,
                user_id=user_id,
                title=f"Terraform Chat - {datetime.utcnow().strftime('%Y-%m-%d %H:%M')}",
                cloud_provider=cloud_provider,
                status="active"
            )

            self.db.add(thread)
            await self.db.flush()
            await self.db.refresh(thread)
        else:
            # Start a new transaction
            async with self.db.begin():
                if thread_id:
                    # Try to find existing thread
                    result = await self.db.execute(
                        select(ConversationThread).filter(
                            ConversationThread.id == thread_id,
                            ConversationThread.project_id == project_id,
                            ConversationThread.user_id == user_id
                        )
                    )
                    thread = result.scalar_one_or_none()
                    if thread:
                        # Update last activity
                        thread.last_message_at = datetime.utcnow()
                        await self.db.flush()
                        return thread

                # Create new thread
                thread = ConversationThread(
                    project_id=project_id,
                    user_id=user_id,
                    title=f"Terraform Chat - {datetime.utcnow().strftime('%Y-%m-%d %H:%M')}",
                    cloud_provider=cloud_provider,
                    status="active"
                )

                self.db.add(thread)
                await self.db.flush()
                await self.db.refresh(thread)

        logger.info(f"Created new conversation thread {thread.id} for user {user_id}")
        return thread

    async def _save_message(self, project_id: str, user_id: str, thread_id: str, message_content: str, message_type: MessageType, generation_id: Optional[str] = None):
        """Save a message to the database."""
        # Check if we're already in a transaction
        if self.db.in_transaction():
            # We're already in a transaction, just save without starting a new one
            message = ProjectChat(
                project_id=project_id,
                user_id=user_id,
                thread_id=thread_id,
                message_content=message_content,
                message_type=message_type,
                generation_id=generation_id
            )

            self.db.add(message)
            await self.db.flush()  # Flush to get the ID

            # Update thread's last message timestamp using ORM
            result = await self.db.execute(
                select(ConversationThread).filter(ConversationThread.id == thread_id)
            )
            thread = result.scalar_one_or_none()
            if thread:
                thread.last_message_at = datetime.utcnow()
                await self.db.flush()  # Flush the update
        else:
            # Start a new transaction to avoid concurrency issues
            async with self.db.begin():
                message = ProjectChat(
                    project_id=project_id,
                    user_id=user_id,
                    thread_id=thread_id,
                    message_content=message_content,
                    message_type=message_type,
                    generation_id=generation_id
                )

                self.db.add(message)
                await self.db.flush()  # Flush to get the ID without committing

                # Update thread's last message timestamp using ORM
                result = await self.db.execute(
                    select(ConversationThread).filter(ConversationThread.id == thread_id)
                )
                thread = result.scalar_one_or_none()
                if thread:
                    thread.last_message_at = datetime.utcnow()
                    await self.db.flush()  # Flush the update

                # Commit the entire transaction
                await self.db.commit()

        logger.debug(f"Saved {message_type.value} message to thread {thread_id}")

    async def _start_generation_with_progress_tracking(
        self, query: str, user_id: int, project_id: str, thread_id: str, supabase_user_id: str, cloud_provider: str
    ) -> str:
        """Start generation with comprehensive progress tracking."""
        # Start the generation
        job_id = await self.code_orchestrator.generate_code_async_with_realtime_monitoring(
            query=query,
            user_id=user_id,
            project_id=project_id,
            scenario=GenerationScenario.NEW_RESOURCE,
            enable_realtime=True,
            supabase_user_id=supabase_user_id,
            cloud_provider=cloud_provider
        )

        # Start monitoring in background
        asyncio.create_task(self._monitor_generation_progress(job_id, thread_id, supabase_user_id, project_id))

        return job_id

    async def _monitor_generation_progress(self, job_id: str, thread_id: str, user_id: str, project_id: str):
        """Monitor generation progress and send updates."""
        try:
            # Poll for completion (simplified - in production use events)
            max_wait_time = 300  # 5 minutes
            poll_interval = 2    # 2 seconds
            elapsed_time = 0

            while elapsed_time < max_wait_time:
                try:
                    # Check generation status
                    status = await self.code_orchestrator.get_realtime_job_status(job_id)

                    if status:
                        if status.get("status") == "completed":
                            # Send completion summary
                            await self._send_generation_summary(thread_id, user_id, status, project_id)
                            break
                        elif status.get("status") == "failed":
                            # Send failure notification
                            await websocket_manager.send_to_user(user_id, {
                                "type": "terraform_generation_failed",
                                "thread_id": thread_id,
                                "job_id": job_id,
                                "error": status.get("error_message", "Generation failed"),
                                "timestamp": datetime.utcnow().isoformat()
                            })
                            break
                        else:
                            # Send progress update
                            progress_percentage = status.get("progress_percentage", 0)
                            current_step = status.get("current_step", "Processing...")

                            await websocket_manager.send_to_user(user_id, {
                                "type": "terraform_generation_progress",
                                "thread_id": thread_id,
                                "job_id": job_id,
                                "progress_percentage": progress_percentage,
                                "current_step": current_step,
                                "timestamp": datetime.utcnow().isoformat()
                            })

                    await asyncio.sleep(poll_interval)
                    elapsed_time += poll_interval

                except Exception as e:
                    logger.error(f"Error checking generation status: {e}")
                    await asyncio.sleep(poll_interval)
                    elapsed_time += poll_interval

            if elapsed_time >= max_wait_time:
                await websocket_manager.send_to_user(user_id, {
                    "type": "terraform_generation_timeout",
                    "thread_id": thread_id,
                    "job_id": job_id,
                    "message": "Generation timed out. Please try again.",
                    "timestamp": datetime.utcnow().isoformat()
                })

        except Exception as e:
            logger.error(f"Error monitoring generation progress: {e}")

    async def _send_generation_summary(self, thread_id: str, user_id: str, status: Dict[str, Any], project_id: str):
        """Send generation completion summary."""
        try:
            # Get generation details
            generated_files = status.get("generated_files", [])
            processing_time = status.get("processing_time_ms", 0)
            job_id = status.get("job_id")

            # Create summary message
            summary_parts = []
            if generated_files:
                summary_parts.append(f"Successfully generated {len(generated_files)} Terraform file{'s' if len(generated_files) != 1 else ''}")
                summary_parts.append(f"Files: {', '.join(generated_files.keys())}")
            else:
                summary_parts.append("Generation completed")

            if processing_time:
                summary_parts.append(f"Processing time: {processing_time}ms")

            # Include generation ID for file retrieval
            if job_id:
                summary_parts.append(f"Generation ID: {job_id}")

            summary_text = " | ".join(summary_parts)

            # Save files to Azure and create database records if generation was successful
            if generated_files and job_id:
                await self._save_generated_files_to_azure_and_db(
                    user_id=user_id,
                    project_id=project_id,
                    generation_id=job_id,
                    generated_files=generated_files
                )

            # Save summary message
            await self._save_message(
                project_id=project_id,
                user_id=user_id,
                thread_id=thread_id,
                message_content=summary_text,
                message_type=MessageType.SYSTEM,
                generation_id=job_id
            )

            # Send WebSocket notification
            await websocket_manager.send_to_user(user_id, {
                "type": "terraform_generation_completed",
                "thread_id": thread_id,
                "job_id": job_id,
                "generated_files": list(generated_files.keys()) if generated_files else [],
                "processing_time_ms": processing_time,
                "summary": summary_text,
                "timestamp": datetime.utcnow().isoformat()
            })

        except Exception as e:
            logger.error(f"Error sending generation summary: {e}")

    async def get_message_history(self, project_id: str, user_id: str, thread_id: Optional[str] = None, limit: int = 50) -> List[Dict[str, Any]]:
        """Get message history for a conversation thread."""
        try:
            query = select(ProjectChat).filter(
                ProjectChat.project_id == project_id,
                ProjectChat.user_id == user_id
            )

            if thread_id:
                query = query.filter(ProjectChat.thread_id == thread_id)

            query = query.order_by(ProjectChat.timestamp.desc()).limit(limit)

            result = await self.db.execute(query)
            messages = result.scalars().all()

            # Convert to dict format
            message_history = []
            for msg in reversed(messages):  # Reverse to get chronological order
                message_history.append({
                    "id": msg.id,
                    "thread_id": msg.thread_id,
                    "message_content": msg.message_content,
                    "message_type": msg.message_type.value,
                    "timestamp": msg.timestamp.isoformat(),
                    "is_user_message": msg.is_user_message,
                    "is_system_message": msg.is_system_message,
                    "is_ai_message": msg.is_ai_message,
                    "is_clarification_request": msg.is_clarification_request,
                    "generation_id": msg.generation_id
                })

            return message_history

        except Exception as e:
            logger.error(f"Error getting message history: {e}")
            return []

    async def _get_internal_user_id(self, supabase_user_id: str) -> int:
        """
        Get or create internal integer user ID from Supabase user ID.

        Args:
            supabase_user_id: Supabase user ID (UUID string)

        Returns:
            Internal integer user ID
        """
        from sqlalchemy import select
        from app.models.user import User

        # Check if we're already in a transaction
        if self.db.in_transaction():
            # We're already in a transaction, just query without starting a new one
            try:
                # Try to find existing user
                result = await self.db.execute(
                    select(User).filter(User.supabase_user_id == supabase_user_id)
                )
                user = result.scalar_one_or_none()

                if user:
                    return user.id

                # User doesn't exist, create a new one
                # This is a simplified version - in production you'd want more user details
                new_user = User(
                    email=f"user-{supabase_user_id[:8]}@temp.local",  # Temporary email
                    supabase_user_id=supabase_user_id,
                    is_active=True
                )

                self.db.add(new_user)
                await self.db.flush()
                await self.db.refresh(new_user)

                logger.info(f"Created new internal user {new_user.id} for Supabase user {supabase_user_id}")
                return new_user.id

            except Exception as e:
                logger.error(f"Failed to get internal user ID for {supabase_user_id}: {e}")
                # Fallback to a default user ID - this should be improved
                return 1
        else:
            # Start a new transaction
            async with self.db.begin():
                try:
                    # Try to find existing user
                    result = await self.db.execute(
                        select(User).filter(User.supabase_user_id == supabase_user_id)
                    )
                    user = result.scalar_one_or_none()

                    if user:
                        return user.id

                    # User doesn't exist, create a new one
                    # This is a simplified version - in production you'd want more user details
                    new_user = User(
                        email=f"user-{supabase_user_id[:8]}@temp.local",  # Temporary email
                        supabase_user_id=supabase_user_id,
                        is_active=True
                    )

                    self.db.add(new_user)
                    await self.db.flush()
                    await self.db.refresh(new_user)

                    logger.info(f"Created new internal user {new_user.id} for Supabase user {supabase_user_id}")
                    return new_user.id

                except Exception as e:
                    logger.error(f"Failed to get internal user ID for {supabase_user_id}: {e}")
                    # Fallback to a default user ID - this should be improved
                    return 1

    async def _analyze_request_for_clarification(self, message: str) -> tuple[bool, List[str]]:
        """
        Analyze if the request needs clarification using Claude LLM.

        Args:
            message: User's message

        Returns:
            Tuple of (needs_clarification, list_of_questions)
        """
        try:
            # Create LLM provider config
            config = LLMConfig(
                api_key=self.settings.LLM_API_KEY,
                model="claude-3-haiku-20240307",  # Fast model for analysis
                temperature=0.1,  # Low temperature for consistent analysis
                max_tokens=1000,
                timeout=30
            )
            provider = self.provider_factory.create_provider("claude", config)

            # Build analysis prompt
            analysis_prompt = self._build_clarification_analysis_prompt(message)

            # Create LLM request
            request = LLMRequest(
                prompt=analysis_prompt,
                config=config,
                system_message="You are an expert at analyzing infrastructure-as-code requests and identifying missing technical details needed for Terraform generation."
            )

            # Get analysis from Claude
            response = await provider.generate(request)
            analysis_result = self._parse_clarification_response(response.content)

            logger.info(f"Claude clarification analysis: needs_clarification={analysis_result['needs_clarification']}, questions={len(analysis_result['questions'])}")

            return analysis_result['needs_clarification'], analysis_result['questions']

        except Exception as e:
            logger.error(f"Error in LLM-based clarification analysis: {e}")
            # Fallback to simple analysis if LLM fails
            return await self._fallback_clarification_analysis(message)

    def _build_clarification_analysis_prompt(self, message: str) -> str:
        """Build the prompt for Claude to analyze clarification needs."""
        return f"""Analyze this infrastructure-as-code generation request for completeness and identify any missing technical details.

Request: "{message}"

Please analyze if this request contains sufficient technical details for generating working Terraform/infrastructure code. Consider these essential elements:

CRITICAL ELEMENTS for Infrastructure Code Generation:
1. Cloud provider (AWS, Azure, GCP) and specific region
2. Resource specifications (instance types, storage sizes, networking requirements)
3. Infrastructure architecture (VPC, subnets, security groups, load balancers)
4. Service integrations and dependencies (databases, caches, message queues)
5. Naming conventions and resource identifiers
6. Compliance and security requirements (encryption, access controls)
7. Deployment and scaling configurations
8. Environment-specific settings (dev/staging/prod)

If information is missing, generate 2-3 specific, actionable clarification questions that will help gather the essential technical details needed for immediate Terraform code generation.

Respond with a JSON object in this exact format:
{{
    "needs_clarification": boolean,
    "questions": ["question1", "question2"] or []
}}

Guidelines for questions:
- Focus on technical details needed for code generation
- Be specific and actionable (user should provide concrete answers)
- Essential for producing deployable infrastructure
- Prioritize the most critical missing information
- Limit to maximum 3 questions

Only ask for clarification if critical information is missing that would prevent generating working Terraform code."""

    def _parse_clarification_response(self, response: str) -> Dict[str, Any]:
        """Parse Claude's clarification analysis response."""
        try:
            # Clean the response
            response = response.strip()
            if response.startswith('```json'):
                response = response[7:]
            if response.startswith('```'):
                response = response[3:]
            if response.endswith('```'):
                response = response[:-3]
            response = response.strip()

            # Parse JSON
            data = json.loads(response)

            # Validate structure
            needs_clarification = data.get("needs_clarification", False)
            questions = data.get("questions", [])

            # Ensure questions is a list and limit to 3
            if not isinstance(questions, list):
                questions = []
            questions = questions[:3]

            return {
                "needs_clarification": needs_clarification,
                "questions": questions
            }

        except (json.JSONDecodeError, KeyError, TypeError) as e:
            logger.warning(f"Failed to parse Claude clarification response: {e}, response: {response}")
            # Return default indicating clarification needed
            return {
                "needs_clarification": True,
                "questions": ["Can you provide more specific details about what infrastructure you want to create?"]
            }

    async def _fallback_clarification_analysis(self, message: str) -> tuple[bool, List[str]]:
        """
        Fallback clarification analysis using simple pattern matching.
        Used when LLM analysis fails.
        """
        questions = []
        message_lower = message.lower()

        # Check for cloud provider
        if not any(provider in message_lower for provider in ["aws", "azure", "gcp", "google cloud"]):
            questions.append("Which cloud provider would you like to use? (AWS, Azure, or GCP)")

        # Check for resource type
        if not any(resource in message_lower for resource in [
            "ec2", "instance", "s3", "bucket", "lambda", "function",
            "rds", "database", "vpc", "network", "security group"
        ]):
            questions.append("What type of infrastructure resource would you like to create?")

        # Check for region (basic check)
        if "region" not in message_lower and not any(region in message_lower for region in [
            "us-east-1", "us-west-2", "eu-west-1", "ap-south-1"
        ]):
            questions.append("Which region should the resources be deployed in?")

        # Only ask clarification if we have 2 or more questions
        needs_clarification = len(questions) >= 2

        return needs_clarification, questions[:3]  # Limit to 3 questions max

    async def _save_generated_files_to_azure_and_db(
        self, user_id: str, project_id: str, generation_id: str, generated_files: Dict[str, str]
    ):
        """Save generated files to Azure File Share and create database records."""
        try:
            # Create CodeGeneration record in database FIRST
            try:
                from app.models.project import CodeGeneration, GenerationStatus
                from app.services.code_generation.generation.prompt_engineer import GenerationScenario

                # Use Supabase user_id (string) for CodeGeneration record
                # CodeGeneration.user_id expects VARCHAR (Supabase user ID), not integer
                generation_record = CodeGeneration(
                    id=generation_id,
                    project_id=project_id,
                    user_id=user_id,  # Use Supabase user_id (string) directly
                    query=f"Terraform generation via chat - {len(generated_files)} files",
                    scenario=GenerationScenario.NEW_RESOURCE.value,
                    status=GenerationStatus.COMPLETED,
                    generation_hash=generation_id[:16],
                    error_message=None
                )

                self.db.add(generation_record)
                await self.db.flush()
                logger.info(f"✅ Created CodeGeneration record {generation_id} for Terraform chat")

            except Exception as gen_error:
                logger.error(f"❌ Failed to create CodeGeneration record: {gen_error}")
                # Continue with file saving even if generation record fails

            # Save files to Azure File Share
            files_saved = []
            try:
                from app.services.azure_file_service import AzureFileService
                azure_service = AzureFileService()

                if generated_files:
                    # Save all files in one call using the correct method
                    save_result = await azure_service.save_generated_files(
                        user_id=user_id,
                        project_id=project_id,
                        generation_id=generation_id,
                        files=generated_files  # This is already a Dict[str, str]
                    )

                    if save_result.success:
                        files_saved = save_result.saved_files
                        logger.info(f"Saved {len(files_saved)} generated files to Azure File Share: {files_saved}")
                    else:
                        logger.error(f"Failed to save files to Azure: {save_result.error}")

            except Exception as azure_error:
                logger.warning(f"Azure File Service not available: {azure_error}")

            # Create ProjectFile records in database for file share visibility
            if files_saved:
                try:
                    from app.models.project import ProjectFile

                    for filename in files_saved:
                        # Get file path relative to generation
                        file_path = f"{generation_id}/{filename}"

                        # Get file content to calculate hash and size
                        file_content = generated_files.get(filename, "")
                        if file_content:
                            # Create ProjectFile record
                            project_file = ProjectFile(
                                project_id=project_id,
                                file_path=file_path,
                                azure_path=f"projects/{user_id}/{project_id}/{generation_id}/{filename}",
                                file_type=filename.split('.')[-1] if '.' in filename else 'txt',
                                size_bytes=len(file_content.encode('utf-8')),
                                content_hash=""  # Will be computed by the model
                            )
                            project_file.update_content_hash(file_content)

                            self.db.add(project_file)
                            await self.db.flush()

                    await self.db.commit()
                    logger.info(f"Created {len(files_saved)} ProjectFile records for generation {generation_id}")

                except Exception as db_error:
                    logger.error(f"Failed to create ProjectFile records: {db_error}")
                    # Don't fail the entire operation if DB save fails

        except Exception as e:
            logger.error(f"Error saving generated files to Azure and DB: {e}")