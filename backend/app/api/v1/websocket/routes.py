"""
WebSocket routes for real-time communication.

This module provides WebSocket endpoints for real-time updates,
project monitoring, and generation progress tracking.
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
from fastapi.security import HTTPBearer

from app.services.websocket_manager import websocket_manager
from app.services.azure_entra_service import AzureEntraService
from app.middleware.supabase_auth import get_current_user_id_optional

logger = logging.getLogger(__name__)
router = APIRouter()
security = HTTPBearer()


@router.websocket("/ws")
async def websocket_endpoint(
    websocket: WebSocket,
    token: Optional[str] = Query(None, description="Supabase JWT access token"),
):
    """
    Main WebSocket endpoint for real-time communication.

    Query Parameters:
        token: Supabase JWT access token for authentication

    WebSocket Message Format:
        {
            "action": "subscribe_project|subscribe_generation|heartbeat|unsubscribe",
            "data": {
                "project_id": "optional",
                "generation_id": "optional"
            }
        }
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

        # Connect WebSocket
        session_id = await websocket_manager.connect(websocket, user_id)

        # Handle incoming messages
        while True:
            try:
                # Receive message from client
                data = await websocket.receive_text()
                message = json.loads(data)

                action = message.get("action")
                message_data = message.get("data", {})

                # Handle different actions
                if action == "subscribe_project":
                    project_id = message_data.get("project_id")
                    if project_id:
                        await websocket_manager.subscribe_to_project(
                            session_id, project_id
                        )
                        logger.info(
                            f"Session {session_id} subscribed to project {project_id}"
                        )
                    else:
                        await websocket_manager.send_to_session(
                            session_id,
                            {
                                "event_type": "error",
                                "data": {
                                    "message": "project_id required for project subscription"
                                },
                            },
                        )

                elif action == "subscribe_generation":
                    generation_id = message_data.get("generation_id")
                    if generation_id:
                        await websocket_manager.subscribe_to_generation(
                            session_id, generation_id
                        )
                        logger.info(
                            f"Session {session_id} subscribed to generation {generation_id}"
                        )
                    else:
                        await websocket_manager.send_to_session(
                            session_id,
                            {
                                "event_type": "error",
                                "data": {
                                    "message": "generation_id required for generation subscription"
                                },
                            },
                        )

                elif action == "heartbeat":
                    await websocket_manager.handle_heartbeat(session_id)

                elif action == "get_stats":
                    # Send connection statistics (for debugging/monitoring)
                    stats = websocket_manager.get_connection_stats()
                    await websocket_manager.send_to_session(
                        session_id, {"event_type": "stats", "data": stats}
                    )

                elif action == "submit_clarification":
                    generation_id = message_data.get("generation_id")
                    response = message_data.get("response")

                    if generation_id and response is not None:
                        success = await websocket_manager.submit_clarification_response(
                            generation_id, user_id, response
                        )
                        if success:
                            await websocket_manager.send_to_session(
                                session_id,
                                {
                                    "event_type": "clarification_submitted",
                                    "data": {
                                        "generation_id": generation_id,
                                        "message": "Clarification response submitted successfully"
                                    },
                                },
                            )
                            logger.info(
                                f"User {user_id} submitted clarification for generation {generation_id}"
                            )
                        else:
                            await websocket_manager.send_to_session(
                                session_id,
                                {
                                    "event_type": "error",
                                    "data": {
                                        "message": "Failed to submit clarification response"
                                    },
                                },
                            )
                    else:
                        await websocket_manager.send_to_session(
                            session_id,
                            {
                                "event_type": "error",
                                "data": {
                                    "message": "generation_id and response required for clarification submission"
                                },
                            },
                        )

                else:
                    await websocket_manager.send_to_session(
                        session_id,
                        {
                            "event_type": "error",
                            "data": {"message": f"Unknown action: {action}"},
                        },
                    )

            except WebSocketDisconnect:
                # Client disconnected, break the loop
                logger.info(f"WebSocket disconnected during message handling: session_id={session_id}")
                break
            except json.JSONDecodeError:
                await websocket_manager.send_to_session(
                    session_id,
                    {"event_type": "error", "data": {"message": "Invalid JSON format"}},
                )
            except Exception as e:
                logger.error(f"Error handling WebSocket message: {str(e)}")
                await websocket_manager.send_to_session(
                    session_id,
                    {
                        "event_type": "error",
                        "data": {"message": "Internal server error"},
                    },
                )

    except WebSocketDisconnect:
        logger.info(f"WebSocket disconnected: session_id={session_id}")
    except Exception as e:
        logger.error(f"WebSocket error: {str(e)}")
    finally:
        if session_id:
            await websocket_manager.disconnect(session_id)


