"""
Chat API endpoints for project chat management.

This module provides REST endpoints for managing chat conversations
associated with projects, including saving messages and retrieving
chat history with proper authentication and access control.
"""

import asyncio
import uuid
from datetime import datetime
from typing import List, Optional, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, Query, Path, Body, BackgroundTasks
from pydantic import BaseModel, Field, ConfigDict
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_async_db
from app.dependencies.auth import get_current_user_id
from app.services.chat_service import (
    ChatService,
    ChatServiceError,
    ChatNotFoundError,
    ChatAccessDeniedError,
    ChatValidationError
)
from app.services.chat.terraform_chat_service import TerraformChatService, TerraformChatRequest
from app.models.chat import MessageType, ConversationThread, ClarificationRequest
from logconfig.logger import get_logger

logger = get_logger()
router = APIRouter(prefix="/projects", tags=["project-chat"])
autonomous_router = APIRouter(prefix="/autonomous", tags=["autonomous-chat"])


# Request/Response Models
class SaveMessageRequest(BaseModel):
    """Request model for saving chat messages."""
    
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "message_content": "Hello, I need help with this project configuration.",
                "message_type": "user"
            }
        }
    )
    
    message_content: str = Field(
        ..., 
        min_length=1, 
        max_length=10000,
        description="Content of the chat message"
    )
    message_type: MessageType = Field(
        default=MessageType.USER,
        description="Type of message (user, system, ai)"
    )


class ChatMessageResponse(BaseModel):
    """Response model for individual chat messages."""

    model_config = ConfigDict(
        from_attributes=True,
        json_schema_extra={
            "example": {
                "id": "550e8400-e29b-41d4-a716-446655440000",
                "project_id": "550e8400-e29b-41d4-a716-446655440001",
                "user_id": "550e8400-e29b-41d4-a716-446655440002",
                "message_content": "Hello, I need help with this project configuration.",
                "message_type": "user",
                "timestamp": "2024-01-15T10:30:00Z",
                "generation_id": None
            }
        }
    )

    id: str = Field(..., description="Unique message identifier")
    project_id: str = Field(..., description="Project identifier")
    user_id: str = Field(..., description="Supabase user identifier")
    message_content: str = Field(..., description="Message content")
    message_type: MessageType = Field(..., description="Message type")
    timestamp: datetime = Field(..., description="Message timestamp")
    generation_id: Optional[str] = Field(None, description="Generation ID for system messages with file links")


class SaveMessageResponse(BaseModel):
    """Response model for saving chat messages."""
    
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "message": {
                    "id": "550e8400-e29b-41d4-a716-446655440000",
                    "project_id": "550e8400-e29b-41d4-a716-446655440001",
                    "user_id": "550e8400-e29b-41d4-a716-446655440002",
                    "message_content": "Hello, I need help with this project configuration.",
                    "message_type": "user",
                    "timestamp": "2024-01-15T10:30:00Z"
                },
                "success": True,
                "message_text": "Message saved successfully"
            }
        }
    )
    
    message: ChatMessageResponse = Field(..., description="Saved message details")
    success: bool = Field(default=True, description="Operation success status")
    message_text: str = Field(..., description="Success message")


class ChatHistoryResponse(BaseModel):
    """Response model for chat history retrieval."""
    
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "project_id": "550e8400-e29b-41d4-a716-446655440001",
                "messages": [],
                "total_count": 25,
                "returned_count": 10,
                "has_more": True,
                "message_text": "Retrieved chat history successfully"
            }
        }
    )
    
    project_id: str = Field(..., description="Project identifier")
    messages: List[ChatMessageResponse] = Field(..., description="Chat messages in chronological order")
    total_count: int = Field(..., description="Total number of messages (if available)")
    returned_count: int = Field(..., description="Number of messages returned")
    has_more: bool = Field(..., description="Whether there are more messages available")
    message_text: str = Field(..., description="Success message")


class ErrorResponse(BaseModel):
    """Standard error response model."""

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "error": "ChatAccessDenied",
                "message": "You don't have permission to access this project's chat.",
                "details": {"project_id": "550e8400-e29b-41d4-a716-446655440001"},
                "timestamp": "2024-01-15T10:30:00Z"
            }
        }
    )

    error: str = Field(..., description="Error type")
    message: str = Field(..., description="Human-readable error message")
    details: Optional[dict] = Field(None, description="Additional error details")
    timestamp: datetime = Field(default_factory=datetime.utcnow, description="Error timestamp")


class ConversationThreadResponse(BaseModel):
    """Response model for conversation threads."""

    model_config = ConfigDict(
        from_attributes=True,
        json_schema_extra={
            "example": {
                "project_id": "550e8400-e29b-41d4-a716-446655440001",
                "thread_id": "550e8400-e29b-41d4-a716-446655440002",
                "title": "S3 Bucket Configuration",
                "created_at": "2024-01-15T10:30:00Z",
                "last_message_at": "2024-01-15T10:35:00Z",
                "message_count": 5
            }
        }
    )

    project_id: str = Field(..., description="Project identifier")
    thread_id: Optional[str] = Field(None, description="Thread identifier")
    title: Optional[str] = Field(None, description="Thread title")
    created_at: datetime = Field(..., description="Thread creation timestamp")
    last_message_at: Optional[datetime] = Field(None, description="Last message timestamp")
    message_count: int = Field(default=0, description="Number of messages in thread")


class AutonomousMessageRequest(BaseModel):
    """Request model for autonomous chat messages."""

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "project_id": "550e8400-e29b-41d4-a716-446655440001",
                "message_content": "Create an S3 bucket with versioning enabled",
                "thread_id": "550e8400-e29b-41d4-a716-446655440002",
                "cloud_provider": "AWS"
            }
        }
    )

    project_id: str = Field(
        ...,
        description="Project ID (UUID) for the autonomous chat session"
    )
    message_content: str = Field(
        ...,
        min_length=1,
        max_length=10000,
        description="Content of the chat message"
    )
    thread_id: Optional[str] = Field(None, description="Existing conversation thread ID")
    cloud_provider: str = Field(
        default="AWS",
        description="Cloud provider for the infrastructure (AWS, Azure, GCP)"
    )


class AutonomousMessageResponse(BaseModel):
    """Response model for autonomous chat messages."""

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "thread_id": "550e8400-e29b-41d4-a716-446655440002",
                "message_id": "550e8400-e29b-41d4-a716-446655440003",
                "analysis": {
                    "is_complete": True,
                    "confidence_score": 0.85,
                    "intent": "Create S3 bucket"
                },
                "next_action": "generation_started",
                "job_id": "550e8400-e29b-41d4-a716-446655440004"
            }
        }
    )

    thread_id: str = Field(..., description="Conversation thread ID")
    message_id: str = Field(..., description="Saved message ID")
    analysis: Dict[str, Any] = Field(..., description="Prompt analysis results")
    next_action: str = Field(..., description="Next action to take")
    clarification_request: Optional[Dict[str, Any]] = Field(None, description="Clarification request if needed")
    generation_triggered: Optional[bool] = Field(None, description="Whether generation was triggered")
    job_id: Optional[str] = Field(None, description="Generation job ID")


