"""
Enhanced Chatbot API with Azure File Share Integration.

This module provides a complete chatbot experience that can:
1. Analyze user requests for infrastructure code generation
2. Ask clarification questions (max 2 rounds)
3. Generate infrastructure code (Terraform, etc.)
4. Automatically save generated files to Azure File Share with user isolation
5. Provide real-time updates via WebSocket
"""

from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Dict, Any, Optional, List
from pydantic import BaseModel, Field
from datetime import datetime
import uuid

from app.db.session import get_async_db
from app.middleware.supabase_auth import get_current_user, SupabaseUser
from app.services.chat.enhanced_autonomous_chat_service import EnhancedAutonomousChatService
from app.services.azure_file_service import get_azure_file_service
from app.services.websocket_manager import websocket_manager
from logconfig.logger import get_logger

logger = get_logger()
router = APIRouter(prefix="/enhanced-chatbot", tags=["Enhanced Chatbot"])


class ChatbotMessageRequest(BaseModel):
    """Request model for chatbot messages."""
    message: str = Field(..., description="User message or question")
    project_id: Optional[str] = Field(None, description="Project ID (will create if not provided)")
    project_name: Optional[str] = Field(None, description="Project name for new projects")
    cloud_provider: str = Field("AWS", description="Cloud provider (AWS, Azure, GCP)")
    priority: str = Field("normal", description="Message priority (low, normal, high, urgent)")
    enable_realtime: bool = Field(True, description="Enable real-time WebSocket updates")
    save_to_azure: bool = Field(True, description="Automatically save generated files to Azure File Share")
    conversation_mode: str = Field("auto", description="Conversation mode: auto, generation_only, chat_only")
    thread_id: Optional[str] = Field(None, description="Existing thread ID for continuing conversations")


class ChatbotMessageResponse(BaseModel):
    """Response model for chatbot messages."""
    success: bool
    thread_id: str
    message_id: str
    status: str
    next_action: str
    analysis: Optional[Dict[str, Any]] = None
    clarification_request: Optional[Dict[str, Any]] = None
    generation_info: Optional[Dict[str, Any]] = None
    azure_integration: bool = False
    websocket_events: List[str] = []
    estimated_completion: Optional[str] = None


class ClarificationResponse(BaseModel):
    """Response model for clarification questions."""
    responses: Dict[str, str] = Field(..., description="Question index -> Answer mapping")
    additional_context: Optional[str] = Field(None, description="Additional context or requirements")


class ChatbotStatusResponse(BaseModel):
    """Response model for chatbot status."""
    thread_id: str
    status: str
    current_round: Optional[int] = None
    max_rounds: Optional[int] = None
    last_activity: str
    pending_clarification: bool = False
    generation_active: bool = False
    azure_files_saved: List[str] = []
    azure_location: Optional[str] = None


class AzureFileInfo(BaseModel):
    """Model for Azure file information."""
    filename: str
    azure_path: str
    size: int
    content_preview: str
    saved_at: str


class ChatbotFilesResponse(BaseModel):
    """Response model for chatbot generated files."""
    success: bool
    files: List[AzureFileInfo]
    azure_location: str
    share_name: str
    total_files: int


