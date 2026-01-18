"""
Socket.IO Manager for real-time updates and communication.

This module provides Socket.IO connection management, user session tracking,
event broadcasting, and authentication for real-time features.
"""

import asyncio
import json
import logging
from datetime import datetime, timedelta
from typing import Dict, Set, Optional, List, Any
from uuid import uuid4

import socketio
from pydantic import BaseModel, ConfigDict
from dataclasses import dataclass

from app.core.settings import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()


@dataclass
class SocketIOSession:
    """Socket.IO session information."""

    session_id: str
    user_id: str  # Supabase user ID (string)
    sid: str  # Socket.IO session ID
    connected_at: datetime
    last_heartbeat: datetime
    metadata: Dict[str, Any]


class RealtimeEvent(BaseModel):
    """Base model for real-time events."""

    event_type: str
    timestamp: datetime
    data: Dict[str, Any]
    session_id: Optional[str] = None
    user_id: Optional[str] = None  # Supabase user ID (string)


class GenerationProgressEvent(RealtimeEvent):
    """Event for code generation progress updates."""

    event_type: str = "generation_progress"
    generation_id: str
    project_id: str
    status: str
    progress_percentage: int
    current_step: str
    estimated_completion: Optional[datetime] = None
    files_generated: List[str] = []


class ProjectUpdateEvent(RealtimeEvent):
    """Event for project updates."""

    event_type: str = "project_updated"
    project_id: str
    update_type: str  # "file_added", "generation_completed", etc.


class UserClarificationRequestEvent(RealtimeEvent):
    """Event for requesting user clarification during autonomous generation."""

    event_type: str = "user_clarification_request"
    generation_id: str
    project_id: str
    question: str
    context: Optional[Dict[str, Any]] = None
    timeout_seconds: int = 300  # 5 minutes default timeout


class ConversationStartedEvent(RealtimeEvent):
    """Event for when a new conversation thread is started."""

    event_type: str = "conversation_started"
    thread_id: str
    project_id: str
    user_id: str
    title: Optional[str] = None


class ClarificationRequestedEvent(RealtimeEvent):
    """Event for when clarification is requested in autonomous chat."""

    event_type: str = "clarification_requested"
    thread_id: str
    request_id: str
    questions: List[str]
    context_summary: str


class CodeGenerationProgressEvent(RealtimeEvent):
    """Event for code generation progress updates."""

    event_type: str = "code_generation_progress"
    thread_id: str
    generation_id: str
    job_id: str
    status: str
    progress_percentage: int
    current_step: str
    estimated_completion: Optional[datetime] = None


