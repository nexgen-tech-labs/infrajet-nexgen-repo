"""
Enhanced WebSocket routes for real-time autonomous chat.

This module provides WebSocket endpoints specifically designed for
enhanced autonomous chat with real-time updates, clarification handling,
and generation progress monitoring.
"""

import json
import logging
from typing import Optional, Dict, Any

from fastapi import (
    APIRouter,
    WebSocket,
    WebSocketDisconnect,
    Query,
    Depends,
    HTTPException,
)

from app.services.websocket_manager import websocket_manager
from app.services.chat.enhanced_autonomous_chat_service import EnhancedAutonomousChatService
from app.db.session import get_async_db
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)
router = APIRouter()


@router.websocket("/ws/enhanced-chat")
async def enhanced_chat_websocket_endpoint(
    websocket: WebSocket,
    token: Optional[str] = Query(None, description="Supabase JWT access token"),
):
    """
    Enhanced WebSocket endpoint for real-time autonomous chat.

    Query Parameters:
        token: Supabase JWT access token for authentication

    WebSocket Message Format:
        {
            "action": "subscribe_thread|submit_clarification|cancel_generation|heartbeat",
            "data": {
                "thread_id": "optional",
                "clarification_id": "optional",
                "responses": {"0": "answer1", "1": "answer2"}
            }
        }

    Real-time Events Sent:
        - analysis_started: When prompt analysis begins
        - analysis_complete: When prompt analysis finishes
        - clarification_needed: When clarification is requested
        - clarification_timeout: When clarification times out
        - generation_started: When code generation begins
        - generation_progress: Progress updates during generation
        - generation_complete: When generation finishes
        - error: When errors occur
    """
    session_id = None

    try:
        # Authenticate user
        if not token:
            await websocket.close(code=4001, reason="Authentication token required")
            return

        user_id = await websocket_manager.authenticate_websocket(websocket, token)
        if not user_id:
            await websocket.close(code=4001, reason="Invalid authentication token")
            return

        # Connect WebSocket with enhanced chat metadata
        session_id = await websocket_manager.connect(
            websocket, 
            user_id,
            metadata={"connection_type": "enhanced_chat", "features": ["realtime_analysis", "clarification_flow"]}
        )

        # Send welcome message with enhanced chat capabilities
        await websocket_manager.send_to_session(session_id, {
            "event_type": "enhanced_chat_connected",
            "timestamp": "2024-01-15T10:30:00Z",
            "data": {
                "session_id": session_id,
                "features": [
                    "real_time_analysis",
                    "clarification_flow",
                    "generation_progress",
                    "max_2_clarification_rounds"
                ],
                "max_clarification_rounds": 2,
                "default_timeout": 300
            }
        })

        # Handle incoming messages
        while True:
            try:
                # Receive message from client
                data = await websocket.receive_text()
                message = json.loads(data)

                action = message.get("action")
                message_data = message.get("data", {})

                # Handle different enhanced chat actions
                if action == "subscribe_thread":
                    thread_id = message_data.get("thread_id")
                    if thread_id:
                        await websocket_manager.subscribe_to_conversation(session_id, thread_id)
                        await websocket_manager.send_to_session(session_id, {
                            "event_type": "thread_subscribed",
                            "timestamp": "2024-01-15T10:30:00Z",
                            "data": {
                                "thread_id": thread_id,
                                "message": f"Subscribed to enhanced chat thread {thread_id}"
                            }
                        })
                        logger.info(f"Enhanced chat session {session_id} subscribed to thread {thread_id}")
                    else:
                        await websocket_manager.send_to_session(session_id, {
                            "event_type": "error",
                            "data": {"message": "thread_id required for thread subscription"}
                        })

                elif action == "submit_clarification":
                    await _handle_clarification_submission(
                        session_id, message_data, user_id
                    )

                elif action == "cancel_generation":
                    await _handle_generation_cancellation(
                        session_id, message_data, user_id
                    )

                elif action == "get_thread_status":
                    await _handle_thread_status_request(
                        session_id, message_data, user_id
                    )

                elif action == "heartbeat":
                    await websocket_manager.handle_heartbeat(session_id)

                elif action == "request_analysis_details":
                    await _handle_analysis_details_request(
                        session_id, message_data, user_id
                    )

                else:
                    await websocket_manager.send_to_session(session_id, {
                        "event_type": "error",
                        "data": {"message": f"Unknown enhanced chat action: {action}"}
                    })

            except WebSocketDisconnect:
                logger.info(f"Enhanced chat WebSocket disconnected during message handling: session_id={session_id}")
                break
            except json.JSONDecodeError:
                await websocket_manager.send_to_session(session_id, {
                    "event_type": "error",
                    "data": {"message": "Invalid JSON format"}
                })
            except Exception as e:
                logger.error(f"Error handling enhanced chat WebSocket message: {str(e)}")
                await websocket_manager.send_to_session(session_id, {
                    "event_type": "error",
                    "data": {"message": "Internal server error processing message"}
                })

    except WebSocketDisconnect:
        logger.info(f"Enhanced chat WebSocket disconnected: session_id={session_id}")
    except Exception as e:
        logger.error(f"Enhanced chat WebSocket error: {str(e)}")
    finally:
        if session_id:
            await websocket_manager.disconnect(session_id)


