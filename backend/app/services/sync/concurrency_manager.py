"""
Concurrency control module for Azure File Share and database operations.

This module provides utilities for managing concurrent access to projects and files,
implementing various locking strategies and optimistic concurrency control.
"""

import asyncio
import logging
import time
from datetime import datetime, timedelta
from typing import Dict, Optional, Set, Any, Callable, Awaitable
from contextlib import asynccontextmanager
from dataclasses import dataclass
from enum import Enum
from uuid import uuid4

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from sqlalchemy import select, update, and_, or_
from sqlalchemy.exc import IntegrityError, SQLAlchemyError

from app.models.project import Project, ProjectFile
from app.exceptions.azure_exceptions import ConcurrencyError, LockTimeoutError


logger = logging.getLogger(__name__)


class LockType(Enum):
    """Types of locks that can be acquired."""
    READ = "read"
    WRITE = "write"
    EXCLUSIVE = "exclusive"


class LockScope(Enum):
    """Scope of the lock operation."""
    PROJECT = "project"
    FILE = "file"
    GENERATION = "generation"


@dataclass
class LockInfo:
    """Information about an acquired lock."""
    lock_id: str
    resource_id: str
    lock_type: LockType
    lock_scope: LockScope
    owner_id: str
    acquired_at: datetime
    expires_at: Optional[datetime] = None
    metadata: Optional[Dict[str, Any]] = None


@dataclass
class OptimisticLockInfo:
    """Information for optimistic locking."""
    resource_id: str
    version: int
    last_modified: datetime
    checksum: Optional[str] = None


