"""
Chat Service for Project Chat Management.

This service provides functionality for managing chat conversations
associated with projects, including saving messages and retrieving
chat history with proper user access control.
"""

import uuid
from datetime import datetime
from typing import List, Optional, Dict, Any
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, desc, func
from sqlalchemy.orm import selectinload

from app.models.chat import ProjectChat, MessageType
from app.models.project import Project
from app.exceptions.base_exceptions import (
    BaseApplicationError,
    ValidationError,
    ResourceNotFoundError,
    AuthorizationError
)
from app.services.chat.conversation_context_manager import ConversationContextManager
from app.services.chat.autonomous_chat_service import AutonomousChatService
from app.services.job_queue import job_queue_service, JobPriority
from logconfig.logger import get_logger

logger = get_logger()


class ChatServiceError(BaseApplicationError):
    """Base exception for chat service operations."""
    
    def __init__(self, message: str, **kwargs):
        # Set default values only if not already provided
        kwargs.setdefault('error_code', 'CHAT_SERVICE_ERROR')
        kwargs.setdefault('user_message', 'An error occurred while processing your chat request.')
        kwargs.setdefault('troubleshooting_guide', 'Please try again. If the problem persists, contact support.')
        kwargs.setdefault('severity', 'medium')
        
        super().__init__(message=message, **kwargs)


class ChatNotFoundError(ChatServiceError):
    """Exception raised when chat history is not found."""
    
    def __init__(self, project_id: str, **kwargs):
        kwargs.setdefault('error_code', 'CHAT_NOT_FOUND')
        kwargs.setdefault('user_message', 'No chat history found for this project.')
        kwargs.setdefault('troubleshooting_guide', 'Start a conversation to create chat history for this project.')
        kwargs.setdefault('severity', 'low')
        
        super().__init__(
            message=f"Chat history not found for project {project_id}",
            **kwargs
        )
        self.project_id = project_id


class ChatAccessDeniedError(ChatServiceError):
    """Exception raised when user lacks access to project chat."""
    
    def __init__(self, user_id: str, project_id: str, **kwargs):
        kwargs.setdefault('error_code', 'CHAT_ACCESS_DENIED')
        kwargs.setdefault('user_message', "You don't have permission to access this project's chat.")
        kwargs.setdefault('troubleshooting_guide', 'Ensure you have access to the project and try again.')
        kwargs.setdefault('severity', 'high')
        
        super().__init__(
            message=f"User {user_id} denied access to chat for project {project_id}",
            **kwargs
        )
        self.user_id = user_id
        self.project_id = project_id


class ChatValidationError(ChatServiceError):
    """Exception raised for invalid chat message data."""
    
    def __init__(self, message: str, field: Optional[str] = None, **kwargs):
        kwargs.setdefault('error_code', 'CHAT_VALIDATION_ERROR')
        kwargs.setdefault('user_message', 'Invalid message data provided.')
        kwargs.setdefault('troubleshooting_guide', 'Check that your message content is valid and try again.')
        kwargs.setdefault('severity', 'medium')
        
        super().__init__(message=message, **kwargs)
        self.field = field