@router.websocket("/ws/enhanced-chat/thread/{thread_id}")
async def enhanced_chat_thread_websocket_endpoint(
    websocket: WebSocket,
    thread_id: str,
    token: Optional[str] = Query(None, description="Supabase JWT access token"),
):
    """
    Enhanced WebSocket endpoint for specific thread real-time updates.

    Path Parameters:
        thread_id: Conversation thread ID to subscribe to

    Query Parameters:
        token: Supabase JWT access token for authentication

    This endpoint automatically subscribes to the specified thread and provides
    real-time updates for that conversation only.
    """
    session_id = None

    try:
        # Authenticate user
        if not token:
            await websocket.close(code=4001, reason="Authentication token required")
            return

        user_id = await websocket_manager.authenticate_websocket(websocket, token)
        if not user_id:
            await websocket.close(code=4001, reason="Invalid authentication token")
            return

        # Connect WebSocket with thread-specific metadata
        session_id = await websocket_manager.connect(
            websocket, 
            user_id,
            metadata={
                "connection_type": "enhanced_chat_thread",
                "auto_subscribed_thread": thread_id,
                "thread_specific": True
            }
        )

        # Auto-subscribe to the thread
        await websocket_manager.subscribe_to_conversation(session_id, thread_id)

        # Send thread connection confirmation
        await websocket_manager.send_to_session(session_id, {
            "event_type": "thread_connected",
            "timestamp": "2024-01-15T10:30:00Z",
            "data": {
                "thread_id": thread_id,
                "session_id": session_id,
                "message": f"Connected to enhanced chat thread {thread_id}",
                "auto_subscribed": True
            }
        })

        # Handle incoming messages (mainly for clarification responses and status requests)
        while True:
            try:
                data = await websocket.receive_text()
                message = json.loads(data)

                action = message.get("action")
                message_data = message.get("data", {})

                if action == "submit_clarification":
                    # Ensure thread_id matches
                    message_data["thread_id"] = thread_id
                    await _handle_clarification_submission(
                        session_id, message_data, user_id
                    )

                elif action == "cancel_generation":
                    message_data["thread_id"] = thread_id
                    await _handle_generation_cancellation(
                        session_id, message_data, user_id
                    )

                elif action == "get_status":
                    message_data["thread_id"] = thread_id
                    await _handle_thread_status_request(
                        session_id, message_data, user_id
                    )

                elif action == "heartbeat":
                    await websocket_manager.handle_heartbeat(session_id)

                else:
                    await websocket_manager.send_to_session(session_id, {
                        "event_type": "info",
                        "data": {
                            "message": f"Thread-specific endpoint. Available actions: submit_clarification, cancel_generation, get_status, heartbeat"
                        }
                    })

            except WebSocketDisconnect:
                logger.info(f"Enhanced chat thread WebSocket disconnected: session_id={session_id}, thread_id={thread_id}")
                break
            except json.JSONDecodeError:
                await websocket_manager.send_to_session(session_id, {
                    "event_type": "error",
                    "data": {"message": "Invalid JSON format"}
                })
            except Exception as e:
                logger.error(f"Error handling enhanced chat thread WebSocket message: {str(e)}")

    except WebSocketDisconnect:
        logger.info(f"Enhanced chat thread WebSocket disconnected: session_id={session_id}, thread_id={thread_id}")
    except Exception as e:
        logger.error(f"Enhanced chat thread WebSocket error: {str(e)}")
    finally:
        if session_id:
            await websocket_manager.disconnect(session_id)