class ClarificationResponseRequest(BaseModel):
    """Request model for responding to clarification requests."""

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "responses": {
                    "0": "AWS",
                    "1": "us-east-1"
                }
            }
        }
    )

    responses: Dict[str, str] = Field(
        ...,
        description="Dictionary mapping question indices to user answers"
    )


class ClarificationResponse(BaseModel):
    """Response model for clarification processing."""

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "clarification_processed": True,
                "thread_id": "550e8400-e29b-41d4-a716-446655440002",
                "is_now_complete": True,
                "next_action": "generation_started",
                "job_id": "550e8400-e29b-41d4-a716-446655440004"
            }
        }
    )

    clarification_processed: bool = Field(..., description="Whether clarification was processed")
    thread_id: str = Field(..., description="Conversation thread ID")
    is_now_complete: bool = Field(..., description="Whether prompt is now complete")
    next_action: str = Field(..., description="Next action to take")
    additional_questions: Optional[List[str]] = Field(None, description="Additional questions if still needed")
    generation_triggered: Optional[bool] = Field(None, description="Whether generation was triggered")
    job_id: Optional[str] = Field(None, description="Generation job ID")


class TerraformChatMessageRequest(BaseModel):
    """Request model for Terraform chat messages."""

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "message": "Create an S3 bucket with versioning enabled",
                "thread_id": "550e8400-e29b-41d4-a716-446655440002",
                "cloud_provider": "AWS"
            }
        }
    )

    message: str = Field(
        ...,
        min_length=1,
        max_length=10000,
        description="Content of the chat message"
    )
    thread_id: Optional[str] = Field(None, description="Existing conversation thread ID")
    cloud_provider: str = Field(
        default="AWS",
        description="Cloud provider for the infrastructure (AWS, Azure, GCP)"
    )


class TerraformChatMessageResponse(BaseModel):
    """Response model for Terraform chat messages."""

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "thread_id": "550e8400-e29b-41d4-a716-446655440002",
                "status": "clarification_needed",
                "clarification_questions": ["Which cloud provider would you like to use?", "Which region should the resources be deployed in?"],
                "message": "I need some additional information to generate the best Terraform code for you."
            }
        }
    )

    thread_id: str = Field(..., description="Conversation thread ID")
    status: str = Field(..., description="Status of the request (clarification_needed, generating, completed, error)")
    clarification_questions: List[str] = Field(default_factory=list, description="Questions to clarify requirements")
    generation_job_id: Optional[str] = Field(None, description="Generation job ID if generation was started")
    message: str = Field(..., description="Human-readable status message")


class TerraformClarificationResponseRequest(BaseModel):
    """Request model for responding to Terraform clarification requests."""

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "responses": {
                    "0": "AWS",
                    "1": "us-east-1"
                }
            }
        }
    )

    responses: Dict[str, str] = Field(
        ...,
        description="Dictionary mapping question indices to user answers"
    )


class TerraformClarificationResponse(BaseModel):
    """Response model for Terraform clarification processing."""

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "thread_id": "550e8400-e29b-41d4-a716-446655440002",
                "status": "generating",
                "generation_job_id": "550e8400-e29b-41d4-a716-446655440003",
                "message": "Terraform generation started with your clarifications."
            }
        }
    )

    thread_id: str = Field(..., description="Conversation thread ID")
    status: str = Field(..., description="Status after processing clarification")
    generation_job_id: Optional[str] = Field(None, description="Generation job ID if generation was started")
    message: str = Field(..., description="Human-readable status message")


# Dependency to get chat service
async def get_chat_service(db: AsyncSession = Depends(get_async_db)) -> ChatService:
    """Get chat service with database session."""
    return ChatService(db)


# Dependency to get terraform chat service
async def get_terraform_chat_service(db: AsyncSession = Depends(get_async_db)) -> TerraformChatService:
    """Get terraform chat service with database session."""
    return TerraformChatService(db)


