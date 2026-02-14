"""
WebSocket dashboard routes for real-time project updates.

This module provides WebSocket endpoints specifically for dashboard
real-time updates, project monitoring, and generation progress tracking.
"""

import json
import logging
from typing import Optional, Dict, Any
from datetime import datetime

from fastapi import (
    APIRouter,
    WebSocket,
    WebSocketDisconnect,
    Query,
    Path,
    Depends,
    HTTPException,
)
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.services.websocket_manager import websocket_manager
from app.services.realtime_service import realtime_service
from app.models.project import Project
from app.models.user import User
from app.dependencies.auth import get_current_user_id

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/websocket/dashboard", tags=["websocket-dashboard"])


@router.websocket("/ws/dashboard")
async def dashboard_websocket_endpoint(
    websocket: WebSocket,
    token: Optional[str] = Query(None, description="Azure Entra access token"),
):
    """
    WebSocket endpoint for dashboard-wide real-time updates.
    
    Provides real-time updates for:
    - All user projects status changes
    - Active generation progress across all projects
    - Project list updates
    - System notifications
    
    Query Parameters:
        token: Azure Entra access token for authentication
        
    WebSocket Message Format:
        Client -> Server:
        {
            "action": "subscribe_dashboard|heartbeat|get_stats",
            "data": {}
        }
        
        Server -> Client:
        {
            "event_type": "dashboard_update|generation_progress|project_updated|heartbeat",
            "timestamp": "2024-01-20T15:00:00Z",
            "data": { ... }
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
            
        # Connect WebSocket with dashboard metadata
        session_id = await websocket_manager.connect(
            websocket, 
            user_id,
            metadata={
                "connection_type": "dashboard",
                "auto_subscribe": "user_projects"
            }
        )
        
        # Send initial dashboard status
        await websocket_manager.send_to_session(
            session_id,
            {
                "event_type": "dashboard_connected",
                "timestamp": datetime.utcnow().isoformat(),
                "data": {
                    "message": "Connected to dashboard real-time updates",
                    "session_id": session_id,
                    "user_id": user_id
                }
            }
        )
        
        # Handle incoming messages
        while True:
            try:
                data = await websocket.receive_text()
                message = json.loads(data)
                
                action = message.get("action")
                message_data = message.get("data", {})
                
                if action == "subscribe_dashboard":
                    # Dashboard subscription is automatic, just confirm
                    await websocket_manager.send_to_session(
                        session_id,
                        {
                            "event_type": "subscription_confirmed",
                            "timestamp": datetime.utcnow().isoformat(),
                            "data": {
                                "subscription_type": "dashboard",
                                "message": "Subscribed to dashboard updates"
                            }
                        }
                    )
                    
                elif action == "heartbeat":
                    await websocket_manager.handle_heartbeat(session_id)
                    
                elif action == "get_stats":
                    stats = websocket_manager.get_connection_stats()
                    await websocket_manager.send_to_session(
                        session_id,
                        {
                            "event_type": "stats",
                            "timestamp": datetime.utcnow().isoformat(),
                            "data": stats
                        }
                    )
                    
                else:
                    await websocket_manager.send_to_session(
                        session_id,
                        {
                            "event_type": "error",
                            "timestamp": datetime.utcnow().isoformat(),
                            "data": {"message": f"Unknown action: {action}"}
                        }
                    )
                    
            except json.JSONDecodeError:
                await websocket_manager.send_to_session(
                    session_id,
                    {
                        "event_type": "error",
                        "timestamp": datetime.utcnow().isoformat(),
                        "data": {"message": "Invalid JSON format"}
                    }
                )
            except Exception as e:
                logger.error(f"Error handling dashboard WebSocket message: {str(e)}")
                await websocket_manager.send_to_session(
                    session_id,
                    {
                        "event_type": "error",
                        "timestamp": datetime.utcnow().isoformat(),
                        "data": {"message": "Internal server error"}
                    }
                )
                
    except WebSocketDisconnect:
        logger.info(f"Dashboard WebSocket disconnected: session_id={session_id}")
    except Exception as e:
        logger.error(f"Dashboard WebSocket error: {str(e)}")
    finally:
        if session_id:
            await websocket_manager.disconnect(session_id)


@router.websocket("/ws/project/{project_id}/dashboard")
async def project_dashboard_websocket_endpoint(
    websocket: WebSocket,
    project_id: str = Path(..., description="Project UUID"),
    token: Optional[str] = Query(None, description="Azure Entra access token"),
):
    """
    WebSocket endpoint for project-specific dashboard updates.
    
    Provides real-time updates for a specific project:
    - Generation progress for the project
    - File tree updates
    - Project status changes
    - Sync status updates
    
    Path Parameters:
        project_id: Project UUID to monitor
        
    Query Parameters:
        token: Azure Entra access token for authentication
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
            
        # Connect WebSocket with project dashboard metadata
        session_id = await websocket_manager.connect(
            websocket,
            user_id,
            metadata={
                "connection_type": "project_dashboard",
                "project_id": project_id,
                "auto_subscribed_project": project_id
            }
        )
        
        # Auto-subscribe to project updates
        await websocket_manager.subscribe_to_project(session_id, project_id)
        
        # Send initial project dashboard status
        await websocket_manager.send_to_session(
            session_id,
            {
                "event_type": "project_dashboard_connected",
                "timestamp": datetime.utcnow().isoformat(),
                "data": {
                    "message": f"Connected to project {project_id} dashboard updates",
                    "project_id": project_id,
                    "session_id": session_id
                }
            }
        )
        
        # Handle incoming messages
        while True:
            try:
                data = await websocket.receive_text()
                message = json.loads(data)
                
                action = message.get("action")
                message_data = message.get("data", {})
                
                if action == "subscribe_generation":
                    generation_id = message_data.get("generation_id")
                    if generation_id:
                        await websocket_manager.subscribe_to_generation(
                            session_id, generation_id
                        )
                        await websocket_manager.send_to_session(
                            session_id,
                            {
                                "event_type": "subscription_confirmed",
                                "timestamp": datetime.utcnow().isoformat(),
                                "data": {
                                    "subscription_type": "generation",
                                    "generation_id": generation_id
                                }
                            }
                        )
                    else:
                        await websocket_manager.send_to_session(
                            session_id,
                            {
                                "event_type": "error",
                                "timestamp": datetime.utcnow().isoformat(),
                                "data": {"message": "generation_id required"}
                            }
                        )
                        
                elif action == "heartbeat":
                    await websocket_manager.handle_heartbeat(session_id)
                    
                elif action == "get_project_status":
                    # Send current project status (would be implemented with database query)
                    await websocket_manager.send_to_session(
                        session_id,
                        {
                            "event_type": "project_status",
                            "timestamp": datetime.utcnow().isoformat(),
                            "data": {
                                "project_id": project_id,
                                "status": "active",  # Would be fetched from database
                                "message": "Project status retrieved"
                            }
                        }
                    )
                    
                else:
                    await websocket_manager.send_to_session(
                        session_id,
                        {
                            "event_type": "error",
                            "timestamp": datetime.utcnow().isoformat(),
                            "data": {"message": f"Unknown action: {action}"}
                        }
                    )
                    
            except json.JSONDecodeError:
                await websocket_manager.send_to_session(
                    session_id,
                    {
                        "event_type": "error",
                        "timestamp": datetime.utcnow().isoformat(),
                        "data": {"message": "Invalid JSON format"}
                    }
                )
            except Exception as e:
                logger.error(f"Error handling project dashboard WebSocket message: {str(e)}")
                
    except WebSocketDisconnect:
        logger.info(f"Project dashboard WebSocket disconnected: session_id={session_id}, project_id={project_id}")
    except Exception as e:
        logger.error(f"Project dashboard WebSocket error: {str(e)}")
    finally:
        if session_id:
            await websocket_manager.disconnect(session_id)