# Helper functions for handling WebSocket actions
async def _handle_clarification_submission(
    session_id: str,
    message_data: Dict[str, Any],
    user_id: str
) -> None:
    """Handle clarification response submission via WebSocket."""
    try:
        clarification_id = message_data.get("clarification_id")
        responses = message_data.get("responses", {})
        thread_id = message_data.get("thread_id")

        if not clarification_id or not responses:
            await websocket_manager.send_to_session(session_id, {
                "event_type": "error",
                "data": {"message": "clarification_id and responses required"}
            })
            return

        # Submit clarification response through WebSocket manager
        success = await websocket_manager.submit_clarification_response(
            clarification_id, user_id, json.dumps(responses)
        )

        if success:
            await websocket_manager.send_to_session(session_id, {
                "event_type": "clarification_submitted",
                "timestamp": "2024-01-15T10:30:00Z",
                "data": {
                    "clarification_id": clarification_id,
                    "thread_id": thread_id,
                    "message": "Clarification response submitted successfully",
                    "processing": True
                }
            })
            logger.info(f"Clarification response submitted via WebSocket: {clarification_id}")
        else:
            await websocket_manager.send_to_session(session_id, {
                "event_type": "error",
                "data": {"message": "Failed to submit clarification response"}
            })

    except Exception as e:
        logger.error(f"Error handling clarification submission: {e}")
        await websocket_manager.send_to_session(session_id, {
            "event_type": "error",
            "data": {"message": "Error processing clarification submission"}
        })


async def _handle_generation_cancellation(
    session_id: str,
    message_data: Dict[str, Any],
    user_id: str
) -> None:
    """Handle generation cancellation via WebSocket."""
    try:
        thread_id = message_data.get("thread_id")
        generation_id = message_data.get("generation_id")

        if not thread_id:
            await websocket_manager.send_to_session(session_id, {
                "event_type": "error",
                "data": {"message": "thread_id required for generation cancellation"}
            })
            return

        # Send cancellation notification to thread subscribers
        await websocket_manager.broadcast_to_conversation(thread_id, {
            "event_type": "generation_cancelled",
            "timestamp": "2024-01-15T10:30:00Z",
            "data": {
                "thread_id": thread_id,
                "generation_id": generation_id,
                "cancelled_by": user_id,
                "message": "Code generation has been cancelled"
            }
        })

        await websocket_manager.send_to_session(session_id, {
            "event_type": "cancellation_confirmed",
            "timestamp": "2024-01-15T10:30:00Z",
            "data": {
                "thread_id": thread_id,
                "message": "Generation cancellation request processed"
            }
        })

        logger.info(f"Generation cancellation requested via WebSocket: thread_id={thread_id}, user_id={user_id}")

    except Exception as e:
        logger.error(f"Error handling generation cancellation: {e}")
        await websocket_manager.send_to_session(session_id, {
            "event_type": "error",
            "data": {"message": "Error processing generation cancellation"}
        })