async def _trigger_code_generation(
    project_id: str,
    user_id: str,
    user_query: str,
    db_session: AsyncSession,
    chat_service: ChatService
) -> None:
    """
    Background task to trigger code generation and save AI response.
    
    Args:
        project_id: Project ID for the generation
        user_id: User ID who made the request
        user_query: User's message content
        db_session: Database session
        chat_service: Chat service instance
    """
    try:
        # Import here to avoid circular imports
        from app.services.code_generation.project_orchestrator import get_project_integrated_orchestrator
        from app.services.code_generation.generation.pipeline import GenerationRequest
        from app.services.code_generation.generation.prompt_engineer import GenerationScenario
        
        # Check if this is a response to a provider question
        provider = await _detect_provider_from_response(user_query)
        if provider:
            # Get the previous user message to combine with provider info
            try:
                chat_history = await chat_service.get_chat_history(project_id, user_id, limit=5)
                previous_user_message = None
                for msg in reversed(chat_history):
                    if msg.message_type == MessageType.USER and msg.message_content != user_query:
                        previous_user_message = msg.message_content
                        break
                
                if previous_user_message:
                    # Combine the original request with provider info
                    enhanced_query = f"{previous_user_message} using {provider.upper()}"
                    user_query = enhanced_query
                    logger.info(f"Enhanced query with provider: {enhanced_query}")
            except Exception as e:
                logger.warning(f"Failed to get chat history for provider enhancement: {e}")
        else:
            # Check if we need to ask for provider information
            provider_needed = await _check_if_provider_needed(user_query)
            if provider_needed:
                # Ask user for provider information
                provider_question = await _generate_provider_question(user_query)
                await chat_service.save_message(
                    project_id=project_id,
                    user_id=user_id,
                    message_content=provider_question,
                    message_type=MessageType.AI
                )
                return  # Exit early, wait for user response
        
        # Use the real-time orchestrator with autonomous interaction
        from app.services.code_generation.realtime_orchestrator import RealtimeCodeGenerationOrchestrator

        orchestrator = RealtimeCodeGenerationOrchestrator(db_session)

        # Generate a unique generation ID for this request
        generation_id = str(uuid.uuid4())

        logger.info(f"Starting autonomous code generation for project {project_id} with query: {user_query[:100]}...")

        # Generate code using the real-time orchestrator with autonomous interaction
        result = await orchestrator.generate_code_with_realtime_monitoring(
            query=user_query,
            user_id=user_id,
            project_id=project_id,
            scenario=GenerationScenario.NEW_RESOURCE,
            enable_realtime=True
        )
        
        # Create generation record in database
        generation_record = None
        if result:
            try:
                from app.models.project import CodeGeneration, GenerationStatus
                from sqlalchemy import select

                generation_record = CodeGeneration(
                    id=generation_id,
                    project_id=project_id,
                    user_id=user_id,
                    query=user_query,
                    scenario=GenerationScenario.NEW_RESOURCE.value,
                    status=GenerationStatus.COMPLETED if result.success else GenerationStatus.FAILED,
                    generation_hash=generation_id[:16],  # Use first 16 chars of generation_id
                    error_message=getattr(result, 'error_message', None) if not result.success else None
                )

                db_session.add(generation_record)
                await db_session.flush()
                await db_session.commit()
                logger.info(f"Saved generation record {generation_id} to database")

            except Exception as db_error:
                logger.error(f"Failed to save generation record: {db_error}")
                # Continue even if DB save fails
        
        if result and result.success:
            # Save generated files to Azure File Share (if available)
            files_saved = []
            try:
                from app.services.azure_file_service import AzureFileService
                azure_service = AzureFileService()
                
                if result.generated_files:
                    # Save all files in one call using the correct method
                    save_result = await azure_service.save_generated_files(
                        user_id=user_id,
                        project_id=project_id,
                        generation_id=generation_id,
                        files=result.generated_files  # This is already a Dict[str, str]
                    )
                    
                    if save_result.success:
                        files_saved = save_result.saved_files
                        logger.info(f"Saved {len(files_saved)} generated files to Azure File Share: {files_saved}")
                    else:
                        logger.error(f"Failed to save files to Azure: {save_result.error}")
                            
            except Exception as azure_error:
                logger.warning(f"Azure File Service not available: {azure_error}")
            
            # Save AI response to chat
            ai_response = f"I've generated the following code for your request:\n\n"
            
            if result.generated_files:
                for file_path, content in result.generated_files.items():
                    ai_response += f"**{file_path}:**\n```hcl\n{content}\n```\n\n"
            elif result.generated_code:
                ai_response += f"```hcl\n{result.generated_code}\n```\n\n"
            
            if files_saved:
                ai_response += f"✅ **Generation ID: `{generation_id}`**\n"
                ai_response += f"Files saved to your project: {', '.join(files_saved)}\n\n"
                ai_response += f"You can find these files in your project under generation `{generation_id[:8]}...`"

                # Create ProjectFile records in database for file share visibility
                try:
                    from app.models.project import ProjectFile
                    from sqlalchemy import select

                    for filename in files_saved:
                        # Get file path relative to generation
                        file_path = f"{generation_id}/{filename}"

                        # Get file content to calculate hash and size
                        file_content = result.generated_files.get(filename, "")
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

                            db_session.add(project_file)
                            await db_session.flush()

                    await db_session.commit()
                    logger.info(f"Created {len(files_saved)} ProjectFile records for generation {generation_id}")

                except Exception as db_error:
                    logger.error(f"Failed to create ProjectFile records: {db_error}")
                    # Don't fail the entire operation if DB save fails
            else:
                ai_response += f"The code has been generated successfully. You can copy and use it in your project."
            
            # Save AI response as a chat message
            await chat_service.save_message(
                project_id=project_id,
                user_id=user_id,  # Using same user_id for now, could be system user
                message_content=ai_response,
                message_type=MessageType.AI
            )
            
            # Send WebSocket notification that generation completed
            try:
                await realtime_service.websocket_manager.send_to_user(
                    user_id,
                    {
                        "type": "generation_completed",
                        "project_id": project_id,
                        "generation_id": generation_id,
                        "files_generated": list(result.generated_files.keys()) if result.generated_files else [],
                        "files_saved": files_saved,
                        "message": f"✅ Generated {len(files_saved)} files successfully!",
                        "timestamp": datetime.utcnow().isoformat()
                    }
                )
            except Exception as ws_error:
                logger.warning(f"Failed to send completion WebSocket notification: {ws_error}")
            
            logger.info(f"Code generation completed successfully for project {project_id}")
            
        else:
            # Save error response to chat
            error_message = "I encountered an error while generating code for your request. Please try rephrasing your request or check the project configuration."
            if result and hasattr(result, 'error_message') and result.error_message:
                error_message += f"\n\nError details: {result.error_message}"
            
            await chat_service.save_message(
                project_id=project_id,
                user_id=user_id,
                message_content=error_message,
                message_type=MessageType.AI
            )
            
            logger.error(f"Code generation failed for project {project_id}: {result.error_message if result and hasattr(result, 'error_message') else 'Unknown error'}")
            
    except Exception as e:
        logger.error(f"Error in code generation background task for project {project_id}: {e}")
        
        # Save error message to chat
        try:
            error_message = "I'm sorry, but I encountered an unexpected error while processing your request. Please try again later."
            await chat_service.save_message(
                project_id=project_id,
                user_id=user_id,
                message_content=error_message,
                message_type=MessageType.AI
            )
        except Exception as chat_error:
            logger.error(f"Failed to save error message to chat: {chat_error}")


async def _check_if_provider_needed(user_query: str) -> bool:
    """
    Check if the user query requires specific cloud provider information.
    
    Args:
        user_query: User's message content
        
    Returns:
        True if provider information is needed
    """
    # Simple keyword detection for cloud providers
    cloud_keywords = {
        'aws': ['s3', 'ec2', 'vpc', 'lambda', 'rds', 'iam', 'cloudfront', 'route53'],
        'azure': ['storage account', 'virtual machine', 'app service', 'cosmos', 'key vault'],
        'gcp': ['cloud storage', 'compute engine', 'cloud function', 'bigquery', 'cloud sql']
    }
    
    query_lower = user_query.lower()
    
    # Check if query contains generic terms that could apply to multiple providers
    generic_terms = ['database', 'storage', 'compute', 'network', 'load balancer', 'cdn']
    has_generic_terms = any(term in query_lower for term in generic_terms)
    
    # Check if query already specifies a provider
    has_specific_provider = any(
        any(keyword in query_lower for keyword in keywords)
        for keywords in cloud_keywords.values()
    )
    
    # If it has generic terms but no specific provider, ask for clarification
    return has_generic_terms and not has_specific_provider


async def _generate_provider_question(user_query: str) -> str:
    """
    Generate a question asking the user to specify the cloud provider.
    
    Args:
        user_query: User's original query
        
    Returns:
        Question message for the user
    """
    return f"""I'd be happy to help you with that! To generate the most accurate Terraform code, could you please specify which cloud provider you'd like to use?

**Available options:**
🔹 **AWS** - Amazon Web Services
🔹 **Azure** - Microsoft Azure  
🔹 **GCP** - Google Cloud Platform

For example, you could say:
- "Create an AWS S3 bucket with versioning"
- "Set up an Azure storage account"
- "Deploy a GCP Cloud Storage bucket"

Which provider would you prefer for: "{user_query}"?"""