@router.post("/chat", response_model=ChatbotMessageResponse)
async def send_chatbot_message(
    request: ChatbotMessageRequest,
    current_user: SupabaseUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_async_db)
):
    """
    Send a message to the enhanced chatbot.
    
    The chatbot will:
    1. Analyze your message for completeness
    2. Ask clarification questions if needed (max 2 rounds)
    3. Generate infrastructure code based on your requirements
    4. Automatically save generated files to Azure File Share
    5. Provide real-time updates via WebSocket
    """
    try:
        # Initialize enhanced chat service
        chat_service = EnhancedAutonomousChatService(db)
        
        # Create or use existing project
        project_id = request.project_id
        if not project_id:
            project_id = str(uuid.uuid4())
            logger.info(f"Created new project {project_id} for user {current_user.id}")
        
        # Process message with enhanced autonomous chat
        result = await chat_service.process_message_with_realtime(
            project_id=project_id,
            user_id=current_user.id,
            message_content=request.message,
            thread_id=request.thread_id,  # Use existing thread or create new
            cloud_provider=request.cloud_provider,
            conversation_mode=request.conversation_mode
        )
        
        # Determine WebSocket events to expect
        websocket_events = []
        
        if result["status"] == "conversational_response":
            websocket_events = ["bot_typing", "conversational_response"]
        elif result["status"] == "clarification_requested":
            websocket_events = ["analysis_started", "analysis_complete", "clarification_needed", "clarification_timeout"]
        elif result["status"] == "generation_started":
            websocket_events = [
                "analysis_started", "analysis_complete", "generation_started",
                "generation_progress", "saving_to_azure", "generation_completed", "azure_files_saved"
            ]
        else:
            websocket_events = ["analysis_started", "analysis_complete"]
        
        return ChatbotMessageResponse(
            success=True,
            thread_id=result["thread_id"],
            message_id=str(uuid.uuid4()),
            status=result["status"],
            next_action=result.get("next_action", "wait"),
            analysis=result.get("analysis"),
            clarification_request=result.get("clarification_request"),
            generation_info=result.get("generation_info"),
            azure_integration=request.save_to_azure,
            websocket_events=websocket_events,
            estimated_completion=result.get("estimated_completion")
        )
        
    except Exception as e:
        logger.error(f"Error processing chatbot message: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to process message: {str(e)}"
        )


@router.post("/clarifications/{clarification_id}/respond")
async def respond_to_clarification(
    clarification_id: str,
    response: ClarificationResponse,
    current_user: SupabaseUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_async_db)
):
    """
    Respond to clarification questions from the chatbot.
    
    After responding, the chatbot will either:
    1. Ask additional clarification questions (if this was round 1 of 2)
    2. Proceed with code generation and save files to Azure File Share
    """
    try:
        chat_service = EnhancedAutonomousChatService(db)
        
        # Process clarification response
        result = await chat_service.process_clarification_response_enhanced(
            project_id="",  # Will be extracted from clarification request
            user_id=current_user.id,
            clarification_id=clarification_id,
            responses=response.responses
        )
        
        return JSONResponse(content={
            "success": True,
            "clarification_processed": True,
            "thread_id": result["thread_id"],
            "status": result["status"],
            "next_action": result.get("next_action", "wait"),
            "generation_info": result.get("generation_info"),
            "azure_integration": True
        })
        
    except Exception as e:
        logger.error(f"Error processing clarification response: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to process clarification: {str(e)}"
        )


@router.get("/conversations/{thread_id}/status", response_model=ChatbotStatusResponse)
async def get_chatbot_status(
    thread_id: str,
    current_user: SupabaseUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_async_db)
):
    """
    Get the current status of a chatbot conversation.
    
    Returns information about:
    - Current conversation status
    - Pending clarifications
    - Generation progress
    - Azure File Share integration status
    """
    try:
        chat_service = EnhancedAutonomousChatService(db)
        
        # Find conversation in active conversations
        conversation = None
        for key, conv in chat_service.active_conversations.items():
            if conv.get("thread_id") == thread_id and conv.get("user_id") == current_user.id:
                conversation = conv
                break
        
        if not conversation:
            raise HTTPException(
                status_code=404,
                detail="Conversation not found or access denied"
            )
        
        # Get Azure file information if available
        azure_files_saved = []
        azure_location = None
        
        if conversation.get("azure_save_result"):
            save_result = conversation["azure_save_result"]
            azure_files_saved = save_result.saved_files
            azure_location = f"projects/{current_user.id}/{conversation['project_id']}/{conversation.get('generation_result', {}).get('generation_id', '')}/"
        
        return ChatbotStatusResponse(
            thread_id=thread_id,
            status=conversation.get("status", "unknown"),
            current_round=conversation.get("clarification_round", 0),
            max_rounds=chat_service.max_clarification_rounds,
            last_activity=conversation.get("last_activity", datetime.utcnow()).isoformat(),
            pending_clarification=bool(conversation.get("clarification_request")),
            generation_active=conversation.get("status") == "generating",
            azure_files_saved=azure_files_saved,
            azure_location=azure_location
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting chatbot status: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get status: {str(e)}"
        )