class DistributedLock:
    """
    Distributed lock implementation using database-backed coordination.
    
    Provides distributed locking across multiple application instances
    using the database as the coordination mechanism.
    """
    
    def __init__(self, db_session: AsyncSession, timeout: float = 30.0):
        self.db_session = db_session
        self.timeout = timeout
        self._locks: Dict[str, LockInfo] = {}
    
    async def acquire_lock(
        self,
        resource_id: str,
        lock_type: LockType,
        lock_scope: LockScope,
        owner_id: str,
        timeout: Optional[float] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> LockInfo:
        """
        Acquire a distributed lock for a resource.
        
        Args:
            resource_id: Unique identifier for the resource
            lock_type: Type of lock to acquire
            lock_scope: Scope of the lock
            owner_id: Identifier of the lock owner
            timeout: Lock timeout in seconds
            metadata: Additional metadata for the lock
            
        Returns:
            LockInfo object with lock details
            
        Raises:
            LockTimeoutError: If lock cannot be acquired within timeout
            ConcurrencyError: If there are conflicting locks
        """
        lock_timeout = timeout or self.timeout
        lock_id = str(uuid4())
        start_time = time.time()
        
        logger.debug(
            f"Attempting to acquire {lock_type.value} lock for {lock_scope.value} "
            f"{resource_id} by {owner_id}"
        )
        
        while time.time() - start_time < lock_timeout:
            try:
                # Check for conflicting locks
                conflicting_locks = await self._get_conflicting_locks(
                    resource_id, lock_type, lock_scope, owner_id
                )
                
                if not conflicting_locks:
                    # No conflicts, acquire the lock
                    lock_info = LockInfo(
                        lock_id=lock_id,
                        resource_id=resource_id,
                        lock_type=lock_type,
                        lock_scope=lock_scope,
                        owner_id=owner_id,
                        acquired_at=datetime.utcnow(),
                        expires_at=datetime.utcnow() + timedelta(seconds=lock_timeout),
                        metadata=metadata or {}
                    )
                    
                    await self._store_lock(lock_info)
                    self._locks[lock_id] = lock_info
                    
                    logger.debug(f"Acquired lock {lock_id} for {resource_id}")
                    return lock_info
                
                # Wait before retrying
                await asyncio.sleep(0.1)
                
            except Exception as e:
                logger.error(f"Error acquiring lock for {resource_id}: {str(e)}")
                raise ConcurrencyError(f"Failed to acquire lock: {str(e)}")
        
        raise LockTimeoutError(
            f"Timeout acquiring {lock_type.value} lock for {resource_id}"
        )
    
    async def release_lock(self, lock_info: LockInfo) -> bool:
        """
        Release a previously acquired lock.
        
        Args:
            lock_info: Lock information to release
            
        Returns:
            True if lock was successfully released
        """
        try:
            await self._remove_lock(lock_info.lock_id)
            
            if lock_info.lock_id in self._locks:
                del self._locks[lock_info.lock_id]
            
            logger.debug(f"Released lock {lock_info.lock_id} for {lock_info.resource_id}")
            return True
            
        except Exception as e:
            logger.error(f"Error releasing lock {lock_info.lock_id}: {str(e)}")
            return False
    
    async def _get_conflicting_locks(
        self,
        resource_id: str,
        lock_type: LockType,
        lock_scope: LockScope,
        owner_id: str
    ) -> List[LockInfo]:
        """Get locks that would conflict with the requested lock."""
        # For simplicity, we'll use in-memory tracking
        # In production, this would query a locks table in the database
        conflicting = []
        
        for lock_info in self._locks.values():
            if (lock_info.resource_id == resource_id and 
                lock_info.owner_id != owner_id and
                self._locks_conflict(lock_info.lock_type, lock_type)):
                
                # Check if lock has expired
                if (lock_info.expires_at and 
                    datetime.utcnow() > lock_info.expires_at):
                    # Lock expired, remove it
                    await self._remove_lock(lock_info.lock_id)
                    continue
                
                conflicting.append(lock_info)
        
        return conflicting
    
    def _locks_conflict(self, existing_type: LockType, requested_type: LockType) -> bool:
        """Check if two lock types conflict."""
        if existing_type == LockType.EXCLUSIVE or requested_type == LockType.EXCLUSIVE:
            return True
        
        if existing_type == LockType.WRITE or requested_type == LockType.WRITE:
            return True
        
        # Multiple read locks are allowed
        return False
    
    async def _store_lock(self, lock_info: LockInfo):
        """Store lock information (placeholder for database storage)."""
        # In production, this would insert into a locks table
        pass
    
    async def _remove_lock(self, lock_id: str):
        """Remove lock information (placeholder for database removal)."""
        # In production, this would delete from locks table
        pass


class OptimisticLockManager:
    """
    Optimistic locking manager for handling concurrent modifications.
    
    Uses version numbers and checksums to detect conflicts without
    blocking operations.
    """
    
    def __init__(self, db_session: AsyncSession):
        self.db_session = db_session
    
    async def get_lock_info(self, resource_type: str, resource_id: str) -> OptimisticLockInfo:
        """
        Get current lock information for a resource.
        
        Args:
            resource_type: Type of resource (project, file, etc.)
            resource_id: Unique identifier for the resource
            
        Returns:
            OptimisticLockInfo with current version and metadata
        """
        if resource_type == "project":
            return await self._get_project_lock_info(resource_id)
        elif resource_type == "file":
            return await self._get_file_lock_info(resource_id)
        else:
            raise ValueError(f"Unsupported resource type: {resource_type}")
    
    async def check_and_update(
        self,
        resource_type: str,
        resource_id: str,
        expected_version: int,
        update_func: Callable[[Any], Awaitable[Any]]
    ) -> bool:
        """
        Check version and update resource if no conflicts.
        
        Args:
            resource_type: Type of resource
            resource_id: Resource identifier
            expected_version: Expected version number
            update_func: Function to perform the update
            
        Returns:
            True if update was successful, False if version conflict
            
        Raises:
            ConcurrencyError: If update fails due to concurrency issues
        """
        try:
            current_lock_info = await self.get_lock_info(resource_type, resource_id)
            
            if current_lock_info.version != expected_version:
                logger.warning(
                    f"Version conflict for {resource_type} {resource_id}: "
                    f"expected {expected_version}, got {current_lock_info.version}"
                )
                return False
            
            # Perform the update
            await update_func(resource_id)
            
            # Increment version
            await self._increment_version(resource_type, resource_id)
            
            logger.debug(f"Successfully updated {resource_type} {resource_id}")
            return True
            
        except Exception as e:
            logger.error(f"Error in optimistic update for {resource_id}: {str(e)}")
            raise ConcurrencyError(f"Optimistic lock update failed: {str(e)}")
    
    async def _get_project_lock_info(self, project_id: str) -> OptimisticLockInfo:
        """Get lock info for a project."""
        query = select(Project).where(Project.id == project_id)
        result = await self.db_session.execute(query)
        project = result.scalar_one_or_none()
        
        if not project:
            raise ValueError(f"Project {project_id} not found")
        
        return OptimisticLockInfo(
            resource_id=project_id,
            version=getattr(project, 'version', 1),
            last_modified=project.updated_at,
            checksum=None
        )
    
    async def _get_file_lock_info(self, file_id: str) -> OptimisticLockInfo:
        """Get lock info for a file."""
        query = select(ProjectFile).where(ProjectFile.id == int(file_id))
        result = await self.db_session.execute(query)
        file_record = result.scalar_one_or_none()
        
        if not file_record:
            raise ValueError(f"File {file_id} not found")
        
        return OptimisticLockInfo(
            resource_id=file_id,
            version=getattr(file_record, 'version', 1),
            last_modified=file_record.updated_at,
            checksum=file_record.content_hash
        )
    
    async def _increment_version(self, resource_type: str, resource_id: str):
        """Increment version number for a resource."""
        if resource_type == "project":
            query = update(Project).where(Project.id == resource_id).values(
                updated_at=datetime.utcnow()
                # In production, would also increment version column
            )
        elif resource_type == "file":
            query = update(ProjectFile).where(ProjectFile.id == int(resource_id)).values(
                updated_at=datetime.utcnow()
                # In production, would also increment version column
            )
        else:
            return
        
        await self.db_session.execute(query)


class ConcurrencyManager:
    """
    Main concurrency control manager that coordinates different locking strategies.
    
    Provides high-level interface for managing concurrent access to projects,
    files, and other resources with configurable locking strategies.
    """
    
    def __init__(self, db_session: AsyncSession):
        self.db_session = db_session
        self.distributed_lock = DistributedLock(db_session)
        self.optimistic_lock = OptimisticLockManager(db_session)
        self._operation_locks: Dict[str, asyncio.Lock] = {}
    
    @asynccontextmanager
    async def exclusive_project_access(
        self,
        project_id: str,
        user_id: str,
        timeout: float = 30.0
    ):
        """
        Acquire exclusive access to a project for critical operations.
        
        Args:
            project_id: Project to lock
            user_id: User requesting the lock
            timeout: Lock timeout in seconds
        """
        lock_info = None
        try:
            lock_info = await self.distributed_lock.acquire_lock(
                resource_id=project_id,
                lock_type=LockType.EXCLUSIVE,
                lock_scope=LockScope.PROJECT,
                owner_id=str(user_id),
                timeout=timeout
            )
            
            logger.info(f"Acquired exclusive access to project {project_id} for user {user_id}")
            yield lock_info
            
        finally:
            if lock_info:
                await self.distributed_lock.release_lock(lock_info)
                logger.info(f"Released exclusive access to project {project_id}")
    
    @asynccontextmanager
    async def shared_project_access(
        self,
        project_id: str,
        user_id: str,
        timeout: float = 30.0
    ):
        """
        Acquire shared (read) access to a project.
        
        Args:
            project_id: Project to access
            user_id: User requesting access
            timeout: Lock timeout in seconds
        """
        lock_info = None
        try:
            lock_info = await self.distributed_lock.acquire_lock(
                resource_id=project_id,
                lock_type=LockType.READ,
                lock_scope=LockScope.PROJECT,
                owner_id=str(user_id),
                timeout=timeout
            )
            
            logger.debug(f"Acquired shared access to project {project_id} for user {user_id}")
            yield lock_info
            
        finally:
            if lock_info:
                await self.distributed_lock.release_lock(lock_info)
                logger.debug(f"Released shared access to project {project_id}")
    
    @asynccontextmanager
    async def file_write_access(
        self,
        project_id: str,
        file_path: str,
        user_id: str,
        timeout: float = 30.0
    ):
        """
        Acquire write access to a specific file.
        
        Args:
            project_id: Project containing the file
            file_path: Path to the file
            user_id: User requesting access
            timeout: Lock timeout in seconds
        """
        resource_id = f"{project_id}:{file_path}"
        lock_info = None
        
        try:
            lock_info = await self.distributed_lock.acquire_lock(
                resource_id=resource_id,
                lock_type=LockType.WRITE,
                lock_scope=LockScope.FILE,
                owner_id=str(user_id),
                timeout=timeout,
                metadata={"project_id": project_id, "file_path": file_path}
            )
            
            logger.debug(f"Acquired write access to file {file_path} in project {project_id}")
            yield lock_info
            
        finally:
            if lock_info:
                await self.distributed_lock.release_lock(lock_info)
                logger.debug(f"Released write access to file {file_path}")
    
    async def optimistic_project_update(
        self,
        project_id: str,
        expected_version: int,
        update_func: Callable[[str], Awaitable[Any]]
    ) -> bool:
        """
        Perform optimistic update on a project.
        
        Args:
            project_id: Project to update
            expected_version: Expected version number
            update_func: Function to perform the update
            
        Returns:
            True if update succeeded, False if version conflict
        """
        return await self.optimistic_lock.check_and_update(
            "project", project_id, expected_version, update_func
        )
    
    async def optimistic_file_update(
        self,
        file_id: str,
        expected_version: int,
        update_func: Callable[[str], Awaitable[Any]]
    ) -> bool:
        """
        Perform optimistic update on a file.
        
        Args:
            file_id: File to update
            expected_version: Expected version number
            update_func: Function to perform the update
            
        Returns:
            True if update succeeded, False if version conflict
        """
        return await self.optimistic_lock.check_and_update(
            "file", file_id, expected_version, update_func
        )
    
    async def get_operation_lock(self, operation_key: str) -> asyncio.Lock:
        """
        Get an in-process lock for a specific operation.
        
        Useful for serializing operations within a single application instance.
        
        Args:
            operation_key: Unique key for the operation
            
        Returns:
            asyncio.Lock for the operation
        """
        if operation_key not in self._operation_locks:
            self._operation_locks[operation_key] = asyncio.Lock()
        
        return self._operation_locks[operation_key]
    
    @asynccontextmanager
    async def serialized_operation(self, operation_key: str):
        """
        Execute an operation with serialization within the application instance.
        
        Args:
            operation_key: Unique key for the operation
        """
        operation_lock = await self.get_operation_lock(operation_key)
        
        async with operation_lock:
            logger.debug(f"Executing serialized operation: {operation_key}")
            yield
            logger.debug(f"Completed serialized operation: {operation_key}")
    
    async def cleanup_expired_locks(self):
        """Clean up expired locks from the system."""
        try:
            current_time = datetime.utcnow()
            expired_locks = []
            
            for lock_id, lock_info in self.distributed_lock._locks.items():
                if (lock_info.expires_at and 
                    current_time > lock_info.expires_at):
                    expired_locks.append(lock_info)
            
            for lock_info in expired_locks:
                await self.distributed_lock.release_lock(lock_info)
                logger.info(f"Cleaned up expired lock {lock_info.lock_id}")
            
            if expired_locks:
                logger.info(f"Cleaned up {len(expired_locks)} expired locks")
                
        except Exception as e:
            logger.error(f"Error cleaning up expired locks: {str(e)}")
    
    async def get_active_locks(self, resource_id: Optional[str] = None) -> List[LockInfo]:
        """
        Get information about active locks.
        
        Args:
            resource_id: Optional filter by resource ID
            
        Returns:
            List of active lock information
        """
        active_locks = []
        
        for lock_info in self.distributed_lock._locks.values():
            if resource_id and lock_info.resource_id != resource_id:
                continue
            
            # Check if lock is still valid
            if (not lock_info.expires_at or 
                datetime.utcnow() <= lock_info.expires_at):
                active_locks.append(lock_info)
        
        return active_locks