async def _detect_provider_from_response(user_response: str) -> Optional[str]:
    """
    Detect cloud provider from user's response.
    
    Args:
        user_response: User's response message
        
    Returns:
        Detected provider ('aws', 'azure', 'gcp') or None
    """
    response_lower = user_response.lower()
    
    if any(keyword in response_lower for keyword in ['aws', 'amazon']):
        return 'aws'
    elif any(keyword in response_lower for keyword in ['azure', 'microsoft']):
        return 'azure'
    elif any(keyword in response_lower for keyword in ['gcp', 'google', 'cloud platform']):
        return 'gcp'
    
    return None


@router.post(
    "/{project_id}/chat/messages",
    response_model=SaveMessageResponse,
    summary="Save chat message and trigger code generation",
    description="""
    Save a new chat message for a project and trigger code generation if it's a user message.
    
    - Validates user has access to the project
    - Automatically associates message with project and user
    - Triggers code generation for user messages
    - Supports different message types (user, system, ai)
    - Returns the saved message with generated ID and timestamp
    """,
    responses={
        200: {"description": "Message saved successfully and code generation triggered"},
        400: {"description": "Invalid message data", "model": ErrorResponse},
        401: {"description": "Authentication required"},
        403: {"description": "Access denied - user lacks project access", "model": ErrorResponse},
        404: {"description": "Project not found", "model": ErrorResponse},
        500: {"description": "Internal server error", "model": ErrorResponse}
    }
)
async def save_message(
    background_tasks: BackgroundTasks,
    project_id: str = Path(..., description="Project ID (UUID)"),
    request: SaveMessageRequest = Body(...),
    user_id: str = Depends(get_current_user_id),
    chat_service: ChatService = Depends(get_chat_service),
    db: AsyncSession = Depends(get_async_db)
) -> SaveMessageResponse:
    """
    Save a chat message for a project and trigger code generation if it's a user message.
    
    Args:
        project_id: Project ID to save message for
        request: Message data to save
        background_tasks: Background tasks for async code generation
        user_id: Supabase user ID from JWT token
        chat_service: Chat service instance
        db: Database session
        
    Returns:
        SaveMessageResponse with saved message details
        
    Raises:
        HTTPException: If operation fails
    """
    try:
        # Save the message using chat service
        saved_message = await chat_service.save_message(
            project_id=project_id,
            user_id=user_id,
            message_content=request.message_content,
            message_type=request.message_type
        )
        
        # Trigger code generation for user messages
        if request.message_type == MessageType.USER:
            background_tasks.add_task(
                _trigger_code_generation,
                project_id=project_id,
                user_id=user_id,
                user_query=request.message_content,
                db_session=db,
                chat_service=chat_service
            )
            logger.info(f"Triggered code generation for user message in project {project_id}")
        
        # Convert to response model
        message_response = ChatMessageResponse(
            id=saved_message.id,
            project_id=saved_message.project_id,
            user_id=saved_message.user_id,
            message_content=saved_message.message_content,
            message_type=saved_message.message_type,
            timestamp=saved_message.timestamp,
            generation_id=saved_message.generation_id
        )
        
        logger.info(f"Saved chat message {saved_message.id} for project {project_id} by user {user_id}")
        
        return SaveMessageResponse(
            message=message_response,
            success=True,
            message_text="Message saved successfully and code generation triggered" if request.message_type == MessageType.USER else "Message saved successfully"
        )
        
    except ChatValidationError as e:
        logger.warning(f"Chat validation error for project {project_id}, user {user_id}: {e}")
        raise HTTPException(
            status_code=400,
            detail=ErrorResponse(
                error="ChatValidationError",
                message=str(e),
                details={"project_id": project_id, "field": getattr(e, 'field', None)}
            ).model_dump()
        )
    except ChatAccessDeniedError as e:
        logger.warning(f"Chat access denied for project {project_id}, user {user_id}: {e}")
        raise HTTPException(
            status_code=403,
            detail=ErrorResponse(
                error="ChatAccessDenied",
                message=str(e),
                details={"project_id": project_id, "user_id": user_id}
            ).model_dump()
        )
    except ChatServiceError as e:
        logger.error(f"Chat service error saving message for project {project_id}, user {user_id}: {e}")
        raise HTTPException(
            status_code=500,
            detail=ErrorResponse(
                error="ChatServiceError",
                message="Failed to save chat message",
                details={"project_id": project_id}
            ).model_dump()
        )
    except Exception as e:
        logger.error(f"Unexpected error saving message for project {project_id}, user {user_id}: {e}")
        raise HTTPException(
            status_code=500,
            detail=ErrorResponse(
                error="InternalServerError",
                message="An unexpected error occurred while saving the message",
                details={"project_id": project_id}
            ).model_dump()
        )


@router.get(
    "/{project_id}/chat/messages",
    response_model=ChatHistoryResponse,
    summary="Get chat history",
    description="""
    Retrieve chat history for a project in chronological order.
    
    - Validates user has access to the project
    - Returns messages in chronological order (oldest first)
    - Supports pagination with limit and offset parameters
    - Includes message metadata and user information
    """,
    responses={
        200: {"description": "Chat history retrieved successfully"},
        401: {"description": "Authentication required"},
        403: {"description": "Access denied - user lacks project access", "model": ErrorResponse},
        404: {"description": "Project not found", "model": ErrorResponse},
        500: {"description": "Internal server error", "model": ErrorResponse}
    }
)
async def get_chat_history(
    project_id: str = Path(..., description="Project ID (UUID)"),
    limit: Optional[int] = Query(None, ge=1, le=1000, description="Maximum number of messages to return"),
    offset: int = Query(0, ge=0, description="Number of messages to skip (for pagination)"),
    user_id: str = Depends(get_current_user_id),
    chat_service: ChatService = Depends(get_chat_service)
) -> ChatHistoryResponse:
    """
    Get chat history for a project.
    
    Args:
        project_id: Project ID to get chat history for
        limit: Maximum number of messages to return
        offset: Number of messages to skip for pagination
        user_id: Supabase user ID from JWT token
        chat_service: Chat service instance
        
    Returns:
        ChatHistoryResponse with chat messages
        
    Raises:
        HTTPException: If operation fails
    """
    try:
        # Get chat history using chat service
        messages = await chat_service.get_chat_history(
            project_id=project_id,
            user_id=user_id,
            limit=limit,
            offset=offset
        )
        
        # Convert to response models
        message_responses = []
        for message in messages:
            message_response = ChatMessageResponse(
                id=message.id,
                project_id=message.project_id,
                user_id=message.user_id,
                message_content=message.message_content,
                message_type=message.message_type,
                timestamp=message.timestamp,
                generation_id=message.generation_id
            )
            message_responses.append(message_response)
        
        # Determine if there are more messages
        has_more = False
        if limit is not None and len(messages) == limit:
            # Check if there are more messages by trying to get one more
            try:
                next_messages = await chat_service.get_chat_history(
                    project_id=project_id,
                    user_id=user_id,
                    limit=1,
                    offset=offset + len(messages)
                )
                has_more = len(next_messages) > 0
            except Exception:
                # If we can't check, assume no more messages
                has_more = False
        
        logger.info(f"Retrieved {len(messages)} chat messages for project {project_id}")
        
        return ChatHistoryResponse(
            project_id=project_id,
            messages=message_responses,
            total_count=len(messages),  # Note: This is returned count, not total in DB
            returned_count=len(messages),
            has_more=has_more,
            message_text=f"Retrieved {len(messages)} chat messages successfully"
        )
        
    except ChatValidationError as e:
        logger.warning(f"Chat validation error for project {project_id}, user {user_id}: {e}")
        raise HTTPException(
            status_code=400,
            detail=ErrorResponse(
                error="ChatValidationError",
                message=str(e),
                details={"project_id": project_id, "field": getattr(e, 'field', None)}
            ).model_dump()
        )
    except ChatAccessDeniedError as e:
        logger.warning(f"Chat access denied for project {project_id}, user {user_id}: {e}")
        raise HTTPException(
            status_code=403,
            detail=ErrorResponse(
                error="ChatAccessDenied",
                message=str(e),
                details={"project_id": project_id, "user_id": user_id}
            ).model_dump()
        )
    except ChatServiceError as e:
        logger.error(f"Chat service error getting history for project {project_id}, user {user_id}: {e}")
        raise HTTPException(
            status_code=500,
            detail=ErrorResponse(
                error="ChatServiceError",
                message="Failed to retrieve chat history",
                details={"project_id": project_id}
            ).model_dump()
        )
    except Exception as e:
        logger.error(f"Unexpected error getting history for project {project_id}, user {user_id}: {e}")
        raise HTTPException(
            status_code=500,
            detail=ErrorResponse(
                error="InternalServerError",
                message="An unexpected error occurred while retrieving chat history",
                details={"project_id": project_id}
            ).model_dump()
        )