@router.get("/conversations/{thread_id}/files", response_model=ChatbotFilesResponse)
async def get_generated_files(
    thread_id: str,
    current_user: SupabaseUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_async_db)
):
    """
    Get information about files generated and saved to Azure File Share.
    
    Returns details about all files generated in this conversation,
    including their Azure File Share locations and content previews.
    """
    try:
        chat_service = EnhancedAutonomousChatService(db)
        azure_service = await get_azure_file_service()
        
        # Find conversation
        conversation = None
        for key, conv in chat_service.active_conversations.items():
            if conv.get("thread_id") == thread_id and conv.get("user_id") == current_user.id:
                conversation = conv
                break
        
        if not conversation:
            raise HTTPException(
                status_code=404,
                detail="Conversation not found or access denied"
            )
        
        # Get generation info
        generation_result = conversation.get("generation_result")
        if not generation_result:
            return ChatbotFilesResponse(
                success=True,
                files=[],
                azure_location="",
                share_name=azure_service.config.AZURE_FILE_SHARE_NAME,
                total_files=0
            )
        
        project_id = conversation["project_id"]
        generation_id = generation_result["generation_id"]
        
        # List files from Azure File Share
        azure_files = await azure_service.list_user_files(
            user_id=current_user.id,
            project_id=project_id,
            generation_id=generation_id
        )
        
        # Convert to response format
        file_infos = []
        for azure_file in azure_files:
            # Get content preview
            content = await azure_service.get_file_content(
                user_id=current_user.id,
                project_id=project_id,
                generation_id=generation_id,
                file_path=azure_file.relative_path
            )
            
            preview = content[:200] + "..." if content and len(content) > 200 else content or ""
            
            file_infos.append(AzureFileInfo(
                filename=azure_file.name,
                azure_path=azure_file.path,
                size=azure_file.size,
                content_preview=preview,
                saved_at=azure_file.modified_date.isoformat()
            ))
        
        azure_location = f"projects/{current_user.id}/{project_id}/{generation_id}/"
        
        return ChatbotFilesResponse(
            success=True,
            files=file_infos,
            azure_location=azure_location,
            share_name=azure_service.config.AZURE_FILE_SHARE_NAME,
            total_files=len(file_infos)
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting generated files: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get files: {str(e)}"
        )


@router.delete("/conversations/{thread_id}")
async def cancel_chatbot_conversation(
    thread_id: str,
    current_user: SupabaseUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_async_db)
):
    """
    Cancel an active chatbot conversation.
    
    This will stop any ongoing generation and clean up resources.
    Generated files that were already saved to Azure File Share will remain.
    """
    try:
        chat_service = EnhancedAutonomousChatService(db)
        
        # Find and remove conversation
        conversation_key = None
        for key, conv in chat_service.active_conversations.items():
            if conv.get("thread_id") == thread_id and conv.get("user_id") == current_user.id:
                conversation_key = key
                break
        
        if conversation_key:
            conversation = chat_service.active_conversations[conversation_key]
            
            # Notify user of cancellation
            await websocket_manager.send_to_user(current_user.id, {
                "type": "conversation_cancelled",
                "thread_id": thread_id,
                "message": "Conversation cancelled by user",
                "timestamp": datetime.utcnow().isoformat()
            })
            
            # Clean up
            del chat_service.active_conversations[conversation_key]
            
            # Clean up any active clarifications
            for clarif_id, clarif in list(chat_service.active_clarifications.items()):
                if clarif.thread_id == thread_id:
                    del chat_service.active_clarifications[clarif_id]
        
        return JSONResponse(content={
            "success": True,
            "message": "Conversation cancelled successfully",
            "thread_id": thread_id
        })
        
    except Exception as e:
        logger.error(f"Error cancelling conversation: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to cancel conversation: {str(e)}"
        )


@router.get("/azure/files")
async def list_user_azure_files(
    project_id: Optional[str] = None,
    current_user: SupabaseUser = Depends(get_current_user)
):
    """
    List all files saved to Azure File Share for the current user.
    
    Optionally filter by project_id to see files for a specific project.
    """
    try:
        azure_service = await get_azure_file_service()
        
        # List user files
        azure_files = await azure_service.list_user_files(
            user_id=current_user.id,
            project_id=project_id
        )
        
        # Group by project and generation
        projects = {}
        for azure_file in azure_files:
            proj_id = azure_file.project_id
            gen_id = azure_file.generation_id or "unknown"
            
            if proj_id not in projects:
                projects[proj_id] = {}
            
            if gen_id not in projects[proj_id]:
                projects[proj_id][gen_id] = []
            
            projects[proj_id][gen_id].append({
                "filename": azure_file.name,
                "path": azure_file.path,
                "size": azure_file.size,
                "modified_date": azure_file.modified_date.isoformat(),
                "relative_path": azure_file.relative_path
            })
        
        return JSONResponse(content={
            "success": True,
            "user_id": current_user.id,
            "share_name": azure_service.config.AZURE_FILE_SHARE_NAME,
            "projects": projects,
            "total_files": len(azure_files)
        })
        
    except Exception as e:
        logger.error(f"Error listing Azure files: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to list files: {str(e)}"
        )