@router.websocket("/ws/project/{project_id}")
async def project_websocket_endpoint(
    websocket: WebSocket,
    project_id: str,
    token: Optional[str] = Query(None, description="Supabase JWT access token"),
):
    """
    WebSocket endpoint for specific project updates.

    Path Parameters:
        project_id: Project ID to subscribe to

    Query Parameters:
        token: Supabase JWT access token for authentication
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

        # Connect WebSocket
        session_id = await websocket_manager.connect(
            websocket, user_id, metadata={"auto_subscribed_project": project_id}
        )

        # Auto-subscribe to project
        await websocket_manager.subscribe_to_project(session_id, project_id)

        # Handle incoming messages (mainly heartbeats)
        while True:
            try:
                data = await websocket.receive_text()
                message = json.loads(data)

                action = message.get("action")

                if action == "heartbeat":
                    await websocket_manager.handle_heartbeat(session_id)
                else:
                    await websocket_manager.send_to_session(
                        session_id,
                        {
                            "event_type": "info",
                            "data": {
                                "message": "This endpoint is auto-subscribed to project updates"
                            },
                        },
                    )

            except WebSocketDisconnect:
                # Client disconnected, break the loop
                logger.info(f"Project WebSocket disconnected during message handling: session_id={session_id}, project_id={project_id}")
                break
            except json.JSONDecodeError:
                await websocket_manager.send_to_session(
                    session_id,
                    {"event_type": "error", "data": {"message": "Invalid JSON format"}},
                )
            except Exception as e:
                logger.error(f"Error handling project WebSocket message: {str(e)}")

    except WebSocketDisconnect:
        logger.info(
            f"Project WebSocket disconnected: session_id={session_id}, project_id={project_id}"
        )
    except Exception as e:
        logger.error(f"Project WebSocket error: {str(e)}")
    finally:
        if session_id:
            await websocket_manager.disconnect(session_id)


@router.websocket("/ws/generation/{generation_id}")
async def generation_websocket_endpoint(
    websocket: WebSocket,
    generation_id: str,
    token: Optional[str] = Query(None, description="Supabase JWT access token"),
):
    """
    WebSocket endpoint for specific generation updates.

    Path Parameters:
        generation_id: Generation ID to subscribe to

    Query Parameters:
        token: Supabase JWT access token for authentication
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

        # Connect WebSocket
        session_id = await websocket_manager.connect(
            websocket, user_id, metadata={"auto_subscribed_generation": generation_id}
        )

        # Auto-subscribe to generation
        await websocket_manager.subscribe_to_generation(session_id, generation_id)

        # Handle incoming messages (mainly heartbeats)
        while True:
            try:
                data = await websocket.receive_text()
                message = json.loads(data)

                action = message.get("action")

                if action == "heartbeat":
                    await websocket_manager.handle_heartbeat(session_id)
                else:
                    await websocket_manager.send_to_session(
                        session_id,
                        {
                            "event_type": "info",
                            "data": {
                                "message": "This endpoint is auto-subscribed to generation updates"
                            },
                        },
                    )

            except WebSocketDisconnect:
                # Client disconnected, break the loop
                logger.info(f"Generation WebSocket disconnected during message handling: session_id={session_id}, generation_id={generation_id}")
                break
            except json.JSONDecodeError:
                await websocket_manager.send_to_session(
                    session_id,
                    {"event_type": "error", "data": {"message": "Invalid JSON format"}},
                )
            except Exception as e:
                logger.error(f"Error handling generation WebSocket message: {str(e)}")

    except WebSocketDisconnect:
        logger.info(
            f"Generation WebSocket disconnected: session_id={session_id}, generation_id={generation_id}"
        )
    except Exception as e:
        logger.error(f"Generation WebSocket error: {str(e)}")
    finally:
        if session_id:
            await websocket_manager.disconnect(session_id)


# HTTP endpoints for WebSocket management
@router.get("/connections/stats")
async def get_connection_stats(user_id=Depends(get_current_user_id_optional)):
    """
    Get WebSocket connection statistics.

    Requires authentication.
    """
    stats = websocket_manager.get_connection_stats()
    return {"status": "success", "data": stats}


@router.post("/broadcast/user/{target_user_id}")
async def broadcast_to_user(
    target_user_id: str,
    message: Dict[str, Any],
    current_user_id=Depends(get_current_user_id_optional),
):
    """
    Broadcast message to all sessions of a specific user.

    Requires authentication. Users can only broadcast to themselves
    unless they have admin privileges.
    """
    # Check permissions (simplified since we don't have role info from Supabase JWT)
    if current_user_id != target_user_id:
        raise HTTPException(status_code=403, detail="Can only broadcast to your own sessions")

    # Convert string user_id to int for websocket_manager
    try:
        user_id_int = int(target_user_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid user ID format")

    sent_count = await websocket_manager.send_to_user(user_id_int, message)

    return {
        "status": "success",
        "data": {
            "user_id": target_user_id,
            "sessions_notified": sent_count,
            "message": message,
        },
    }


@router.post("/broadcast/project/{project_id}")
async def broadcast_to_project(
    project_id: str,
    message: Dict[str, Any],
    user_id=Depends(get_current_user_id_optional),
):
    """
    Broadcast message to all sessions subscribed to a project.

    Requires authentication. This would typically be called by
    internal services when project updates occur.
    """
    # TODO: Add project ownership/permission checks

    sent_count = await websocket_manager.broadcast_to_project(project_id, message)

    return {
        "status": "success",
        "data": {
            "project_id": project_id,
            "sessions_notified": sent_count,
            "message": message,
        },
    }


@router.post("/broadcast/generation/{generation_id}")
async def broadcast_to_generation(
    generation_id: str,
    message: Dict[str, Any],
    user_id=Depends(get_current_user_id_optional),
):
    """
    Broadcast message to all sessions subscribed to a generation.

    Requires authentication. This would typically be called by
    code generation services when status updates occur.
    """
    # TODO: Add generation ownership/permission checks

    sent_count = await websocket_manager.broadcast_to_generation(generation_id, message)

    return {
        "status": "success",
        "data": {
            "generation_id": generation_id,
            "sessions_notified": sent_count,
            "message": message,
        },
    }
