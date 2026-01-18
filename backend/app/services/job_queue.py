"""
Background Job Queue Service for autonomous chat processing.

This service provides asynchronous job processing for autonomous chat operations,
including prompt analysis, clarification handling, and code generation.
"""

import asyncio
import uuid
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Callable
from dataclasses import dataclass, field
from enum import Enum
import logging

logger = logging.getLogger(__name__)


class JobStatus(str, Enum):
    """Job status enumeration."""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class JobPriority(str, Enum):
    """Job priority levels."""
    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    URGENT = "urgent"


@dataclass
class Job:
    """Represents a background job."""
    job_id: str
    job_type: str
    priority: JobPriority
    status: JobStatus
    created_at: datetime
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    data: Dict[str, Any] = field(default_factory=dict)
    result: Optional[Any] = None
    error: Optional[str] = None
    retry_count: int = 0
    max_retries: int = 3
    timeout_seconds: int = 300  # 5 minutes default


class JobQueueService:
    """
    Background job queue service for processing autonomous chat operations.

    Features:
    - Priority-based job scheduling
    - Retry mechanism for failed jobs
    - Timeout handling
    - Real-time status updates via WebSocket
    - Concurrent job processing
    """

    def __init__(self, max_concurrent_jobs: int = 5):
        self.max_concurrent_jobs = max_concurrent_jobs
        self.jobs: Dict[str, Job] = {}
        self.job_handlers: Dict[str, Callable] = {}
        self.running_jobs = set()
        self.job_queue = asyncio.PriorityQueue()

        # Background tasks
        self._processor_task = None
        self._cleanup_task = None

        # WebSocket manager for real-time updates
        from app.services.websocket_manager import websocket_manager
        self.websocket_manager = websocket_manager

    async def start(self):
        """Start the job queue processor."""
        if not self._processor_task:
            self._processor_task = asyncio.create_task(self._process_jobs())
        if not self._cleanup_task:
            self._cleanup_task = asyncio.create_task(self._cleanup_expired_jobs())

        logger.info("Job queue service started")

    async def stop(self):
        """Stop the job queue processor."""
        if self._processor_task:
            self._processor_task.cancel()
            try:
                await self._processor_task
            except asyncio.CancelledError:
                pass
            self._processor_task = None

        if self._cleanup_task:
            self._cleanup_task.cancel()
            try:
                await self._cleanup_task
            except asyncio.CancelledError:
                pass
            self._cleanup_task = None

        logger.info("Job queue service stopped")

    def register_handler(self, job_type: str, handler: Callable):
        """Register a job handler for a specific job type."""
        self.job_handlers[job_type] = handler
        logger.info(f"Registered handler for job type: {job_type}")

    async def submit_job(
        self,
        job_type: str,
        data: Dict[str, Any],
        priority: JobPriority = JobPriority.NORMAL,
        timeout_seconds: int = 300
    ) -> str:
        """Submit a job to the queue."""
        job_id = str(uuid.uuid4())
        job = Job(
            job_id=job_id,
            job_type=job_type,
            priority=priority,
            status=JobStatus.PENDING,
            created_at=datetime.utcnow(),
            data=data,
            timeout_seconds=timeout_seconds
        )

        self.jobs[job_id] = job

        # Priority queue: lower number = higher priority
        priority_value = {
            JobPriority.URGENT: 0,
            JobPriority.HIGH: 1,
            JobPriority.NORMAL: 2,
            JobPriority.LOW: 3
        }[priority]

        await self.job_queue.put((priority_value, job_id))

        # Send WebSocket notification
        await self._notify_job_status(job, "queued")

        logger.info(f"Job submitted: {job_id} (type: {job_type}, priority: {priority.value})")
        return job_id

    async def get_job_status(self, job_id: str) -> Optional[Dict[str, Any]]:
        """Get the status of a job."""
        job = self.jobs.get(job_id)
        if not job:
            return None

        return {
            "job_id": job.job_id,
            "job_type": job.job_type,
            "status": job.status.value,
            "priority": job.priority.value,
            "created_at": job.created_at.isoformat(),
            "started_at": job.started_at.isoformat() if job.started_at else None,
            "completed_at": job.completed_at.isoformat() if job.completed_at else None,
            "progress": job.data.get("progress", 0),
            "result": job.result,
            "error": job.error
        }

    async def cancel_job(self, job_id: str) -> bool:
        """Cancel a job if it's still pending."""
        job = self.jobs.get(job_id)
        if not job or job.status not in [JobStatus.PENDING, JobStatus.RUNNING]:
            return False

        job.status = JobStatus.CANCELLED
        job.completed_at = datetime.utcnow()

        await self._notify_job_status(job, "cancelled")
        logger.info(f"Job cancelled: {job_id}")
        return True

    async def _process_jobs(self):
        """Background task to process jobs from the queue."""
        while True:
            try:
                # Wait for a job
                priority_value, job_id = await self.job_queue.get()

                job = self.jobs.get(job_id)
                if not job or job.status != JobStatus.PENDING:
                    continue

                # Check if we can run this job
                if len(self.running_jobs) >= self.max_concurrent_jobs:
                    # Put it back in the queue
                    await self.job_queue.put((priority_value, job_id))
                    await asyncio.sleep(1)  # Wait before checking again
                    continue

                # Start processing the job
                self.running_jobs.add(job_id)
                asyncio.create_task(self._execute_job(job))

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in job processor: {e}")
                await asyncio.sleep(1)

    async def _execute_job(self, job: Job):
        """Execute a single job."""
        try:
            job.status = JobStatus.RUNNING
            job.started_at = datetime.utcnow()

            await self._notify_job_status(job, "started")

            # Get the handler
            handler = self.job_handlers.get(job.job_type)
            if not handler:
                raise ValueError(f"No handler registered for job type: {job.job_type}")

            # Execute with timeout
            try:
                result = await asyncio.wait_for(
                    handler(job.data, job),
                    timeout=job.timeout_seconds
                )
                job.result = result
                job.status = JobStatus.COMPLETED
                job.completed_at = datetime.utcnow()

                await self._notify_job_status(job, "completed")

            except asyncio.TimeoutError:
                raise Exception(f"Job timed out after {job.timeout_seconds} seconds")
            except Exception as e:
                # Handle retries
                job.retry_count += 1
                if job.retry_count < job.max_retries:
                    logger.warning(f"Job {job.job_id} failed (attempt {job.retry_count}), retrying...")
                    job.status = JobStatus.PENDING
                    await self.job_queue.put((0, job.job_id))  # High priority retry
                    return
                else:
                    raise e

        except Exception as e:
            job.status = JobStatus.FAILED
            job.error = str(e)
            job.completed_at = datetime.utcnow()

            await self._notify_job_status(job, "failed")
            logger.error(f"Job {job.job_id} failed: {e}")

        finally:
            self.running_jobs.discard(job.job_id)

    async def _notify_job_status(self, job: Job, action: str):
        """Send WebSocket notification about job status change."""
        if not self.websocket_manager:
            return

        try:
            # Get user_id from job data
            user_id = job.data.get("user_id")
            if not user_id:
                return

            event_data = {
                "event_type": "job_status_update",
                "timestamp": datetime.utcnow().isoformat(),
                "data": {
                    "job_id": job.job_id,
                    "job_type": job.job_type,
                    "action": action,
                    "status": job.status.value,
                    "progress": job.data.get("progress", 0),
                    "result": job.result,
                    "error": job.error
                }
            }

            await self.websocket_manager.send_to_user(user_id, event_data)

        except Exception as e:
            logger.warning(f"Failed to send job status notification: {e}")

    async def _cleanup_expired_jobs(self):
        """Background task to clean up expired jobs."""
        while True:
            try:
                await asyncio.sleep(60)  # Check every minute

                current_time = datetime.utcnow()
                expired_jobs = []

                for job_id, job in self.jobs.items():
                    if job.status in [JobStatus.PENDING, JobStatus.RUNNING]:
                        # Check for timeout
                        start_time = job.started_at or job.created_at
                        if current_time - start_time > timedelta(seconds=job.timeout_seconds * 2):
                            expired_jobs.append(job_id)

                for job_id in expired_jobs:
                    job = self.jobs[job_id]
                    job.status = JobStatus.FAILED
                    job.error = "Job expired"
                    job.completed_at = current_time
                    await self._notify_job_status(job, "expired")
                    logger.warning(f"Job expired: {job_id}")

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in job cleanup: {e}")
                await asyncio.sleep(60)


