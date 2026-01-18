"""
Enhanced Autonomous Chat API with Real-time Capabilities.

This module provides enhanced REST endpoints for autonomous chat with:
- Real-time WebSocket integration
- Maximum 2 clarification rounds
- Streaming responses
- Enhanced error handling
"""

import asyncio
import uuid
from datetime import datetime
from typing import List, Optional, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, Query, Path, Body, BackgroundTasks
from pydantic import BaseModel, Field, ConfigDict
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_async_db
from app.middleware.supabase_auth import get_current_user_id
from app.services.chat.enhanced_autonomous_chat_service import EnhancedAutonomousChatService
from app.services.chat_service import ChatService, ChatServiceError, ChatAccessDeniedError, ChatValidationError
from app.services.websocket_manager import websocket_manager
from app.models.chat import MessageType
from logconfig.logger import get_logger

logger = get_logger()
router = APIRouter(prefix="/enhanced-chat", tags=["enhanced-autonomous-chat"])


# Enhanced Request/Response Models
class EnhancedAutonomousMessageRequest(BaseModel):
    """Enhanced request model for autonomous chat messages."""

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "project_id": "550e8400-e29b-41d4-a716-446655440001",
                "message_content": "Create an S3 bucket with versioning and encryption enabled",
                "thread_id": "550e8400-e29b-41d4-a716-446655440002",
                "cloud_provider": "AWS",
                "enable_realtime": True,
                "priority": "normal"
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
    enable_realtime: bool = Field(
        default=True,
        description="Enable real-time WebSocket updates"
    )
    priority: str = Field(
        default="normal",
        description="Message priority (low, normal, high, urgent)"
    )


class EnhancedAutonomousMessageResponse(BaseModel):
    """Enhanced response model for autonomous chat messages."""

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "thread_id": "550e8400-e29b-41d4-a716-446655440002",
                "message_id": "550e8400-e29b-41d4-a716-446655440003",
                "status": "processing",
                "analysis": {
                    "is_complete": False,
                    "confidence_score": 0.65,
                    "complexity_score": 0.7,
                    "estimated_time": 90
                },
                "next_action": "clarification_requested",
                "clarification_request": {
                    "id": "550e8400-e29b-41d4-a716-446655440004",
                    "questions": ["What instance type do you need?"],
                    "round": 1,
                    "max_rounds": 2,
                    "timeout_seconds": 300
                },
                "realtime_enabled": True,
                "websocket_events": ["analysis_started", "clarification_needed"]
            }
        }
    )

    thread_id: str = Field(..., description="Conversation thread ID")
    message_id: str = Field(..., description="Saved message ID")
    status: str = Field(..., description="Processing status")
    analysis: Dict[str, Any] = Field(..., description="Enhanced prompt analysis results")
    next_action: str = Field(..., description="Next action in the flow")
    clarification_request: Optional[Dict[str, Any]] = Field(None, description="Clarification request if needed")
    generation_info: Optional[Dict[str, Any]] = Field(None, description="Generation information if triggered")
    realtime_enabled: bool = Field(default=True, description="Whether real-time updates are enabled")
    websocket_events: List[str] = Field(default_factory=list, description="Expected WebSocket event types")
    estimated_completion: Optional[str] = Field(None, description="Estimated completion time")


class EnhancedClarificationResponseRequest(BaseModel):
    """Enhanced request model for responding to clarification requests."""

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "responses": {
                    "0": "t3.medium",
                    "1": "us-east-1"
                },
                "additional_context": "This is for a development environment"
            }
        }
    )

    responses: Dict[str, str] = Field(
        ...,
        description="Dictionary mapping question indices to user answers"
    )
    additional_context: Optional[str] = Field(
        None,
        description="Additional context or clarifications from user"
    )


class EnhancedClarificationResponse(BaseModel):
    """Enhanced response model for clarification processing."""

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "clarification_processed": True,
                "thread_id": "550e8400-e29b-41d4-a716-446655440002",
                "round_completed": 1,
                "is_now_complete": True,
                "next_action": "generation_started",
                "generation_info": {
                    "job_id": "550e8400-e29b-41d4-a716-446655440004",
                    "estimated_time": 60
                },
                "realtime_updates": True
            }
        }
    )

    clarification_processed: bool = Field(..., description="Whether clarification was processed")
    thread_id: str = Field(..., description="Conversation thread ID")
    round_completed: int = Field(..., description="Clarification round that was completed")
    is_now_complete: bool = Field(..., description="Whether prompt is now complete")
    next_action: str = Field(..., description="Next action to take")
    additional_questions: Optional[List[str]] = Field(None, description="Additional questions if still needed")
    generation_info: Optional[Dict[str, Any]] = Field(None, description="Generation information if triggered")
    realtime_updates: bool = Field(default=True, description="Whether real-time updates are active")