# HTTP endpoints for dashboard WebSocket management
@router.get("/connections/dashboard-stats")
async def get_dashboard_connection_stats(
    user_id: str = Depends(get_current_user_id)
):
    """
    Get dashboard-specific WebSocket connection statistics.
    
    Returns connection stats filtered for dashboard connections.
    """
    try:
        stats = websocket_manager.get_connection_stats()
        
        # Filter for dashboard connections
        dashboard_connections = 0
        project_dashboard_connections = 0
        
        for session_id, session in websocket_manager.active_connections.items():
            if session.user_id == user_id:
                connection_type = session.metadata.get("connection_type")
                if connection_type == "dashboard":
                    dashboard_connections += 1
                elif connection_type == "project_dashboard":
                    project_dashboard_connections += 1
        
        return {
            "status": "success",
            "data": {
                "user_id": user_id,
                "dashboard_connections": dashboard_connections,
                "project_dashboard_connections": project_dashboard_connections,
                "total_user_connections": stats.get("connections_by_user", {}).get(user_id, 0),
                "global_stats": stats
            }
        }
        
    except Exception as e:
        logger.error(f"Failed to get dashboard connection stats: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to retrieve dashboard connection stats: {str(e)}"
        )


@router.post("/broadcast/dashboard-update")
async def broadcast_dashboard_update(
    message: Dict[str, Any],
    user_id: str = Depends(get_current_user_id),
    db: Session = Depends(get_db)
):
    """
    Broadcast dashboard update to user's dashboard connections.
    
    This endpoint allows services to trigger dashboard updates
    for specific users.
    """
    try:
        # Add timestamp to message
        dashboard_message = {
            "event_type": "dashboard_update",
            "timestamp": datetime.utcnow().isoformat(),
            "data": message
        }
        
        # Send to user's dashboard connections
        sent_count = await websocket_manager.send_to_user(user_id, dashboard_message)
        
        return {
            "status": "success",
            "data": {
                "user_id": user_id,
                "sessions_notified": sent_count,
                "message": dashboard_message
            }
        }
        
    except Exception as e:
        logger.error(f"Failed to broadcast dashboard update: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to broadcast dashboard update: {str(e)}"
        )