# Global job queue instance
job_queue_service = JobQueueService()


async def handle_autonomous_chat_processing(job_data: dict, job) -> dict:
    """
    Handle autonomous chat message processing job.

    Args:
        job_data: Job data containing message details
        job: Job instance for progress updates

    Returns:
        dict: Processing result
    """
    from app.services.chat_service import ChatService
    from app.db.session import get_async_db

    # Update job progress
    job.data["progress"] = 10

    try:
        # Get database session
        db = await anext(get_async_db())
        chat_service = ChatService(db)

        # Extract job data
        project_id = job_data["project_id"]
        user_id = job_data["user_id"]
        message_content = job_data["message_content"]
        thread_id = job_data["thread_id"]
        cloud_provider = job_data.get("cloud_provider", "AWS")
        clarification_round = job_data.get("clarification_round", 0)

        # Update progress
        job.data["progress"] = 25

        # Process the autonomous message synchronously in the job
        result = await chat_service._process_autonomous_message_sync(
            project_id=project_id,
            user_id=user_id,
            message_content=message_content,
            thread_id=thread_id,
            cloud_provider=cloud_provider,
            clarification_round=clarification_round
        )

        # Update progress
        job.data["progress"] = 100

        return result

    except Exception as e:
        logger.error(f"Error in autonomous chat processing job: {e}")
        raise


# Register job handlers
job_queue_service.register_handler("autonomous_chat_processing", handle_autonomous_chat_processing)