class ConversationStatusResponse(BaseModel):
    """Response model for conversation status."""

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "thread_id": "550e8400-e29b-41d4-a716-446655440002",
                "status": "active",
                "current_round": 1,
                "max_rounds": 2,
                "last_activity": "2024-01-15T10:35:00Z",
                "pending_clarification": True,
                "generation_active": False
            }
        }
    )

    thread_id: str = Field(..., description="Conversation thread ID")
    status: str = Field(..., description="Conversation status")
    current_round: int = Field(..., description="Current clarification round")
    max_rounds: int = Field(..., description="Maximum clarification rounds")
    last_activity: datetime = Field(..., description="Last activity timestamp")
    pending_clarification: bool = Field(..., description="Whether clarification is pending")
    generation_active: bool = Field(..., description="Whether code generation is active")


# Dependency to get enhanced chat service
async def get_enhanced_chat_service(db: AsyncSession = Depends(get_async_db)) -> EnhancedAutonomousChatService:
    """Get enhanced autonomous chat service with database session."""
    return EnhancedAutonomousChatService(db)


async def get_chat_service(db: AsyncSession = Depends(get_async_db)) -> ChatService:
    """Get regular chat service with database session."""
    return ChatService(db)


@router.post(
    "/projects/{project_id}/messages",
    response_model=EnhancedAutonomousMessageResponse,
    summary="Send enhanced autonomous chat message",
    description="""
    Send a message through the enhanced autonomous chat system with real-time capabilities.
    
    Features:
    - Real-time WebSocket updates throughout the process
    - Maximum 2 clarification rounds with intelligent timeout handling
    - Enhanced prompt analysis with complexity scoring
    - Automatic generation trigger after clarification rounds
    - Streaming progress updates during code generation
    
    The system will:
    1. Analyze your prompt for completeness and complexity
    2. Request clarification if needed (max 2 rounds)
    3. Automatically proceed with generation after clarification rounds
    4. Provide real-time updates via WebSocket throughout the process
    """,
    responses={
        200: {"description": "Message processed successfully with real-time flow initiated"},
        400: {"description": "Invalid message data"},
        401: {"description": "Authentication required"},
        403: {"description": "Access denied - user lacks project access"},
        404: {"description": "Project not found"},
        500: {"description": "Internal server error"}
    }
)
async def send_enhanced_autonomous_message(
    background_tasks: BackgroundTasks,
    project_id: str = Path(..., description="Project ID (UUID)"),
    request: EnhancedAutonomousMessageRequest = Body(...),
    user_id: str = Depends(get_current_user_id),
    enhanced_service: EnhancedAutonomousChatService = Depends(get_enhanced_chat_service),
    chat_service: ChatService = Depends(get_chat_service),
    db: AsyncSession = Depends(get_async_db)
) -> EnhancedAutonomousMessageResponse:
    """
    Send a message through the enhanced autonomous chat system.
    
    Args:
        project_id: Project ID to send message for
        request: Enhanced message data
        background_tasks: Background tasks for async processing
        user_id: Supabase user ID from JWT token
        enhanced_service: Enhanced autonomous chat service instance
        chat_service: Regular chat service instance
        db: Database session
        
    Returns:
        EnhancedAutonomousMessageResponse with processing details and real-time info
        
    Raises:
        HTTPException: If operation fails
    """
    try:
        # Validate project access first
        await chat_service._validate_project_access(project_id, user_id)
        
        # Save the user message
        saved_message = await chat_service.save_message(
            project_id=project_id,
            user_id=user_id,
            message_content=request.message_content,
            message_type=MessageType.USER
        )
        
        # Process with enhanced autonomous service
        if request.enable_realtime:
            # Process with real-time capabilities
            background_tasks.add_task(
                _process_enhanced_message_async,
                enhanced_service,
                project_id,
                user_id,
                request.message_content,
                request.thread_id,
                request.cloud_provider,
                saved_message.id
            )
            
            # Return immediate response with processing info
            return EnhancedAutonomousMessageResponse(
                thread_id=request.thread_id or "pending",
                message_id=saved_message.id,
                status="processing",
                analysis={"status": "analyzing"},
                next_action="analysis_in_progress",
                realtime_enabled=True,
                websocket_events=["analysis_started", "analysis_complete", "clarification_needed", "generation_started"],
                estimated_completion="Processing will complete within 5 minutes"
            )
        else:
            # Process synchronously (fallback mode)
            result = await enhanced_service.process_message_with_realtime(
                project_id=project_id,
                user_id=user_id,
                message_content=request.message_content,
                thread_id=request.thread_id,
                cloud_provider=request.cloud_provider
            )
            
            return EnhancedAutonomousMessageResponse(
                thread_id=result["thread_id"],
                message_id=saved_message.id,
                status=result.get("status", "completed"),
                analysis=result.get("analysis", {}),
                next_action=result.get("next_action", "completed"),
                clarification_request=result.get("clarification_request"),
                generation_info=result.get("generation_info"),
                realtime_enabled=False,
                websocket_events=[]
            )
        
    except (ChatValidationError, ChatAccessDeniedError) as e:
        logger.warning(f"Enhanced chat validation/access error for project {project_id}, user {user_id}: {e}")
        raise HTTPException(status_code=400 if isinstance(e, ChatValidationError) else 403, detail=str(e))
    except Exception as e:
        logger.error(f"Enhanced chat error for project {project_id}, user {user_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to process enhanced autonomous message")