@router.post("/trigger/project-list-update")
async def trigger_project_list_update(
    user_id: str = Depends(get_current_user_id),
    db: Session = Depends(get_db)
):
    """
    Trigger a project list update for the user's dashboard.
    
    This endpoint can be called when projects are created, updated,
    or when their status changes to notify dashboard clients.
    """
    try:
        # Get current project summary for the user
        from app.api.v1.projects.dashboard_routes import get_project_dashboard
        
        # Get updated dashboard data
        dashboard_data = await get_project_dashboard(
            include_archived=False,
            limit=20,
            db=db,
            current_user=current_user
        )
        
        # Broadcast update to dashboard connections
        update_message = {
            "event_type": "project_list_updated",
            "timestamp": datetime.utcnow().isoformat(),
            "data": {
                "total_projects": dashboard_data.total_projects,
                "total_active_generations": dashboard_data.total_active_generations,
                "projects": [
                    {
                        "id": p.id,
                        "name": p.name,
                        "realtime_status": p.realtime_status,
                        "active_generation_count": p.active_generation_count,
                        "file_count": p.file_count,
                        "generation_count": p.generation_count
                    }
                    for p in dashboard_data.projects
                ],
                "active_generations": [
                    {
                        "generation_id": g.generation_id,
                        "project_id": g.project_id,
                        "project_name": g.project_name,
                        "status": g.status,
                        "query": g.query[:100] + "..." if len(g.query) > 100 else g.query
                    }
                    for g in dashboard_data.active_generations
                ]
            }
        }
        
        sent_count = await websocket_manager.send_to_user(user_id, update_message)
        
        return {
            "status": "success",
            "data": {
                "user_id": user_id,
                "sessions_notified": sent_count,
                "projects_count": dashboard_data.total_projects,
                "active_generations_count": dashboard_data.total_active_generations
            }
        }
        
    except Exception as e:
        logger.error(f"Failed to trigger project list update: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to trigger project list update: {str(e)}"
        )