@router.get(
    "/{project_id}/generations",
    summary="List project generations",
    description="""
    List all code generations for a project from database with file information.
    
    This helps users see which generation files to choose from.
    """,
    responses={
        200: {"description": "Successfully retrieved generations"},
        401: {"description": "Authentication required"},
        403: {"description": "Access denied", "model": ErrorResponse},
        404: {"description": "Project not found", "model": ErrorResponse},
        500: {"description": "Internal server error", "model": ErrorResponse}
    }
)
async def list_project_generations(
    project_id: str = Path(..., description="Project ID (UUID)"),
    user_id: str = Depends(get_current_user_id),
    chat_service: ChatService = Depends(get_chat_service),
    db: AsyncSession = Depends(get_async_db)
) -> Dict[str, Any]:
    """
    List all generations for a project from database and Azure files.
    
    Args:
        project_id: Project ID to get generations for
        user_id: Supabase user ID from JWT token
        chat_service: Chat service instance
        db: Database session
        
    Returns:
        Dictionary with generation information
    """
    try:
        # Validate project access
        await chat_service._validate_project_access(project_id, user_id)
        
        # Get generations from database
        from app.models.project import CodeGeneration
        from sqlalchemy import select, desc
        
        query = select(CodeGeneration).where(
            CodeGeneration.project_id == project_id
        ).order_by(desc(CodeGeneration.created_at))
        
        result = await db.execute(query)
        db_generations = result.scalars().all()
        
        # Get file information from Azure
        generations_with_files = []
        try:
            from app.services.azure_file_service import AzureFileService
            azure_service = AzureFileService()
            files = await azure_service.list_user_files(user_id, project_id)
            
            # Group files by generation_id
            files_by_generation = {}
            for file_info in files:
                gen_id = file_info.generation_id
                if gen_id not in files_by_generation:
                    files_by_generation[gen_id] = []
                files_by_generation[gen_id].append({
                    "name": file_info.name,
                    "path": file_info.relative_path,
                    "size": file_info.size
                })
            
            # Combine database and file information
            for gen in db_generations:
                gen_files = files_by_generation.get(gen.id, [])

                # Create a description/summary for the generation
                description = f"Generated {len(gen_files)} file{'s' if len(gen_files) != 1 else ''}"
                if gen_files:
                    file_types = list(set(f["name"].split(".")[-1] for f in gen_files if "." in f["name"]))
                    if file_types:
                        description += f" ({', '.join(file_types)})"
                description += f" - {gen.status.value}"

                generations_with_files.append({
                    "generation_id": gen.id,
                    "query": gen.query,
                    "scenario": gen.scenario,
                    "status": gen.status.value,
                    "created_at": gen.created_at,
                    "updated_at": gen.updated_at,
                    "generation_hash": gen.generation_hash,
                    "error_message": gen.error_message,
                    "files": gen_files,
                    "file_count": len(gen_files),
                    "description": description,
                    "summary": f"Generation {gen.id[:8]}... - {gen.query[:50]}{'...' if len(gen.query) > 50 else ''}"
                })
                
        except Exception as azure_error:
            logger.warning(f"Azure service error: {azure_error}")
            # Return database info only
            for gen in db_generations:
                # Create description even without files
                description = f"Generation {gen.status.value}"
                if gen.error_message:
                    description += f" - Error: {gen.error_message[:50]}..."
                else:
                    description += " - No files available"

                generations_with_files.append({
                    "generation_id": gen.id,
                    "query": gen.query,
                    "scenario": gen.scenario,
                    "status": gen.status.value,
                    "created_at": gen.created_at,
                    "updated_at": gen.updated_at,
                    "generation_hash": gen.generation_hash,
                    "error_message": gen.error_message,
                    "files": [],
                    "file_count": 0,
                    "description": description,
                    "summary": f"Generation {gen.id[:8]}... - {gen.query[:50]}{'...' if len(gen.query) > 50 else ''}"
                })
        
        return {
            "project_id": project_id,
            "generations": generations_with_files,
            "total_count": len(generations_with_files),
            "message": f"Found {len(generations_with_files)} generations"
        }
        
    except Exception as e:
        logger.error(f"Error listing generations for project {project_id}: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to list generations: {str(e)}"
        )