@router.post(
    "/clarifications/{clarification_id}/respond",
    response_model=EnhancedClarificationResponse,
    summary="Respond to enhanced clarification request",
    description="""
    Respond to a clarification request in the enhanced autonomous chat system.
    
    Features:
    - Real-time processing of clarification responses
    - Automatic progression through clarification rounds (max 2)
    - Intelligent decision making on when to proceed with generation
    - Enhanced prompt enrichment with user responses
    
    The system will:
    1. Process your clarification responses
    2. Re-analyze the enriched prompt
    3. Either request additional clarification (if round < 2) or proceed with generation
    4. Provide real-time updates throughout the process
    """,
    responses={
        200: {"description": "Clarification response processed successfully"},
        400: {"description": "Invalid clarification response"},
        401: {"description": "Authentication required"},
        404: {"description": "Clarification request not found"},
        500: {"description": "Internal server error"}
    }
)
async def respond_to_enhanced_clarification(
    clarification_id: str = Path(..., description="Clarification request ID"),
    request: EnhancedClarificationResponseRequest = Body(...),
    user_id: str = Depends(get_current_user_id),
    enhanced_service: EnhancedAutonomousChatService = Depends(get_enhanced_chat_service)
) -> EnhancedClarificationResponse:
    """
    Respond to a clarification request with enhanced processing.
    
    Args:
        clarification_id: ID of the clarification request
        request: Clarification response data
        user_id: Supabase user ID from JWT token
        enhanced_service: Enhanced autonomous chat service instance
        
    Returns:
        EnhancedClarificationResponse with processing results
        
    Raises:
        HTTPException: If operation fails
    """
    try:
        # Find project_id from clarification (this is a simplified approach)
        # In a real implementation, you'd look up the clarification request
        project_id = "temp"  # This should be retrieved from the clarification request
        
        # Process the clarification response
        result = await enhanced_service.process_clarification_response_enhanced(
            project_id=project_id,
            user_id=user_id,
            clarification_id=clarification_id,
            responses=request.responses
        )
        
        return EnhancedClarificationResponse(
            clarification_processed=True,
            thread_id=result["thread_id"],
            round_completed=result.get("round_completed", 1),
            is_now_complete=result.get("is_now_complete", False),
            next_action=result.get("next_action", "unknown"),
            additional_questions=result.get("additional_questions"),
            generation_info=result.get("generation_info"),
            realtime_updates=True
        )
        
    except Exception as e:
        logger.error(f"Enhanced clarification response error for clarification {clarification_id}, user {user_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to process enhanced clarification response")


@router.get(
    "/conversations/{thread_id}/status",
    response_model=ConversationStatusResponse,
    summary="Get enhanced conversation status",
    description="""
    Get the current status of an enhanced autonomous chat conversation.
    
    Provides information about:
    - Current clarification round and limits
    - Pending clarification requests
    - Active generation processes
    - Last activity timestamp
    - Overall conversation status
    """,
    responses={
        200: {"description": "Conversation status retrieved successfully"},
        401: {"description": "Authentication required"},
        404: {"description": "Conversation not found"},
        500: {"description": "Internal server error"}
    }
)
async def get_enhanced_conversation_status(
    thread_id: str = Path(..., description="Conversation thread ID"),
    user_id: str = Depends(get_current_user_id),
    enhanced_service: EnhancedAutonomousChatService = Depends(get_enhanced_chat_service)
) -> ConversationStatusResponse:
    """
    Get the status of an enhanced conversation.
    
    Args:
        thread_id: Conversation thread ID
        user_id: Supabase user ID from JWT token
        enhanced_service: Enhanced autonomous chat service instance
        
    Returns:
        ConversationStatusResponse with conversation status
        
    Raises:
        HTTPException: If operation fails
    """
    try:
        # Find conversation in active conversations
        conversation_key = f"{thread_id}_{user_id}"
        
        if conversation_key in enhanced_service.active_conversations:
            conversation = enhanced_service.active_conversations[conversation_key]
            
            return ConversationStatusResponse(
                thread_id=thread_id,
                status=conversation.get("status", "active"),
                current_round=conversation.get("clarification_round", 0),
                max_rounds=enhanced_service.max_clarification_rounds,
                last_activity=conversation.get("last_activity", datetime.utcnow()),
                pending_clarification=bool(conversation.get("clarification_request")),
                generation_active=conversation.get("generation_triggered", False)
            )
        else:
            # Conversation not found in active conversations
            return ConversationStatusResponse(
                thread_id=thread_id,
                status="inactive",
                current_round=0,
                max_rounds=enhanced_service.max_clarification_rounds,
                last_activity=datetime.utcnow(),
                pending_clarification=False,
                generation_active=False
            )
        
    except Exception as e:
        logger.error(f"Enhanced conversation status error for thread {thread_id}, user {user_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to get enhanced conversation status")