class SocketIOManager:
    """
    Manages Socket.IO connections, user sessions, and event broadcasting.

    Features:
    - Connection management with authentication
    - User session tracking
    - Event broadcasting to specific users or sessions
    - Heartbeat mechanism for connection health
    - Automatic cleanup of stale connections
    """

    def __init__(self):
        # Create Socket.IO server
        self.sio = socketio.AsyncServer(
            async_mode='asgi',
            cors_allowed_origins='*',
            logger=True,
            engineio_logger=True
        )

        # Active Socket.IO connections: session_id -> SocketIOSession
        self.active_connections: Dict[str, SocketIOSession] = {}

        # User to sessions mapping: user_id -> Set[session_id]
        self.user_sessions: Dict[str, Set[str]] = {}  # Supabase user ID (string)

        # SID to session mapping: sid -> session_id
        self.sid_to_session: Dict[str, str] = {}

        # Project subscriptions: project_id -> Set[session_id]
        self.project_subscriptions: Dict[str, Set[str]] = {}

        # Generation subscriptions: generation_id -> Set[session_id]
        self.generation_subscriptions: Dict[str, Set[str]] = {}

        # Conversation subscriptions: thread_id -> Set[session_id]
        self.conversation_subscriptions: Dict[str, Set[str]] = {}

        # Pending clarification requests: generation_id -> clarification_data
        self.pending_clarifications: Dict[str, Dict[str, Any]] = {}

        # Heartbeat interval (seconds)
        self.heartbeat_interval = 30

        # Connection timeout (seconds)
        self.connection_timeout = 300  # 5 minutes

        # Setup Socket.IO event handlers
        self._setup_event_handlers()

        # Start background tasks
        self._heartbeat_task = None
        self._cleanup_task = None

    def _setup_event_handlers(self):
        """Setup Socket.IO event handlers."""

        @self.sio.event
        async def connect(sid, environ, auth):
            """Handle Socket.IO connection with authentication."""
            try:
                # Extract token from auth data
                token = auth.get('token') if auth else None
                if not token:
                    logger.warning(f"Socket.IO connection {sid} rejected: No token provided")
                    return False

                # Authenticate user
                user_id = await self.authenticate_socketio(sid, token)
                if not user_id:
                    logger.warning(f"Socket.IO connection {sid} rejected: Invalid token")
                    return False

                # Create session
                session_id = await self.connect_socketio(sid, user_id)
                logger.info(f"Socket.IO client connected: sid={sid}, user_id={user_id}, session_id={session_id}")

                return True

            except Exception as e:
                logger.error(f"Socket.IO connection error for {sid}: {e}")
                return False

        @self.sio.event
        async def disconnect(sid):
            """Handle Socket.IO disconnection."""
            await self.disconnect_socketio(sid)
            logger.info(f"Socket.IO client disconnected: {sid}")

        @self.sio.event
        async def heartbeat(sid, data):
            """Handle heartbeat from client."""
            await self.handle_heartbeat_socketio(sid)

        @self.sio.event
        async def subscribe_project(sid, data):
            """Handle project subscription request."""
            session_id = self.sid_to_session.get(sid)
            if session_id and data.get('project_id'):
                await self.subscribe_to_project(session_id, data['project_id'])
                await self.sio.emit('subscription_confirmed', {
                    'subscription_type': 'project',
                    'project_id': data['project_id']
                }, to=sid)

        @self.sio.event
        async def subscribe_generation(sid, data):
            """Handle generation subscription request."""
            session_id = self.sid_to_session.get(sid)
            if session_id and data.get('generation_id'):
                await self.subscribe_to_generation(session_id, data['generation_id'])
                await self.sio.emit('subscription_confirmed', {
                    'subscription_type': 'generation',
                    'generation_id': data['generation_id']
                }, to=sid)

        @self.sio.event
        async def submit_clarification(sid, data):
            """Handle clarification response submission."""
            session_id = self.sid_to_session.get(sid)
            if session_id:
                generation_id = data.get('generation_id')
                response = data.get('response')
                user_id = self.active_connections[session_id].user_id if session_id in self.active_connections else None

                if generation_id and response is not None and user_id:
                    success = await self.submit_clarification_response(generation_id, user_id, response)
                    if success:
                        await self.sio.emit('clarification_submitted', {
                            'generation_id': generation_id,
                            'message': 'Clarification response submitted successfully'
                        }, to=sid)
                    else:
                        await self.sio.emit('error', {
                            'message': 'Failed to submit clarification response'
                        }, to=sid)

        @self.sio.event
        async def handle_heartbeat_socketio(sid):
            """Handle heartbeat from client."""
            session_id = self.sid_to_session.get(sid)
            if session_id:
                await self.handle_heartbeat(session_id)

    async def start_background_tasks(self):
        """Start background tasks for heartbeat and cleanup."""
        if not self._heartbeat_task:
            self._heartbeat_task = asyncio.create_task(self._heartbeat_loop())
        if not self._cleanup_task:
            self._cleanup_task = asyncio.create_task(self._cleanup_loop())

    async def stop_background_tasks(self):
        """Stop background tasks."""
        if self._heartbeat_task:
            self._heartbeat_task.cancel()
            try:
                await self._heartbeat_task
            except asyncio.CancelledError:
                pass
            self._heartbeat_task = None

        if self._cleanup_task:
            self._cleanup_task.cancel()
            try:
                await self._cleanup_task
            except asyncio.CancelledError:
                pass
            self._cleanup_task = None

    async def authenticate_socketio(self, sid: str, token: str) -> Optional[str]:
        """
        Authenticate Socket.IO connection using Supabase JWT token.

        Args:
            sid: Socket.IO session ID
            token: Supabase JWT access token

        Returns:
            Supabase user ID if authentication successful, None otherwise
        """
        try:
            # Import here to avoid circular imports
            from app.middleware.supabase_auth import SupabaseJWTValidator

            validator = SupabaseJWTValidator()

            # Validate token and extract user information
            supabase_user = validator.extract_user_info(token)

            # Additional validation: check if user exists in Supabase
            user_exists = await validator.validate_user_exists(supabase_user.id)

            if user_exists:
                logger.debug(f"Socket.IO authentication successful for Supabase user: {supabase_user.id}")
                return supabase_user.id
            else:
                logger.warning(
                    f"Socket.IO authentication failed: User not found in Supabase (user_id: {supabase_user.id})"
                )
                return None

        except Exception as e:
            logger.error(f"Socket.IO authentication error: {str(e)}")
            return None

    async def connect_socketio(self, sid: str, user_id: str, metadata: Optional[Dict[str, Any]] = None) -> str:
        """
        Register Socket.IO connection and create session.

        Args:
            sid: Socket.IO session ID
            user_id: Authenticated Supabase user ID
            metadata: Optional session metadata

        Returns:
            Session ID
        """
        session_id = str(uuid4())
        now = datetime.utcnow()

        session = SocketIOSession(
            session_id=session_id,
            user_id=user_id,
            sid=sid,
            connected_at=now,
            last_heartbeat=now,
            metadata=metadata or {},
        )

        # Store session
        self.active_connections[session_id] = session
        self.sid_to_session[sid] = session_id

        # Add to user sessions
        if user_id not in self.user_sessions:
            self.user_sessions[user_id] = set()
        self.user_sessions[user_id].add(session_id)

        logger.info(f"Socket.IO session created: user_id={user_id}, session_id={session_id}, sid={sid}")

        # Send connection confirmation
        await self.sio.emit('connection_established', {
            "session_id": session_id,
            "timestamp": now.isoformat(),
            "data": {"message": "Socket.IO connection established"},
        }, to=sid)

        # Start background tasks if not already running
        await self.start_background_tasks()

        return session_id

    async def disconnect_socketio(self, sid: str):
        """
        Disconnect Socket.IO session and cleanup.

        Args:
            sid: Socket.IO session ID to disconnect
        """
        session_id = self.sid_to_session.get(sid)
        if not session_id or session_id not in self.active_connections:
            return

        session = self.active_connections[session_id]
        user_id = session.user_id

        # Remove from active connections
        del self.active_connections[session_id]
        del self.sid_to_session[sid]

        # Remove from user sessions
        if user_id in self.user_sessions:
            self.user_sessions[user_id].discard(session_id)
            if not self.user_sessions[user_id]:
                del self.user_sessions[user_id]

        # Remove from project subscriptions
        for project_id, sessions in self.project_subscriptions.items():
            sessions.discard(session_id)

        # Remove from generation subscriptions
        for generation_id, sessions in self.generation_subscriptions.items():
            sessions.discard(session_id)

        # Remove from conversation subscriptions
        for thread_id, sessions in self.conversation_subscriptions.items():
            sessions.discard(session_id)

        # Clean up empty subscription sets
        self.project_subscriptions = {
            k: v for k, v in self.project_subscriptions.items() if v
        }
        self.generation_subscriptions = {
            k: v for k, v in self.generation_subscriptions.items() if v
        }
        self.conversation_subscriptions = {
            k: v for k, v in self.conversation_subscriptions.items() if v
        }

        logger.info(f"Socket.IO disconnected: user_id={user_id}, session_id={session_id}, sid={sid}")

    async def send_to_session(self, session_id: str, message: Dict[str, Any]) -> bool:
        """
        Send message to specific session.

        Args:
            session_id: Target session ID
            message: Message to send

        Returns:
            True if sent successfully, False otherwise
        """
        if session_id not in self.active_connections:
            return False

        session = self.active_connections[session_id]
        sid = session.sid

        try:
            await self.sio.emit('message', message, to=sid)
            return True
        except Exception as e:
            logger.error(f"Failed to send message to session {session_id}: {str(e)}")
            await self.disconnect_socketio(sid)
            return False

    async def send_to_user(self, user_id: str, message: Dict[str, Any]) -> int:
        """
        Send message to all sessions of a user.

        Args:
            user_id: Target user ID
            message: Message to send

        Returns:
            Number of sessions message was sent to
        """
        if user_id not in self.user_sessions:
            return 0

        session_ids = self.user_sessions[user_id].copy()
        sent_count = 0

        for session_id in session_ids:
            if await self.send_to_session(session_id, message):
                sent_count += 1

        return sent_count

    async def broadcast_to_project(
        self, project_id: str, message: Dict[str, Any]
    ) -> int:
        """
        Broadcast message to all sessions subscribed to a project.

        Args:
            project_id: Target project ID
            message: Message to broadcast

        Returns:
            Number of sessions message was sent to
        """
        if project_id not in self.project_subscriptions:
            return 0

        session_ids = self.project_subscriptions[project_id].copy()
        sent_count = 0

        for session_id in session_ids:
            if await self.send_to_session(session_id, message):
                sent_count += 1

        return sent_count

    async def broadcast_to_generation(
        self, generation_id: str, message: Dict[str, Any]
    ) -> int:
        """
        Broadcast message to all sessions subscribed to a generation.

        Args:
            generation_id: Target generation ID
            message: Message to broadcast

        Returns:
            Number of sessions message was sent to
        """
        if generation_id not in self.generation_subscriptions:
            return 0

        session_ids = self.generation_subscriptions[generation_id].copy()
        sent_count = 0

        for session_id in session_ids:
            if await self.send_to_session(session_id, message):
                sent_count += 1

        return sent_count

    async def subscribe_to_project(self, session_id: str, project_id: str) -> bool:
        """
        Subscribe session to project updates.

        Args:
            session_id: Session ID
            project_id: Project ID to subscribe to

        Returns:
            True if subscribed successfully
        """
        if session_id not in self.active_connections:
            return False

        if project_id not in self.project_subscriptions:
            self.project_subscriptions[project_id] = set()

        self.project_subscriptions[project_id].add(session_id)

        # Send confirmation
        await self.send_to_session(
            session_id,
            {
                "event_type": "subscription_confirmed",
                "timestamp": datetime.utcnow().isoformat(),
                "data": {"subscription_type": "project", "project_id": project_id},
            },
        )

        return True

    async def subscribe_to_generation(
        self, session_id: str, generation_id: str
    ) -> bool:
        """
        Subscribe session to generation updates.

        Args:
            session_id: Session ID
            generation_id: Generation ID to subscribe to

        Returns:
            True if subscribed successfully
        """
        if session_id not in self.active_connections:
            return False

        if generation_id not in self.generation_subscriptions:
            self.generation_subscriptions[generation_id] = set()

        self.generation_subscriptions[generation_id].add(session_id)

        # Send confirmation
        await self.send_to_session(
            session_id,
            {
                "event_type": "subscription_confirmed",
                "timestamp": datetime.utcnow().isoformat(),
                "data": {
                    "subscription_type": "generation",
                    "generation_id": generation_id,
                },
            },
        )

        return True

    async def subscribe_to_conversation(
        self, session_id: str, thread_id: str
    ) -> bool:
        """
        Subscribe session to conversation updates.

        Args:
            session_id: Session ID
            thread_id: Conversation thread ID to subscribe to

        Returns:
            True if subscribed successfully
        """
        if session_id not in self.active_connections:
            return False

        if thread_id not in self.conversation_subscriptions:
            self.conversation_subscriptions[thread_id] = set()

        self.conversation_subscriptions[thread_id].add(session_id)

        # Send confirmation
        await self.send_to_session(
            session_id,
            {
                "event_type": "subscription_confirmed",
                "timestamp": datetime.utcnow().isoformat(),
                "data": {"subscription_type": "conversation", "thread_id": thread_id},
            },
        )

        return True

    async def broadcast_to_conversation(
        self, thread_id: str, message: Dict[str, Any]
    ) -> int:
        """
        Broadcast message to all sessions subscribed to a conversation.

        Args:
            thread_id: Target conversation thread ID
            message: Message to broadcast

        Returns:
            Number of sessions message was sent to
        """
        if thread_id not in self.conversation_subscriptions:
            return 0

        session_ids = self.conversation_subscriptions[thread_id].copy()
        sent_count = 0

        for session_id in session_ids:
            if await self.send_to_session(session_id, message):
                sent_count += 1

        return sent_count

    async def notify_conversation_started(
        self, thread_id: str, project_id: str, user_id: str, title: Optional[str] = None
    ) -> int:
        """
        Notify subscribers that a new conversation has started.

        Args:
            thread_id: Conversation thread ID
            project_id: Project ID
            user_id: User ID who started the conversation
            title: Optional conversation title

        Returns:
            Number of sessions notified
        """
        event_data = {
            "event_type": "conversation_started",
            "timestamp": datetime.utcnow().isoformat(),
            "data": {
                "thread_id": thread_id,
                "project_id": project_id,
                "user_id": user_id,
                "title": title,
            },
        }

        # Send to user's sessions
        sent_count = await self.send_to_user(user_id, event_data)

        logger.info(f"Conversation started notification sent to {sent_count} sessions for thread {thread_id}")
        return sent_count

    async def notify_clarification_requested(
        self, thread_id: str, request_id: str, questions: List[str], context_summary: str
    ) -> int:
        """
        Notify subscribers that clarification has been requested.

        Args:
            thread_id: Conversation thread ID
            request_id: Clarification request ID
            questions: List of clarification questions
            context_summary: Summary of conversation context

        Returns:
            Number of sessions notified
        """
        event_data = {
            "event_type": "clarification_requested",
            "timestamp": datetime.utcnow().isoformat(),
            "data": {
                "thread_id": thread_id,
                "request_id": request_id,
                "questions": questions,
                "context_summary": context_summary,
            },
        }

        # Send to conversation subscribers
        sent_count = await self.broadcast_to_conversation(thread_id, event_data)

        logger.info(f"Clarification requested notification sent to {sent_count} sessions for thread {thread_id}")
        return sent_count

    async def notify_code_generation_progress(
        self,
        thread_id: str,
        generation_id: str,
        job_id: str,
        status: str,
        progress_percentage: int,
        current_step: str,
        estimated_completion: Optional[datetime] = None
    ) -> int:
        """
        Notify subscribers of code generation progress.

        Args:
            thread_id: Conversation thread ID
            generation_id: Generation ID
            job_id: Job ID
            status: Current status
            progress_percentage: Progress percentage (0-100)
            current_step: Current step description
            estimated_completion: Estimated completion time

        Returns:
            Number of sessions notified
        """
        event_data = {
            "event_type": "code_generation_progress",
            "timestamp": datetime.utcnow().isoformat(),
            "data": {
                "thread_id": thread_id,
                "generation_id": generation_id,
                "job_id": job_id,
                "status": status,
                "progress_percentage": progress_percentage,
                "current_step": current_step,
                "estimated_completion": estimated_completion.isoformat() if estimated_completion else None,
            },
        }

        # Send to conversation subscribers
        sent_count = await self.broadcast_to_conversation(thread_id, event_data)

        logger.info(f"Code generation progress notification sent to {sent_count} sessions for thread {thread_id}: {status} ({progress_percentage}%)")
        return sent_count

    async def request_user_clarification(
        self,
        generation_id: str,
        project_id: str,
        user_id: str,
        question: str,
        context: Optional[Dict[str, Any]] = None,
        timeout_seconds: int = 300,
    ) -> bool:
        """
        Request clarification from user during autonomous generation.

        Args:
            generation_id: Generation ID requesting clarification
            project_id: Project ID
            user_id: User ID to request clarification from
            question: Question to ask the user
            context: Additional context for the clarification
            timeout_seconds: Timeout for user response

        Returns:
            True if request sent successfully
        """
        # Store pending clarification
        self.pending_clarifications[generation_id] = {
            "question": question,
            "context": context or {},
            "user_id": user_id,
            "project_id": project_id,
            "requested_at": datetime.utcnow(),
            "timeout_seconds": timeout_seconds,
            "response_future": asyncio.Future(),
        }

        event_data = {
            "event_type": "user_clarification_request",
            "timestamp": datetime.utcnow().isoformat(),
            "data": {
                "generation_id": generation_id,
                "project_id": project_id,
                "question": question,
                "context": context or {},
                "timeout_seconds": timeout_seconds,
            },
        }

        # Send to user's sessions
        sent_count = await self.send_to_user(user_id, event_data)

        if sent_count > 0:
            logger.info(
                f"Clarification request sent to user {user_id} for generation {generation_id}: {question[:50]}..."
            )

            # Set up timeout
            asyncio.create_task(self._handle_clarification_timeout(generation_id))
            return True
        else:
            logger.warning(f"Failed to send clarification request to user {user_id} - no active sessions")
            return False

    async def submit_clarification_response(
        self, generation_id: str, user_id: str, response: str
    ) -> bool:
        """
        Submit user response to a clarification request.

        Args:
            generation_id: Generation ID
            user_id: User ID providing the response
            response: User's response

        Returns:
            True if response was accepted
        """
        if generation_id not in self.pending_clarifications:
            logger.warning(f"No pending clarification found for generation {generation_id}")
            return False

        clarification = self.pending_clarifications[generation_id]

        # Verify user matches
        if clarification["user_id"] != user_id:
            logger.warning(f"User {user_id} attempted to respond to clarification for user {clarification['user_id']}")
            return False

        # Set the response
        clarification["response_future"].set_result(response)
        del self.pending_clarifications[generation_id]

        logger.info(f"Clarification response received for generation {generation_id}: {response[:50]}...")
        return True

    async def get_clarification_response(
        self, generation_id: str, timeout_seconds: Optional[int] = None
    ) -> Optional[str]:
        """
        Get the response to a clarification request.

        Args:
            generation_id: Generation ID
            timeout_seconds: Override timeout

        Returns:
            User response or None if timeout/no response
        """
        if generation_id not in self.pending_clarifications:
            return None

        clarification = self.pending_clarifications[generation_id]
        timeout = timeout_seconds or clarification["timeout_seconds"]

        try:
            response = await asyncio.wait_for(
                clarification["response_future"], timeout=timeout
            )
            return response
        except asyncio.TimeoutError:
            logger.warning(f"Clarification timeout for generation {generation_id}")
            del self.pending_clarifications[generation_id]
            return None

    async def _handle_clarification_timeout(self, generation_id: str):
        """Handle timeout for clarification requests."""
        if generation_id not in self.pending_clarifications:
            return

        clarification = self.pending_clarifications[generation_id]
        timeout = clarification["timeout_seconds"]

        try:
            await asyncio.sleep(timeout)
            if generation_id in self.pending_clarifications:
                clarification["response_future"].set_exception(asyncio.TimeoutError())
                del self.pending_clarifications[generation_id]
                logger.info(f"Clarification timed out for generation {generation_id}")
        except Exception as e:
            logger.error(f"Error handling clarification timeout: {e}")

    async def handle_heartbeat(self, session_id: str):
        """
        Handle heartbeat from client.

        Args:
            session_id: Session ID
        """
        if session_id in self.active_connections:
            self.active_connections[session_id].last_heartbeat = datetime.utcnow()

            # Send heartbeat response
            await self.send_to_session(
                session_id,
                {
                    "event_type": "heartbeat_response",
                    "timestamp": datetime.utcnow().isoformat(),
                    "data": {"status": "alive"},
                },
            )

    async def _heartbeat_loop(self):
        """Background task to send periodic heartbeats."""
        while True:
            try:
                await asyncio.sleep(self.heartbeat_interval)

                current_time = datetime.utcnow()
                heartbeat_message = {
                    "event_type": "heartbeat",
                    "timestamp": current_time.isoformat(),
                    "data": {"server_time": current_time.isoformat()},
                }

                # Send heartbeat to all active connections
                for session_id in list(self.active_connections.keys()):
                    await self.send_to_session(session_id, heartbeat_message)

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Heartbeat loop error: {str(e)}")

    async def _cleanup_loop(self):
        """Background task to cleanup stale connections."""
        while True:
            try:
                await asyncio.sleep(60)  # Check every minute

                current_time = datetime.utcnow()
                timeout_threshold = current_time - timedelta(
                    seconds=self.connection_timeout
                )

                # Find stale connections
                stale_sessions = []
                for session_id, session in self.active_connections.items():
                    if session.last_heartbeat < timeout_threshold:
                        stale_sessions.append(session_id)

                # Disconnect stale sessions
                for session_id in stale_sessions:
                    logger.info(f"Cleaning up stale WebSocket session: {session_id}")
                    await self.disconnect(session_id)

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Cleanup loop error: {str(e)}")

    def get_connection_stats(self) -> Dict[str, Any]:
        """
        Get WebSocket connection statistics.

        Returns:
            Dictionary with connection statistics
        """
        return {
            "total_connections": len(self.active_connections),
            "unique_users": len(self.user_sessions),
            "project_subscriptions": len(self.project_subscriptions),
            "generation_subscriptions": len(self.generation_subscriptions),
            "conversation_subscriptions": len(self.conversation_subscriptions),
            "connections_by_user": {
                user_id: len(sessions)
                for user_id, sessions in self.user_sessions.items()
            },
        }


# Global Socket.IO manager instance
websocket_manager = SocketIOManager()