@router.get(
    "/{project_id}/generations/{generation_id}/files",
    summary="Get generation files",
    description="""
    Get all files for a specific generation with their content.
    """,
    responses={
        200: {"description": "Successfully retrieved generation files"},
        401: {"description": "Authentication required"},
        403: {"description": "Access denied", "model": ErrorResponse},
        404: {"description": "Generation not found", "model": ErrorResponse},
        500: {"description": "Internal server error", "model": ErrorResponse}
    }
)
async def get_generation_files(
    project_id: str = Path(..., description="Project ID (UUID)"),
    generation_id: str = Path(..., description="Generation ID (UUID)"),
    include_content: bool = Query(False, description="Include file content"),
    user_id: str = Depends(get_current_user_id),
    chat_service: ChatService = Depends(get_chat_service)
) -> Dict[str, Any]:
    """
    Get all files for a specific generation.
    
    Args:
        project_id: Project ID
        generation_id: Generation ID
        include_content: Whether to include file content
        user_id: Supabase user ID from JWT token
        chat_service: Chat service instance
        
    Returns:
        Dictionary with generation files
    """
    try:
        # Validate project access
        await chat_service._validate_project_access(project_id, user_id)
        
        # Get files from Azure File Service
        from app.services.azure_file_service import AzureFileService
        azure_service = AzureFileService()
        
        try:
            # Get all files for this generation
            all_files = await azure_service.list_user_files(user_id, project_id)
            generation_files = [f for f in all_files if f.generation_id == generation_id]
            
            if not generation_files:
                raise HTTPException(
                    status_code=404,
                    detail=f"No files found for generation {generation_id}"
                )
            
            files_data = []
            for file_info in generation_files:
                file_data = {
                    "name": file_info.name,
                    "path": file_info.relative_path,
                    "size": file_info.size,
                    "modified_date": file_info.modified_date,
                    "content_type": file_info.content_type
                }
                
                if include_content:
                    try:
                        content = await azure_service.get_file_content(
                            user_id=user_id,
                            project_id=project_id,
                            generation_id=generation_id,
                            file_path=file_info.relative_path
                        )
                        file_data["content"] = content
                    except Exception as content_error:
                        logger.warning(f"Failed to get content for {file_info.name}: {content_error}")
                        file_data["content"] = None
                
                files_data.append(file_data)
            
            return {
                "project_id": project_id,
                "generation_id": generation_id,
                "files": files_data,
                "file_count": len(files_data),
                "total_size": sum(f["size"] for f in files_data),
                "message": f"Retrieved {len(files_data)} files for generation {generation_id[:8]}..."
            }
            
        except HTTPException:
            raise
        except Exception as azure_error:
            logger.error(f"Azure service error: {azure_error}")
            raise HTTPException(
                status_code=500,
                detail=f"Failed to retrieve generation files: {str(azure_error)}"
            )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting generation files: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get generation files: {str(e)}"
        )


@router.get(
    "/{project_id}/generations/{generation_id}/files/{file_path:path}",
    summary="Get specific generation file",
    description="""
    Get a specific file from a generation with its content.
    """,
    responses={
        200: {"description": "Successfully retrieved file"},
        401: {"description": "Authentication required"},
        403: {"description": "Access denied", "model": ErrorResponse},
        404: {"description": "File not found", "model": ErrorResponse},
        500: {"description": "Internal server error", "model": ErrorResponse}
    }
)
async def get_generation_file(
    project_id: str = Path(..., description="Project ID (UUID)"),
    generation_id: str = Path(..., description="Generation ID (UUID)"),
    file_path: str = Path(..., description="File path within generation"),
    user_id: str = Depends(get_current_user_id),
    chat_service: ChatService = Depends(get_chat_service)
) -> Dict[str, Any]:
    """
    Get a specific file from a generation.
    
    Args:
        project_id: Project ID
        generation_id: Generation ID
        file_path: File path within the generation
        user_id: Supabase user ID from JWT token
        chat_service: Chat service instance
        
    Returns:
        Dictionary with file information and content
    """
    try:
        # Validate project access
        await chat_service._validate_project_access(project_id, user_id)
        
        # Get file from Azure File Service
        from app.services.azure_file_service import AzureFileService
        azure_service = AzureFileService()
        
        try:
            content = await azure_service.get_file_content(
                user_id=user_id,
                project_id=project_id,
                generation_id=generation_id,
                file_path=file_path
            )
            
            if content is None:
                raise HTTPException(
                    status_code=404,
                    detail=f"File {file_path} not found in generation {generation_id}"
                )
            
            # Get file metadata
            all_files = await azure_service.list_user_files(user_id, project_id)
            file_info = next(
                (f for f in all_files if f.generation_id == generation_id and f.relative_path == file_path),
                None
            )
            
            return {
                "project_id": project_id,
                "generation_id": generation_id,
                "file_path": file_path,
                "content": content,
                "size": file_info.size if file_info else len(content.encode('utf-8')),
                "modified_date": file_info.modified_date if file_info else None,
                "content_type": file_info.content_type if file_info else "text/plain",
                "message": f"Retrieved file {file_path}"
            }
            
        except HTTPException:
            raise
        except Exception as azure_error:
            logger.error(f"Azure service error: {azure_error}")
            raise HTTPException(
                status_code=500,
                detail=f"Failed to retrieve file: {str(azure_error)}"
            )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting generation file: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get generation file: {str(e)}"
        )


# Terraform Chat Endpoints

@router.post(
    "/{project_id}/terraform-chat/messages",
    response_model=TerraformChatMessageResponse,
    summary="Send Terraform chat message",
    description="""Send a message to the Terraform chat system for conversational code generation.

    The system will analyze your request and either:
    - Ask clarification questions if more information is needed
    - Start generating Terraform code immediately

    Real-time updates are sent via WebSocket during the process.
    """,
    responses={
        200: {"description": "Message processed successfully"},
        400: {"description": "Invalid message data", "model": ErrorResponse},
        401: {"description": "Authentication required"},
        403: {"description": "Access denied", "model": ErrorResponse},
        500: {"description": "Internal server error", "model": ErrorResponse}
    }
)
async def send_terraform_chat_message(
    project_id: str = Path(..., description="Project ID (UUID)"),
    request: TerraformChatMessageRequest = Body(...),
    user_id: str = Depends(get_current_user_id),
    terraform_chat_service: TerraformChatService = Depends(get_terraform_chat_service)
) -> TerraformChatMessageResponse:
    """
    Send a message to the Terraform chat system.

    Args:
        project_id: Project ID for the chat session
        request: Message data with content and optional thread_id
        user_id: Supabase user ID from JWT token
        terraform_chat_service: Terraform chat service instance

    Returns:
        TerraformChatMessageResponse with processing results

    Raises:
        HTTPException: If operation fails
    """
    try:
        # Create the chat request
        chat_request = TerraformChatRequest(
            user_id=user_id,
            project_id=project_id,
            message=request.message,
            thread_id=request.thread_id,
            cloud_provider=request.cloud_provider
        )

        # Process the message
        result = await terraform_chat_service.process_message(chat_request)

        # Convert to response model
        response = TerraformChatMessageResponse(
            thread_id=result.thread_id,
            status=result.status,
            clarification_questions=result.clarification_questions,
            generation_job_id=result.generation_job_id,
            message=result.message
        )

        logger.info(f"Processed Terraform chat message for thread {result.thread_id}: {result.status}")
        return response

    except Exception as e:
        logger.error(f"Error processing Terraform chat message: {e}")
        raise HTTPException(
            status_code=500,
            detail=ErrorResponse(
                error="InternalServerError",
                message="An unexpected error occurred while processing the message"
            ).model_dump()
        )