@router.get("/conversations/{thread_id}/history")
async def get_conversation_history(
    thread_id: str,
    limit: int = 50,
    current_user: SupabaseUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_async_db)
):
    """
    Get the conversation history for a thread.
    
    Returns the message history for continuing conversations.
    """
    try:
        chat_service = EnhancedAutonomousChatService(db)
        
        # Find conversation
        conversation = None
        for key, conv in chat_service.active_conversations.items():
            if conv.get("thread_id") == thread_id and conv.get("user_id") == current_user.id:
                conversation = conv
                break
        
        if not conversation:
            raise HTTPException(
                status_code=404,
                detail="Conversation not found or access denied"
            )
        
        # Get conversation history
        history = conversation.get("conversation_history", [])
        
        # Limit results
        if limit > 0:
            history = history[-limit:]
        
        return JSONResponse(content={
            "success": True,
            "thread_id": thread_id,
            "history": [
                {
                    "role": msg["role"],
                    "content": msg["content"],
                    "timestamp": msg["timestamp"].isoformat() if isinstance(msg["timestamp"], datetime) else msg["timestamp"],
                    "response_type": msg.get("response_type", "message")
                }
                for msg in history
            ],
            "total_messages": len(history)
        })
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting conversation history: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get conversation history: {str(e)}"
        )


@router.post("/conversations/{thread_id}/continue")
async def continue_conversation(
    thread_id: str,
    request: ChatbotMessageRequest,
    current_user: SupabaseUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_async_db)
):
    """
    Continue an existing conversation thread.
    
    This endpoint is optimized for multi-turn conversations and maintains context.
    """
    try:
        chat_service = EnhancedAutonomousChatService(db)
        
        # Process message in conversational context
        result = await chat_service.process_message_with_realtime(
            project_id=request.project_id or "default",
            user_id=current_user.id,
            message_content=request.message,
            thread_id=thread_id,
            cloud_provider=request.cloud_provider,
            conversation_mode=request.conversation_mode
        )
        
        return ChatbotMessageResponse(
            success=True,
            thread_id=result["thread_id"],
            message_id=str(uuid.uuid4()),
            status=result["status"],
            next_action=result.get("next_action", "continue_conversation"),
            analysis=result.get("analysis"),
            clarification_request=result.get("clarification_request"),
            generation_info=result.get("generation_info"),
            azure_integration=request.save_to_azure,
            websocket_events=["bot_typing", "conversational_response"] if result["status"] == "conversational_response" else [],
            estimated_completion=result.get("estimated_completion")
        )
        
    except Exception as e:
        logger.error(f"Error continuing conversation: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to continue conversation: {str(e)}"
        )


@router.get("/azure/files/{project_id}/{generation_id}/{file_path:path}")
async def get_azure_file_content(
    project_id: str,
    generation_id: str,
    file_path: str,
    current_user: SupabaseUser = Depends(get_current_user)
):
    """
    Get the content of a specific file from Azure File Share.
    
    Returns the full content of the file for viewing or downloading.
    """
    try:
        azure_service = await get_azure_file_service()
        
        # Get file content
        content = await azure_service.get_file_content(
            user_id=current_user.id,
            project_id=project_id,
            generation_id=generation_id,
            file_path=file_path
        )
        
        if content is None:
            raise HTTPException(
                status_code=404,
                detail="File not found or access denied"
            )
        
        return JSONResponse(content={
            "success": True,
            "file_path": file_path,
            "project_id": project_id,
            "generation_id": generation_id,
            "content": content,
            "size": len(content)
        })
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting file content: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get file content: {str(e)}"
        )