@router.delete(
    "/conversations/{thread_id}",
    summary="Cancel enhanced conversation",
    description="""
    Cancel an active enhanced autonomous chat conversation.
    
    This will:
    - Stop any pending clarification requests
    - Cancel active generation processes
    - Clean up conversation state
    - Send cancellation notifications via WebSocket
    """,
    responses={
        200: {"description": "Conversation cancelled successfully"},
        401: {"description": "Authentication required"},
        404: {"description": "Conversation not found"},
        500: {"description": "Internal server error"}
    }
)
async def cancel_enhanced_conversation(
    thread_id: str = Path(..., description="Conversation thread ID"),
    user_id: str = Depends(get_current_user_id),
    enhanced_service: EnhancedAutonomousChatService = Depends(get_enhanced_chat_service)
) -> Dict[str, Any]:
    """
    Cancel an enhanced conversation.
    
    Args:
        thread_id: Conversation thread ID
        user_id: Supabase user ID from JWT token
        enhanced_service: Enhanced autonomous chat service instance
        
    Returns:
        Dict with cancellation confirmation
        
    Raises:
        HTTPException: If operation fails
    """
    try:
        conversation_key = f"{thread_id}_{user_id}"
        
        if conversation_key in enhanced_service.active_conversations:
            # Clean up conversation
            enhanced_service.cleanup_conversation(conversation_key)
            
            # Send cancellation notification
            await websocket_manager.send_to_user(user_id, {
                "type": "conversation_cancelled",
                "thread_id": thread_id,
                "message": "Conversation has been cancelled.",
                "timestamp": datetime.utcnow().isoformat()
            })
            
            return {
                "success": True,
                "message": "Enhanced conversation cancelled successfully",
                "thread_id": thread_id,
                "timestamp": datetime.utcnow().isoformat()
            }
        else:
            raise HTTPException(status_code=404, detail="Conversation not found")
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Enhanced conversation cancellation error for thread {thread_id}, user {user_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to cancel enhanced conversation")


# Background task function
async def _process_enhanced_message_async(
    enhanced_service: EnhancedAutonomousChatService,
    project_id: str,
    user_id: str,
    message_content: str,
    thread_id: Optional[str],
    cloud_provider: str,
    message_id: str
) -> None:
    """
    Background task to process enhanced autonomous message.
    
    Args:
        enhanced_service: Enhanced autonomous chat service instance
        project_id: Project ID
        user_id: User ID
        message_content: Message content
        thread_id: Optional thread ID
        cloud_provider: Cloud provider
        message_id: Saved message ID
    """
    try:
        result = await enhanced_service.process_message_with_realtime(
            project_id=project_id,
            user_id=user_id,
            message_content=message_content,
            thread_id=thread_id,
            cloud_provider=cloud_provider
        )
        
        # Send completion notification
        await websocket_manager.send_to_user(user_id, {
            "type": "message_processing_complete",
            "thread_id": result["thread_id"],
            "message_id": message_id,
            "result": result,
            "timestamp": datetime.utcnow().isoformat()
        })
        
        logger.info(f"Enhanced message processing completed for user {user_id}, thread {result['thread_id']}")
        
    except Exception as e:
        logger.error(f"Enhanced message processing failed for user {user_id}: {e}")
        
        # Send error notification
        await websocket_manager.send_to_user(user_id, {
            "type": "message_processing_error",
            "message_id": message_id,
            "error": str(e),
            "timestamp": datetime.utcnow().isoformat()
        })


# WebSocket event handlers (these would be called by the WebSocket manager)
async def handle_enhanced_chat_events():
    """Handle enhanced chat WebSocket events."""
    # This is a placeholder for WebSocket event handling
    # In a real implementation, this would be integrated with the WebSocket manager
    pass