@router.post(
    "/{project_id}/terraform-chat/clarifications/{thread_id}/respond",
    response_model=TerraformClarificationResponse,
    summary="Respond to Terraform clarification questions",
    description="""Submit responses to clarification questions asked by the Terraform chat system.

    After providing answers, the system will either ask more questions or start generating code.
    """,
    responses={
        200: {"description": "Clarification response processed successfully"},
        400: {"description": "Invalid response data", "model": ErrorResponse},
        401: {"description": "Authentication required"},
        403: {"description": "Access denied", "model": ErrorResponse},
        500: {"description": "Internal server error", "model": ErrorResponse}
    }
)
async def respond_to_terraform_clarification(
    project_id: str = Path(..., description="Project ID (UUID)"),
    thread_id: str = Path(..., description="Conversation thread ID"),
    request: TerraformClarificationResponseRequest = Body(...),
    user_id: str = Depends(get_current_user_id),
    terraform_chat_service: TerraformChatService = Depends(get_terraform_chat_service)
) -> TerraformClarificationResponse:
    """
    Respond to Terraform clarification questions.

    Args:
        project_id: Project ID
        thread_id: Conversation thread ID
        request: Response data with answers to questions
        user_id: Supabase user ID from JWT token
        terraform_chat_service: Terraform chat service instance

    Returns:
        TerraformClarificationResponse with processing results

    Raises:
        HTTPException: If operation fails
    """
    try:
        # Process the clarification response
        result = await terraform_chat_service.process_clarification_response(
            project_id=project_id,
            user_id=user_id,
            thread_id=thread_id,
            responses=request.responses
        )

        # Convert to response model
        response = TerraformClarificationResponse(
            thread_id=result.thread_id,
            status=result.status,
            generation_job_id=result.generation_job_id,
            message=result.message
        )

        logger.info(f"Processed Terraform clarification response for thread {thread_id}: {result.status}")
        return response

    except Exception as e:
        logger.error(f"Error processing Terraform clarification response: {e}")
        raise HTTPException(
            status_code=500,
            detail=ErrorResponse(
                error="InternalServerError",
                message="An unexpected error occurred while processing the clarification response"
            ).model_dump()
        )


@router.get(
    "/{project_id}/terraform-chat/threads/{thread_id}/messages",
    summary="Get Terraform chat message history",
    description="""Get the complete message history for a Terraform chat conversation thread.

    Returns all messages in chronological order, including user messages, system responses,
    clarification requests, and generation summaries.
    """,
    responses={
        200: {"description": "Message history retrieved successfully"},
        401: {"description": "Authentication required"},
        403: {"description": "Access denied", "model": ErrorResponse},
        404: {"description": "Thread not found", "model": ErrorResponse},
        500: {"description": "Internal server error", "model": ErrorResponse}
    }
)
async def get_terraform_chat_history(
    project_id: str = Path(..., description="Project ID (UUID)"),
    thread_id: str = Path(..., description="Conversation thread ID"),
    limit: int = Query(50, ge=1, le=200, description="Maximum number of messages to return"),
    user_id: str = Depends(get_current_user_id),
    terraform_chat_service: TerraformChatService = Depends(get_terraform_chat_service)
) -> Dict[str, Any]:
    """
    Get message history for a Terraform chat thread.

    Args:
        project_id: Project ID
        thread_id: Conversation thread ID
        limit: Maximum number of messages to return
        user_id: Supabase user ID from JWT token
        terraform_chat_service: Terraform chat service instance

    Returns:
        Dictionary with message history

    Raises:
        HTTPException: If operation fails
    """
    try:
        # Get message history
        messages = await terraform_chat_service.get_message_history(
            project_id=project_id,
            user_id=user_id,
            thread_id=thread_id,
            limit=limit
        )

        return {
            "project_id": project_id,
            "thread_id": thread_id,
            "messages": messages,
            "total_count": len(messages),
            "message": f"Retrieved {len(messages)} messages for thread {thread_id[:8]}..."
        }

    except Exception as e:
        logger.error(f"Error getting Terraform chat history: {e}")
        raise HTTPException(
            status_code=500,
            detail=ErrorResponse(
                error="InternalServerError",
                message="An unexpected error occurred while retrieving message history"
            ).model_dump()
        )


# Autonomous Chat Endpoints

@autonomous_router.post(
    "/messages",
    response_model=AutonomousMessageResponse,
    summary="Send autonomous chat message",
    description="""
    Send a message through the autonomous chat system.

    The system will analyze the prompt for completeness, generate clarification
    questions if needed, and trigger code generation when ready.

    - Automatically creates conversation threads
    - Uses LLM analysis for prompt completeness
    - Generates targeted clarification questions
    - Triggers code generation with proper context
    """,
    responses={
        200: {"description": "Message processed successfully"},
        400: {"description": "Invalid message data", "model": ErrorResponse},
        401: {"description": "Authentication required"},
        403: {"description": "Access denied", "model": ErrorResponse},
        500: {"description": "Internal server error", "model": ErrorResponse}
    }
)
async def send_autonomous_message(
    request: AutonomousMessageRequest = Body(...),
    user_id: str = Depends(get_current_user_id),
    chat_service: ChatService = Depends(get_chat_service),
    db: AsyncSession = Depends(get_async_db)
) -> AutonomousMessageResponse:
    """
    Send a message through the autonomous chat system.

    Args:
        request: Message data with project_id, content and optional thread_id
        user_id: Supabase user ID from JWT token
        chat_service: Chat service instance
        db: Database session

    Returns:
        AutonomousMessageResponse with processing results

    Raises:
        HTTPException: If operation fails
    """
    try:
        # Process the autonomous message
        result = await chat_service.process_autonomous_message(
            project_id=request.project_id,
            user_id=user_id,
            message_content=request.message_content,
            thread_id=request.thread_id,
            cloud_provider=request.cloud_provider
        )

        # Convert to response model
        response = AutonomousMessageResponse(
            thread_id=result["thread_id"],
            message_id=result["message_id"],
            analysis=result["analysis"],
            next_action=result["next_action"],
            clarification_request=result.get("clarification_request"),
            generation_triggered=result.get("generation_triggered"),
            job_id=result.get("job_id")
        )

        logger.info(f"Processed autonomous message for thread {result['thread_id']}: {result['next_action']}")
        return response

    except ChatValidationError as e:
        logger.warning(f"Chat validation error for autonomous message: {e}")
        raise HTTPException(
            status_code=400,
            detail=ErrorResponse(
                error="ChatValidationError",
                message=str(e),
                details={"field": getattr(e, 'field', None)}
            ).model_dump()
        )
    except ChatAccessDeniedError as e:
        logger.warning(f"Chat access denied for autonomous message: {e}")
        raise HTTPException(
            status_code=403,
            detail=ErrorResponse(
                error="ChatAccessDenied",
                message=str(e),
                details={"user_id": user_id}
            ).model_dump()
        )
    except ChatServiceError as e:
        logger.error(f"Chat service error processing autonomous message: {e}")
        raise HTTPException(
            status_code=500,
            detail=ErrorResponse(
                error="ChatServiceError",
                message="Failed to process autonomous message"
            ).model_dump()
        )
    except Exception as e:
        logger.error(f"Unexpected error processing autonomous message: {e}")
        raise HTTPException(
            status_code=500,
            detail=ErrorResponse(
                error="InternalServerError",
                message="An unexpected error occurred while processing the message"
            ).model_dump()
        )