class ChatService:
    """
    Service for managing project chat functionality.
    
    Provides methods for saving chat messages and retrieving chat history
    with proper project association and user access validation.
    """
    
    def __init__(self, db_session: AsyncSession):
        """
        Initialize the chat service.

        Args:
            db_session: Database session for operations
        """
        self.db = db_session
        self.context_manager = ConversationContextManager(db_session)
        self.autonomous_service = AutonomousChatService(db_session)
    
    async def save_message(
        self,
        project_id: str,
        user_id: str,
        message_content: str,
        message_type: MessageType = MessageType.USER
    ) -> ProjectChat:
        """
        Save a chat message with project association and validation.
        
        Args:
            project_id: ID of the project the message belongs to
            user_id: Supabase user ID of the message sender
            message_content: Content of the chat message
            message_type: Type of message (USER, SYSTEM, AI)
            
        Returns:
            ProjectChat: The saved chat message
            
        Raises:
            ChatValidationError: If message data is invalid
            ChatAccessDeniedError: If user lacks project access
            ChatServiceError: If save operation fails
        """
        try:
            # Validate input parameters
            if not project_id or not project_id.strip():
                raise ChatValidationError("Project ID is required", field="project_id")
            
            if not user_id or not user_id.strip():
                raise ChatValidationError("User ID is required", field="user_id")
            
            if not message_content or not message_content.strip():
                raise ChatValidationError("Message content is required", field="message_content")
            
            if len(message_content.strip()) > 10000:  # Reasonable message length limit
                raise ChatValidationError("Message content is too long (max 10,000 characters)", field="message_content")
            
            # Validate message type
            if not isinstance(message_type, MessageType):
                try:
                    message_type = MessageType(message_type)
                except ValueError:
                    raise ChatValidationError(f"Invalid message type: {message_type}", field="message_type")
            
            # Verify project exists and user has access
            await self._validate_project_access(project_id, user_id)
            
            # Create and save chat message
            chat_message = ProjectChat(
                project_id=project_id,
                user_id=user_id,
                message_content=message_content.strip(),
                message_type=message_type
            )
            
            self.db.add(chat_message)
            await self.db.flush()  # Flush to get the ID without committing
            
            logger.info(f"Saved chat message {chat_message.id} for project {project_id} by user {user_id}")
            
            return chat_message
            
        except (ChatValidationError, ChatAccessDeniedError):
            # Re-raise chat-specific exceptions
            raise
        except Exception as e:
            logger.error(f"Failed to save chat message for project {project_id}: {e}")
            raise ChatServiceError(
                f"Failed to save chat message: {e}",
                original_exception=e,
                details={"project_id": project_id, "user_id": user_id}
            )
    
    async def get_chat_history(
        self,
        project_id: str,
        user_id: str,
        limit: Optional[int] = None,
        offset: int = 0
    ) -> List[ProjectChat]:
        """
        Retrieve chat history for a project in chronological order.
        
        Args:
            project_id: ID of the project to get chat history for
            user_id: Supabase user ID requesting the chat history
            limit: Maximum number of messages to return (None for all)
            offset: Number of messages to skip (for pagination)
            
        Returns:
            List[ProjectChat]: List of chat messages in chronological order
            
        Raises:
            ChatValidationError: If parameters are invalid
            ChatAccessDeniedError: If user lacks project access
            ChatServiceError: If retrieval operation fails
        """
        try:
            # Validate input parameters
            if not project_id or not project_id.strip():
                raise ChatValidationError("Project ID is required", field="project_id")
            
            if not user_id or not user_id.strip():
                raise ChatValidationError("User ID is required", field="user_id")
            
            if limit is not None and limit <= 0:
                raise ChatValidationError("Limit must be positive", field="limit")
            
            if offset < 0:
                raise ChatValidationError("Offset must be non-negative", field="offset")
            
            # Verify project exists and user has access
            await self._validate_project_access(project_id, user_id)
            
            # Build query for chat messages
            query = select(ProjectChat).where(
                ProjectChat.project_id == project_id
            ).order_by(ProjectChat.timestamp.asc())  # Chronological order
            
            # Apply pagination
            if offset > 0:
                query = query.offset(offset)
            
            if limit is not None:
                query = query.limit(limit)
            
            # Execute query
            result = await self.db.execute(query)
            chat_messages = result.scalars().all()
            
            logger.info(f"Retrieved {len(chat_messages)} chat messages for project {project_id}")
            
            return list(chat_messages)
            
        except (ChatValidationError, ChatAccessDeniedError):
            # Re-raise chat-specific exceptions
            raise
        except Exception as e:
            logger.error(f"Failed to get chat history for project {project_id}: {e}")
            raise ChatServiceError(
                f"Failed to retrieve chat history: {e}",
                original_exception=e,
                details={"project_id": project_id, "user_id": user_id}
            )
    
    async def initialize_project_chat(self, project_id: str) -> None:
        """
        Initialize empty chat for a new project.
        
        This method ensures that the project exists and is ready for chat functionality.
        No actual chat messages are created, but the project is validated.
        
        Args:
            project_id: ID of the project to initialize chat for
            
        Raises:
            ChatValidationError: If project_id is invalid
            ResourceNotFoundError: If project doesn't exist
            ChatServiceError: If initialization fails
        """
        try:
            # Validate input
            if not project_id or not project_id.strip():
                raise ChatValidationError("Project ID is required", field="project_id")
            
            # Verify project exists
            query = select(Project).where(Project.id == project_id)
            result = await self.db.execute(query)
            project = result.scalar_one_or_none()
            
            if not project:
                raise ResourceNotFoundError(
                    f"Project {project_id} not found",
                    resource_type="project",
                    resource_id=project_id
                )
            
            logger.info(f"Initialized chat for project {project_id}")
            
        except (ChatValidationError, ResourceNotFoundError):
            # Re-raise specific exceptions
            raise
        except Exception as e:
            logger.error(f"Failed to initialize chat for project {project_id}: {e}")
            raise ChatServiceError(
                f"Failed to initialize project chat: {e}",
                original_exception=e,
                details={"project_id": project_id}
            )
    
    async def _validate_project_access(self, project_id: str, user_id: str) -> Project:
        """
        Validate that a project exists and user has access to it.
        
        Args:
            project_id: ID of the project to validate
            user_id: Supabase user ID to validate access for
            
        Returns:
            Project: The project if access is valid
            
        Raises:
            ResourceNotFoundError: If project doesn't exist
            ChatAccessDeniedError: If user lacks access
        """
        # Get project with user validation
        query = select(Project).where(
            and_(
                Project.id == project_id,
                Project.user_id == user_id
            )
        )
        
        result = await self.db.execute(query)
        project = result.scalar_one_or_none()
        
        if not project:
            # Check if project exists at all
            exists_query = select(Project).where(Project.id == project_id)
            exists_result = await self.db.execute(exists_query)
            exists = exists_result.scalar_one_or_none()
            
            if not exists:
                raise ResourceNotFoundError(
                    f"Project {project_id} not found",
                    resource_type="project",
                    resource_id=project_id
                )
            else:
                raise ChatAccessDeniedError(user_id, project_id)
        
        return project

    async def create_conversation_thread(
        self,
        project_id: str,
        user_id: str,
        thread_title: Optional[str] = None,
        cloud_provider: str = "AWS"
    ) -> str:
        """
        Create a new conversation thread for autonomous chat.

        Args:
            project_id: ID of the project
            user_id: User ID creating the thread
            thread_title: Optional title for the thread

        Returns:
            str: Thread ID

        Raises:
            ChatValidationError: If parameters are invalid
            ChatAccessDeniedError: If user lacks project access
            ChatServiceError: If creation fails
        """
        try:
            # Validate project access
            await self._validate_project_access(project_id, user_id)

            thread_id = str(uuid.uuid4())

            # Initialize context for the thread
            from app.services.chat.conversation_context_manager import ConversationContext
            context = ConversationContext(
                thread_id=thread_id,
                context_metadata={"cloud_provider": cloud_provider}
            )
            await self.context_manager.save_context(context)

            # Save system message to indicate thread creation
            title = thread_title or f"Conversation started at {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')}"
            await self.save_message(
                project_id=project_id,
                user_id=user_id,
                message_content=f"Started new conversation thread: {title}",
                message_type=MessageType.SYSTEM
            )

            logger.info(f"Created conversation thread {thread_id} for project {project_id}")
            return thread_id

        except (ChatValidationError, ChatAccessDeniedError):
            raise
        except Exception as e:
            logger.error(f"Failed to create conversation thread for project {project_id}: {e}")
            raise ChatServiceError(
                f"Failed to create conversation thread: {e}",
                original_exception=e,
                details={"project_id": project_id, "user_id": user_id}
            )

    async def process_autonomous_message(
        self,
        project_id: str,
        user_id: str,
        message_content: str,
        thread_id: Optional[str] = None,
        cloud_provider: str = "AWS",
        clarification_round: int = 0
    ) -> Dict[str, Any]:
        """
        Process a user message through the autonomous chat flow using background jobs.

        Args:
            project_id: ID of the project
            user_id: User ID sending the message
            message_content: The user's message
            thread_id: Optional existing thread ID
            cloud_provider: Cloud provider for the infrastructure
            clarification_round: Current clarification round

        Returns:
            Dict[str, Any]: Processing result with job information

        Raises:
            ChatValidationError: If parameters are invalid
            ChatAccessDeniedError: If user lacks project access
            ChatServiceError: If processing fails
        """
        try:
            # Validate project access
            await self._validate_project_access(project_id, user_id)

            # Create thread if not provided
            if not thread_id:
                thread_id = await self.create_conversation_thread(project_id, user_id, cloud_provider=cloud_provider)

            # Save user message
            user_message = await self.save_message(
                project_id=project_id,
                user_id=user_id,
                message_content=message_content,
                message_type=MessageType.USER
            )

            # Submit job to background queue
            job_data = {
                "project_id": project_id,
                "user_id": user_id,
                "message_content": message_content,
                "thread_id": thread_id,
                "message_id": user_message.id,
                "cloud_provider": cloud_provider,
                "clarification_round": clarification_round
            }

            job_id = await job_queue_service.submit_job(
                job_type="autonomous_chat_processing",
                data=job_data,
                priority=JobPriority.HIGH
            )

            result = {
                "thread_id": thread_id,
                "message_id": user_message.id,
                "job_id": job_id,
                "status": "processing",
                "message": "Your request is being processed. You'll receive real-time updates."
            }

            logger.info(f"Submitted autonomous message processing job: {job_id} for thread {thread_id}")
            return result

        except (ChatValidationError, ChatAccessDeniedError):
            raise
        except Exception as e:
            logger.error(f"Failed to submit autonomous message job for project {project_id}: {e}")
            raise ChatServiceError(
                f"Failed to process autonomous message: {e}",
                original_exception=e,
                details={"project_id": project_id, "user_id": user_id, "thread_id": thread_id}
            )

    async def _process_autonomous_message_sync(
        self,
        project_id: str,
        user_id: str,
        message_content: str,
        thread_id: str,
        cloud_provider: str = "AWS",
        clarification_round: int = 0
    ) -> Dict[str, Any]:
        """
        Synchronous processing of autonomous message (called from job queue).

        Args:
            project_id: ID of the project
            user_id: User ID sending the message
            message_content: The user's message
            thread_id: Conversation thread ID
            cloud_provider: Cloud provider for the infrastructure
            clarification_round: Current clarification round

        Returns:
            Dict[str, Any]: Processing result
        """
        try:
            # Get conversation history for context
            chat_history = await self.get_chat_history(project_id, user_id, limit=10)
            context_history = [
                {"content": msg.message_content, "type": msg.message_type.value, "timestamp": msg.timestamp.isoformat()}
                for msg in chat_history[-5:]  # Last 5 messages for context
            ]

            # Analyze prompt completeness
            analysis = await self.autonomous_service.analyze_prompt_completeness(
                prompt=message_content,
                thread_id=thread_id,
                context_history=context_history
            )

            result = {
                "thread_id": thread_id,
                "analysis": {
                    "is_complete": analysis.is_complete,
                    "confidence_score": analysis.confidence_score,
                    "missing_elements": analysis.missing_elements,
                    "intent": analysis.intent_classification
                }
            }

            # Check if we should ask for clarification or force generation
            max_clarification_rounds = 2
            should_ask_clarification = (
                analysis.clarification_needed and
                clarification_round < max_clarification_rounds
            )

            if should_ask_clarification:
                # Generate clarification questions
                questions = await self.autonomous_service.generate_clarification_questions(
                    prompt=message_content,
                    analysis=analysis,
                    thread_id=thread_id
                )

                # Create clarification request
                context_summary = await self.context_manager.summarize_context(thread_id)
                clarification = await self.autonomous_service.create_clarification_request(
                    thread_id=thread_id,
                    questions=questions,
                    context_summary=context_summary
                )

                # Save clarification message
                clarification_content = {
                    "clarification_id": clarification.request_id,
                    "questions": clarification.questions,
                    "context_summary": clarification.context_summary,
                    "clarification_round": clarification_round + 1
                }
                import json
                await self.save_message(
                    project_id=project_id,
                    user_id=user_id,
                    message_content=json.dumps(clarification_content),
                    message_type=MessageType.CLARIFICATION_REQUEST
                )

                result["clarification_request"] = {
                    "id": clarification.request_id,
                    "questions": clarification.questions,
                    "round": clarification_round + 1,
                    "max_rounds": max_clarification_rounds
                }
                result["next_action"] = "await_clarification"

                # Send WebSocket notification for clarification needed
                try:
                    from app.services.websocket_manager import websocket_manager
                    await websocket_manager.send_to_user(
                        user_id,
                        {
                            "type": "clarification_needed",
                            "project_id": project_id,
                            "thread_id": thread_id,
                            "clarification_id": clarification.request_id,
                            "questions": clarification.questions,
                            "round": clarification_round + 1,
                            "max_rounds": max_clarification_rounds,
                            "message": f"I need some clarification to generate the best code for you. Round {clarification_round + 1} of {max_clarification_rounds}",
                            "timestamp": datetime.utcnow().isoformat()
                        }
                    )
                except Exception as ws_error:
                    logger.warning(f"Failed to send clarification WebSocket notification: {ws_error}")

            else:
                # Either complete or max clarification rounds reached - trigger code generation
                generation_message = message_content
                if analysis.clarification_needed and clarification_round >= max_clarification_rounds:
                    logger.info(f"Max clarification rounds ({max_clarification_rounds}) reached, proceeding with generation despite incomplete analysis")
                    generation_message = f"[After {max_clarification_rounds} clarification rounds] {message_content}"

                # Trigger code generation
                generation_result = await self.autonomous_service.trigger_code_generation(
                    thread_id=thread_id,
                    enriched_prompt=generation_message,
                    user_id=user_id,
                    project_id=project_id
                )

                result["generation_triggered"] = True
                result["job_id"] = generation_result["job_id"]
                result["next_action"] = "generation_started"

                # Send WebSocket notification for generation started
                try:
                    from app.services.websocket_manager import websocket_manager
                    await websocket_manager.send_to_user(
                        user_id,
                        {
                            "type": "generation_started",
                            "project_id": project_id,
                            "thread_id": thread_id,
                            "job_id": generation_result["job_id"],
                            "message": "Starting code generation based on your requirements...",
                            "timestamp": datetime.utcnow().isoformat()
                        }
                    )
                except Exception as ws_error:
                    logger.warning(f"Failed to send generation start WebSocket notification: {ws_error}")

            logger.info(f"Synchronously processed autonomous message for thread {thread_id}: {result['next_action']}")
            return result

        except Exception as e:
            logger.error(f"Failed to synchronously process autonomous message for project {project_id}: {e}")
            raise

    async def respond_to_clarification(
        self,
        project_id: str,
        user_id: str,
        clarification_id: str,
        responses: Dict[str, str],
        clarification_round: int = 1
    ) -> Dict[str, Any]:
        """
        Process user responses to clarification questions.

        Args:
            project_id: ID of the project
            user_id: User ID responding
            clarification_id: ID of the clarification request
            responses: Dictionary mapping question indices to answers

        Returns:
            Dict[str, Any]: Processing result

        Raises:
            ChatValidationError: If parameters are invalid
            ChatAccessDeniedError: If user lacks project access
            ChatServiceError: If processing fails
        """
        try:
            # Validate project access
            await self._validate_project_access(project_id, user_id)

            # Find the clarification message to get thread_id
            query = select(ProjectChat).where(
                and_(
                    ProjectChat.project_id == project_id,
                    ProjectChat.message_type == MessageType.CLARIFICATION_REQUEST
                )
            ).order_by(ProjectChat.timestamp.desc())

            result = await self.db.execute(query)
            clarification_msg = result.scalar_one_or_none()

            if not clarification_msg:
                raise ChatValidationError("Clarification request not found", field="clarification_id")

            import json
            clarification_data = json.loads(clarification_msg.message_content)
            if clarification_data.get("clarification_id") != clarification_id:
                raise ChatValidationError("Clarification ID mismatch", field="clarification_id")

            thread_id = clarification_data.get("thread_id")

            # Process the response
            processing_result = await self.autonomous_service.process_user_response(
                thread_id=thread_id,
                clarification_id=clarification_id,
                responses=responses
            )

            result = {
                "clarification_processed": True,
                "thread_id": thread_id,
                "is_now_complete": processing_result["is_now_complete"],
                "next_action": processing_result["next_action"],
                "clarification_round": clarification_round
            }

            if processing_result["is_now_complete"]:
                # Trigger code generation with enriched prompt
                generation_result = await self.autonomous_service.trigger_code_generation(
                    thread_id=thread_id,
                    enriched_prompt=processing_result["enriched_prompt"],
                    user_id=user_id,
                    project_id=project_id
                )

                result["generation_triggered"] = True
                result["job_id"] = generation_result["job_id"]
                result["next_action"] = "generation_started"

                # Send WebSocket notification for generation started
                try:
                    from app.services.websocket_manager import websocket_manager
                    await websocket_manager.send_to_user(
                        user_id,
                        {
                            "type": "generation_started",
                            "project_id": project_id,
                            "thread_id": thread_id,
                            "job_id": generation_result["job_id"],
                            "message": "Starting code generation with your clarifications...",
                            "timestamp": datetime.utcnow().isoformat()
                        }
                    )
                except Exception as ws_error:
                    logger.warning(f"Failed to send generation start WebSocket notification: {ws_error}")

            else:
                # Check if we should ask for more clarification or force generation
                max_clarification_rounds = 2
                if clarification_round < max_clarification_rounds:
                    # Need more clarification - generate new questions
                    enriched_prompt = processing_result["enriched_prompt"]

                    # Re-analyze the enriched prompt
                    analysis = await self.autonomous_service.analyze_prompt_completeness(
                        prompt=enriched_prompt,
                        thread_id=thread_id
                    )

                    if analysis.clarification_needed:
                        # Generate new clarification questions
                        questions = await self.autonomous_service.generate_clarification_questions(
                            prompt=enriched_prompt,
                            analysis=analysis,
                            thread_id=thread_id
                        )

                        # Create new clarification request
                        context_summary = await self.context_manager.summarize_context(thread_id)
                        clarification = await self.autonomous_service.create_clarification_request(
                            thread_id=thread_id,
                            questions=questions,
                            context_summary=context_summary
                        )

                        # Save new clarification message
                        clarification_content = {
                            "clarification_id": clarification.request_id,
                            "questions": clarification.questions,
                            "context_summary": clarification.context_summary,
                            "clarification_round": clarification_round + 1
                        }
                        import json
                        await self.save_message(
                            project_id=project_id,
                            user_id=user_id,
                            message_content=json.dumps(clarification_content),
                            message_type=MessageType.CLARIFICATION_REQUEST
                        )

                        result["additional_questions"] = clarification.questions
                        result["new_clarification_request"] = {
                            "id": clarification.request_id,
                            "questions": clarification.questions,
                            "round": clarification_round + 1,
                            "max_rounds": max_clarification_rounds
                        }
                        result["next_action"] = "await_clarification"

                        # Send WebSocket notification for additional clarification
                        try:
                            from app.services.websocket_manager import websocket_manager
                            await websocket_manager.send_to_user(
                                user_id,
                                {
                                    "type": "additional_clarification_needed",
                                    "project_id": project_id,
                                    "thread_id": thread_id,
                                    "clarification_id": clarification.request_id,
                                    "questions": clarification.questions,
                                    "round": clarification_round + 1,
                                    "max_rounds": max_clarification_rounds,
                                    "message": f"I still need some more details. Round {clarification_round + 1} of {max_clarification_rounds}",
                                    "timestamp": datetime.utcnow().isoformat()
                                }
                            )
                        except Exception as ws_error:
                            logger.warning(f"Failed to send additional clarification WebSocket notification: {ws_error}")
                    else:
                        # Actually complete now - trigger generation
                        generation_result = await self.autonomous_service.trigger_code_generation(
                            thread_id=thread_id,
                            enriched_prompt=enriched_prompt,
                            user_id=user_id,
                            project_id=project_id
                        )

                        result["generation_triggered"] = True
                        result["job_id"] = generation_result["job_id"]
                        result["next_action"] = "generation_started"
                else:
                    # Max rounds reached - force generation
                    enriched_prompt = processing_result["enriched_prompt"]
                    logger.info(f"Max clarification rounds ({max_clarification_rounds}) reached, forcing generation")

                    generation_result = await self.autonomous_service.trigger_code_generation(
                        thread_id=thread_id,
                        enriched_prompt=f"[After {max_clarification_rounds} clarification rounds] {enriched_prompt}",
                        user_id=user_id,
                        project_id=project_id
                    )

                    result["generation_triggered"] = True
                    result["job_id"] = generation_result["job_id"]
                    result["next_action"] = "generation_started"
                    result["forced_generation"] = True

            logger.info(f"Processed clarification response for thread {thread_id}: {result['next_action']}")
            return result

        except (ChatValidationError, ChatAccessDeniedError):
            raise
        except Exception as e:
            logger.error(f"Failed to process clarification response for project {project_id}: {e}")
            raise ChatServiceError(
                f"Failed to process clarification response: {e}",
                original_exception=e,
                details={"project_id": project_id, "clarification_id": clarification_id}
            )

    async def get_conversation_threads(
        self,
        project_id: str,
        user_id: str,
        limit: int = 10
    ) -> List[Dict[str, Any]]:
        """
        Get conversation threads for a project.

        Args:
            project_id: ID of the project
            user_id: User ID requesting threads
            limit: Maximum number of threads to return

        Returns:
            List[Dict[str, Any]]: List of conversation threads

        Raises:
            ChatValidationError: If parameters are invalid
            ChatAccessDeniedError: If user lacks project access
            ChatServiceError: If retrieval fails
        """
        try:
            # Validate project access
            await self._validate_project_access(project_id, user_id)

            # Import ConversationThread here to avoid circular imports
            from app.models.chat import ConversationThread

            # Query conversation threads with message count
            query = select(
                ConversationThread,
                # Count messages for each thread
                select(func.count(ProjectChat.id)).where(
                    and_(
                        ProjectChat.thread_id == ConversationThread.id,
                        ProjectChat.project_id == project_id
                    )
                ).label("message_count")
            ).where(
                and_(
                    ConversationThread.project_id == project_id,
                    ConversationThread.user_id == user_id
                )
            ).order_by(
                desc(ConversationThread.last_message_at),
                desc(ConversationThread.created_at)
            ).limit(limit)

            result = await self.db.execute(query)
            thread_rows = result.all()

            threads = []
            for thread, message_count in thread_rows:
                thread_info = {
                    "project_id": thread.project_id,
                    "thread_id": thread.id,
                    "title": thread.title,
                    "created_at": thread.created_at.isoformat(),
                    "last_message_at": thread.last_message_at.isoformat() if thread.last_message_at else None,
                    "message_count": message_count,
                    "status": thread.status,
                    "cloud_provider": thread.cloud_provider
                }
                threads.append(thread_info)

            logger.info(f"Retrieved {len(threads)} conversation threads for project {project_id}")
            return threads

        except (ChatValidationError, ChatAccessDeniedError):
            raise
        except Exception as e:
            logger.error(f"Failed to get conversation threads for project {project_id}: {e}")
            raise ChatServiceError(
                f"Failed to get conversation threads: {e}",
                original_exception=e,
                details={"project_id": project_id, "user_id": user_id}
            )