async def _handle_thread_status_request(
    session_id: str,
    message_data: Dict[str, Any],
    user_id: str
) -> None:
    """Handle thread status request via WebSocket."""
    try:
        thread_id = message_data.get("thread_id")

        if not thread_id:
            await websocket_manager.send_to_session(session_id, {
                "event_type": "error",
                "data": {"message": "thread_id required for status request"}
            })
            return

        # Get thread status (this would integrate with the enhanced chat service)
        # For now, return basic status information
        status_data = {
            "thread_id": thread_id,
            "status": "active",
            "last_activity": "2024-01-15T10:30:00Z",
            "pending_clarification": False,
            "generation_active": False,
            "current_round": 0,
            "max_rounds": 2
        }

        await websocket_manager.send_to_session(session_id, {
            "event_type": "thread_status",
            "timestamp": "2024-01-15T10:30:00Z",
            "data": status_data
        })

        logger.info(f"Thread status requested via WebSocket: thread_id={thread_id}, user_id={user_id}")

    except Exception as e:
        logger.error(f"Error handling thread status request: {e}")
        await websocket_manager.send_to_session(session_id, {
            "event_type": "error",
            "data": {"message": "Error retrieving thread status"}
        })


async def _handle_analysis_details_request(
    session_id: str,
    message_data: Dict[str, Any],
    user_id: str
) -> None:
    """Handle request for detailed analysis information."""
    try:
        thread_id = message_data.get("thread_id")

        if not thread_id:
            await websocket_manager.send_to_session(session_id, {
                "event_type": "error",
                "data": {"message": "thread_id required for analysis details"}
            })
            return

        # Return detailed analysis information (mock data for now)
        analysis_details = {
            "thread_id": thread_id,
            "analysis": {
                "confidence_score": 0.75,
                "complexity_score": 0.6,
                "estimated_generation_time": 90,
                "missing_elements": ["instance_type", "region"],
                "intent_classification": "infrastructure_creation",
                "processing_time_ms": 1250
            },
            "clarification_history": [],
            "generation_status": "not_started"
        }

        await websocket_manager.send_to_session(session_id, {
            "event_type": "analysis_details",
            "timestamp": "2024-01-15T10:30:00Z",
            "data": analysis_details
        })

        logger.info(f"Analysis details requested via WebSocket: thread_id={thread_id}, user_id={user_id}")

    except Exception as e:
        logger.error(f"Error handling analysis details request: {e}")
        await websocket_manager.send_to_session(session_id, {
            "event_type": "error",
            "data": {"message": "Error retrieving analysis details"}
        })


# HTTP endpoints for enhanced chat WebSocket management
@router.get("/enhanced-chat/connections/stats")
async def get_enhanced_chat_connection_stats():
    """Get enhanced chat WebSocket connection statistics."""
    stats = websocket_manager.get_connection_stats()
    
    # Filter for enhanced chat connections
    enhanced_chat_connections = 0
    for session_id, session in websocket_manager.active_connections.items():
        if session.metadata.get("connection_type") == "enhanced_chat":
            enhanced_chat_connections += 1
    
    return {
        "status": "success",
        "data": {
            **stats,
            "enhanced_chat_connections": enhanced_chat_connections,
            "features": [
                "real_time_analysis",
                "clarification_flow",
                "generation_progress",
                "max_2_clarification_rounds"
            ]
        }
    }


@router.post("/enhanced-chat/broadcast/thread/{thread_id}")
async def broadcast_to_enhanced_chat_thread(
    thread_id: str,
    message: Dict[str, Any]
):
    """Broadcast message to enhanced chat thread subscribers."""
    sent_count = await websocket_manager.broadcast_to_conversation(thread_id, {
        "event_type": "enhanced_chat_broadcast",
        "timestamp": "2024-01-15T10:30:00Z",
        "data": message
    })

    return {
        "status": "success",
        "data": {
            "thread_id": thread_id,
            "sessions_notified": sent_count,
            "message": message
        }
    }