@autonomous_router.get(
    "/conversations",
    response_model=List[ConversationThreadResponse],
    summary="List conversation threads",
    description="""
    Get a list of conversation threads for the authenticated user and project.

    - Returns threads in chronological order (most recent first)
    - Includes thread metadata and message counts
    - Supports pagination with limit parameter
    """,
    responses={
        200: {"description": "Conversation threads retrieved successfully"},
        401: {"description": "Authentication required"},
        500: {"description": "Internal server error", "model": ErrorResponse}
    }
)
async def list_conversation_threads(
    project_id: str = Query(..., description="Project ID (UUID) to get threads for"),
    limit: int = Query(10, ge=1, le=50, description="Maximum number of threads to return"),
    user_id: str = Depends(get_current_user_id),
    chat_service: ChatService = Depends(get_chat_service)
) -> List[ConversationThreadResponse]:
    """
    List conversation threads for the user and project.

    Args:
        project_id: Project ID to get threads for
        limit: Maximum number of threads to return
        user_id: Supabase user ID from JWT token
        chat_service: Chat service instance

    Returns:
        List of conversation threads

    Raises:
        HTTPException: If operation fails
    """
    try:
        # Get conversation threads
        threads = await chat_service.get_conversation_threads(
            project_id=project_id,
            user_id=user_id,
            limit=limit
        )

        # Convert to response models
        thread_responses = []
        for thread in threads:
            response = ConversationThreadResponse(
                project_id=thread["project_id"],
                thread_id=thread.get("thread_id"),
                title=thread.get("title"),
                created_at=thread["created_at"],
                last_message_at=thread.get("last_message_at"),
                message_count=thread.get("message_count", 0)
            )
            thread_responses.append(response)

        logger.info(f"Retrieved {len(thread_responses)} conversation threads for user {user_id}")
        return thread_responses

    except ChatServiceError as e:
        logger.error(f"Chat service error listing threads: {e}")
        raise HTTPException(
            status_code=500,
            detail=ErrorResponse(
                error="ChatServiceError",
                message="Failed to retrieve conversation threads"
            ).model_dump()
        )
    except Exception as e:
        logger.error(f"Unexpected error listing conversation threads: {e}")
        raise HTTPException(
            status_code=500,
            detail=ErrorResponse(
                error="InternalServerError",
                message="An unexpected error occurred while retrieving threads"
            ).model_dump()
        )


@autonomous_router.post(
    "/clarifications/{request_id}/respond",
    response_model=ClarificationResponse,
    summary="Respond to clarification request",
    description="""
    Submit responses to clarification questions.

    The system will process the responses, potentially generate additional
    questions, and trigger code generation when the prompt is complete.

    - Updates clarification request status
    - Re-analyzes prompt completeness
    - Triggers code generation if ready
    """,
    responses={
        200: {"description": "Clarification response processed successfully"},
        400: {"description": "Invalid response data", "model": ErrorResponse},
        401: {"description": "Authentication required"},
        403: {"description": "Access denied", "model": ErrorResponse},
        404: {"description": "Clarification request not found", "model": ErrorResponse},
        500: {"description": "Internal server error", "model": ErrorResponse}
    }
)
async def respond_to_clarification(
    project_id: str = Query(..., description="Project ID (UUID)"),
    request_id: str = Path(..., description="Clarification request ID"),
    request: ClarificationResponseRequest = Body(...),
    user_id: str = Depends(get_current_user_id),
    chat_service: ChatService = Depends(get_chat_service)
) -> ClarificationResponse:
    """
    Respond to a clarification request.

    Args:
        project_id: Project ID
        request_id: Clarification request ID
        request: Response data with answers to questions
        user_id: Supabase user ID from JWT token
        chat_service: Chat service instance

    Returns:
        ClarificationResponse with processing results

    Raises:
        HTTPException: If operation fails
    """
    try:
        # Extract clarification round from the stored message
        clarification_round = 1
        try:
            # Find the clarification message to get the round
            from app.models.chat import ProjectChat, MessageType
            from sqlalchemy import select, desc

            query = select(ProjectChat).where(
                ProjectChat.project_id == project_id,
                ProjectChat.message_type == MessageType.CLARIFICATION_REQUEST
            ).order_by(desc(ProjectChat.timestamp))

            result_query = await db.execute(query)
            clarification_msg = result_query.scalar_one_or_none()

            if clarification_msg:
                import json
                clarification_data = json.loads(clarification_msg.message_content)
                clarification_round = clarification_data.get("clarification_round", 1)
        except Exception as round_error:
            logger.warning(f"Could not extract clarification round: {round_error}")
            clarification_round = 1

        # Process the clarification response
        result = await chat_service.respond_to_clarification(
            project_id=project_id,
            user_id=user_id,
            clarification_id=request_id,
            responses=request.responses,
            clarification_round=clarification_round
        )

        # Convert to response model
        response = ClarificationResponse(
            clarification_processed=result["clarification_processed"],
            thread_id=result["thread_id"],
            is_now_complete=result["is_now_complete"],
            next_action=result["next_action"],
            additional_questions=result.get("additional_questions"),
            generation_triggered=result.get("generation_triggered"),
            job_id=result.get("job_id")
        )

        logger.info(f"Processed clarification response for request {request_id}: {result['next_action']}")
        return response

    except ChatValidationError as e:
        logger.warning(f"Chat validation error for clarification response: {e}")
        raise HTTPException(
            status_code=400,
            detail=ErrorResponse(
                error="ChatValidationError",
                message=str(e),
                details={"request_id": request_id, "field": getattr(e, 'field', None)}
            ).model_dump()
        )
    except ChatAccessDeniedError as e:
        logger.warning(f"Chat access denied for clarification response: {e}")
        raise HTTPException(
            status_code=403,
            detail=ErrorResponse(
                error="ChatAccessDenied",
                message=str(e),
                details={"request_id": request_id, "user_id": user_id}
            ).model_dump()
        )
    except ChatServiceError as e:
        logger.error(f"Chat service error processing clarification response: {e}")
        raise HTTPException(
            status_code=500,
            detail=ErrorResponse(
                error="ChatServiceError",
                message="Failed to process clarification response"
            ).model_dump()
        )
    except Exception as e:
        logger.error(f"Unexpected error processing clarification response: {e}")
        raise HTTPException(
            status_code=500,
            detail=ErrorResponse(
                error="InternalServerError",
                message="An unexpected error occurred while processing the response"
            ).model_dump()
        )