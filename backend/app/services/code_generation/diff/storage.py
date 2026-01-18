"""
Diff Storage for Terraform Code Changes.

This module provides persistent storage capabilities for generated diffs,
including versioning, search functionality, and integration with generation
job tracking using SQLAlchemy.
"""

import json
from datetime import datetime, timedelta
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Union, Any
from enum import Enum
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, delete, and_, or_, func, text
from sqlalchemy.orm import selectinload

from logconfig.logger import get_logger

logger = get_logger()


class StorageStatus(Enum):
    """Status of stored diff."""
    ACTIVE = "active"
    ARCHIVED = "archived"
    DELETED = "deleted"


class SearchScope(Enum):
    """Scope for diff searches."""
    ALL = "all"
    RECENT = "recent"
    BY_JOB = "by_job"
    BY_FILE = "by_file"
    BY_USER = "by_user"


@dataclass
class DiffRecord:
    """Database record for a stored diff."""
    id: Optional[int] = None
    job_id: Optional[str] = None
    user_id: Optional[str] = None
    source_file: Optional[str] = None
    target_file: Optional[str] = None
    source_hash: str = ""
    target_hash: str = ""
    diff_content: str = ""
    diff_format: str = "unified"
    additions: int = 0
    deletions: int = 0
    changes: int = 0
    risk_score: float = 0.0
    impact_level: str = "low"
    status: StorageStatus = StorageStatus.ACTIVE
    metadata: Dict[str, Any] = field(default_factory=dict)
    tags: List[str] = field(default_factory=list)
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    version: int = 1


@dataclass
class SearchFilters:
    """Filters for diff searches."""
    job_id: Optional[str] = None
    user_id: Optional[str] = None
    source_file: Optional[str] = None
    target_file: Optional[str] = None
    min_changes: Optional[int] = None
    max_risk_score: Optional[float] = None
    impact_level: Optional[str] = None
    status: Optional[StorageStatus] = None
    tags: Optional[List[str]] = None
    date_from: Optional[datetime] = None
    date_to: Optional[datetime] = None
    limit: int = 50
    offset: int = 0


@dataclass
class SearchResult:
    """Result of a diff search operation."""
    records: List[DiffRecord] = field(default_factory=list)
    total_count: int = 0
    has_more: bool = False
    search_time_ms: float = 0.0


class TerraformDiffStorage:
    """
    Persistent storage for Terraform diffs with versioning and search capabilities.

    Integrates with SQLAlchemy for database operations and provides comprehensive
    diff management functionality.
    """

    def __init__(self, db_session: AsyncSession):
        """
        Initialize the diff storage.

        Args:
            db_session: Database session for operations
        """
        self.db = db_session
        self.table_name = "terraform_diffs"
        logger.info("TerraformDiffStorage initialized")

    async def store_diff(
        self,
        diff_content: str,
        source_hash: str,
        target_hash: str,
        job_id: Optional[str] = None,
        user_id: Optional[str] = None,
        source_file: Optional[str] = None,
        target_file: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
        tags: Optional[List[str]] = None,
        additions: int = 0,
        deletions: int = 0,
        changes: int = 0,
        risk_score: float = 0.0,
        impact_level: str = "low"
    ) -> DiffRecord:
        """
        Store a new diff record in the database.

        Args:
            diff_content: The diff content to store
            source_hash: Hash of source content
            target_hash: Hash of target content
            job_id: Associated generation job ID
            user_id: User who generated the diff
            source_file: Source file path
            target_file: Target file path
            metadata: Additional metadata
            tags: Tags for categorization
            additions: Number of additions
            deletions: Number of deletions
            changes: Total changes
            risk_score: Risk score of changes
            impact_level: Impact level assessment

        Returns:
            Stored DiffRecord with generated ID
        """
        import time
        start_time = time.time()

        try:
            # Create record
            record = DiffRecord(
                job_id=job_id,
                user_id=user_id,
                source_file=source_file,
                target_file=target_file,
                source_hash=source_hash,
                target_hash=target_hash,
                diff_content=diff_content,
                diff_format="unified",
                additions=additions,
                deletions=deletions,
                changes=changes,
                risk_score=risk_score,
                impact_level=impact_level,
                status=StorageStatus.ACTIVE,
                metadata=metadata or {},
                tags=tags or [],
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow(),
                version=1
            )

            # Insert into database
            record_id = await self._insert_diff_record(record)
            record.id = record_id

            processing_time = (time.time() - start_time) * 1000
            logger.info(
                f"Stored diff record {record_id} with {changes} changes in {processing_time:.2f}ms"
            )

            return record

        except Exception as e:
            logger.error(f"Failed to store diff: {e}")
            raise

    async def get_diff(self, diff_id: int) -> Optional[DiffRecord]:
        """
        Retrieve a diff record by ID.

        Args:
            diff_id: Diff record ID

        Returns:
            DiffRecord if found, None otherwise
        """
        try:
            query = f"""
                SELECT id, job_id, user_id, source_file, target_file,
                       source_hash, target_hash, diff_content, diff_format,
                       additions, deletions, changes, risk_score, impact_level,
                       status, metadata, tags, created_at, updated_at, version
                FROM {self.table_name}
                WHERE id = $1 AND status != $2
            """

            result = await self.db.execute(text(query), (diff_id, StorageStatus.DELETED.value))
            row = result.fetchone()

            if row:
                return self._row_to_record(row)

            return None

        except Exception as e:
            logger.error(f"Failed to retrieve diff {diff_id}: {e}")
            return None

    async def update_diff(
        self,
        diff_id: int,
        updates: Dict[str, Any]
    ) -> bool:
        """
        Update a diff record.

        Args:
            diff_id: Diff record ID
            updates: Fields to update

        Returns:
            True if update successful
        """
        try:
            # Add updated_at timestamp
            updates["updated_at"] = datetime.utcnow()

            # Build update query
            set_clause = ", ".join(f"{k} = ${i+2}" for i, k in enumerate(updates.keys()))
            query = f"""
                UPDATE {self.table_name}
                SET {set_clause}
                WHERE id = $1
            """

            params = (diff_id,) + tuple(updates.values())
            await self.db.execute(text(query), params)
            await self.db.commit()

            logger.info(f"Updated diff record {diff_id}")
            return True

        except Exception as e:
            logger.error(f"Failed to update diff {diff_id}: {e}")
            await self.db.rollback()
            return False

    async def delete_diff(self, diff_id: int, soft_delete: bool = True) -> bool:
        """
        Delete a diff record.

        Args:
            diff_id: Diff record ID
            soft_delete: If True, mark as deleted instead of hard delete

        Returns:
            True if deletion successful
        """
        try:
            if soft_delete:
                await self.update_diff(diff_id, {"status": StorageStatus.DELETED.value})
            else:
                query = f"DELETE FROM {self.table_name} WHERE id = $1"
                await self.db.execute(text(query), (diff_id,))
                await self.db.commit()

            logger.info(f"Deleted diff record {diff_id}")
            return True

        except Exception as e:
            logger.error(f"Failed to delete diff {diff_id}: {e}")
            await self.db.rollback()
            return False

    async def search_diffs(
        self,
        filters: SearchFilters,
        scope: SearchScope = SearchScope.ALL
    ) -> SearchResult:
        """
        Search for diff records based on filters.

        Args:
            filters: Search filters
            scope: Search scope

        Returns:
            SearchResult with matching records
        """
        import time
        start_time = time.time()

        try:
            # Build query conditions
            conditions = []
            params = []

            if filters.job_id:
                conditions.append("job_id = $" + str(len(params) + 1))
                params.append(filters.job_id)

            if filters.user_id:
                conditions.append("user_id = $" + str(len(params) + 1))
                params.append(filters.user_id)

            if filters.source_file:
                conditions.append("source_file LIKE $" + str(len(params) + 1))
                params.append(f"%{filters.source_file}%")

            if filters.target_file:
                conditions.append("target_file LIKE $" + str(len(params) + 1))
                params.append(f"%{filters.target_file}%")

            if filters.min_changes is not None:
                conditions.append("changes >= $" + str(len(params) + 1))
                params.append(filters.min_changes)

            if filters.max_risk_score is not None:
                conditions.append("risk_score <= $" + str(len(params) + 1))
                params.append(filters.max_risk_score)

            if filters.impact_level:
                conditions.append("impact_level = $" + str(len(params) + 1))
                params.append(filters.impact_level)

            if filters.status:
                conditions.append("status = $" + str(len(params) + 1))
                params.append(filters.status.value)

            if filters.date_from:
                conditions.append("created_at >= $" + str(len(params) + 1))
                params.append(filters.date_from)

            if filters.date_to:
                conditions.append("created_at <= $" + str(len(params) + 1))
                params.append(filters.date_to)

            # Exclude deleted records by default
            conditions.append("status != $" + str(len(params) + 1))
            params.append(StorageStatus.DELETED.value)

            # Build WHERE clause
            where_clause = " AND ".join(conditions) if conditions else "1=1"

            # Build ORDER BY based on scope
            order_by = "created_at DESC"
            if scope == SearchScope.RECENT:
                # Already descending by created_at
                pass

            # Build query
            query = f"""
                SELECT id, job_id, user_id, source_file, target_file,
                       source_hash, target_hash, diff_content, diff_format,
                       additions, deletions, changes, risk_score, impact_level,
                       status, metadata, tags, created_at, updated_at, version
                FROM {self.table_name}
                WHERE {where_clause}
                ORDER BY {order_by}
                LIMIT ${len(params) + 1} OFFSET ${len(params) + 2}
            """

            params.extend([filters.limit, filters.offset])

            # Execute query
            result = await self.db.execute(text(query), tuple(params))
            rows = result.fetchall()

            # Get total count
            count_query = f"""
                SELECT COUNT(*) FROM {self.table_name}
                WHERE {where_clause}
            """
            count_result = await self.db.execute(text(count_query), tuple(params[:-2]))
            total_count = count_result.scalar()

            # Convert rows to records
            records = [self._row_to_record(row) for row in rows]

            processing_time = (time.time() - start_time) * 1000

            return SearchResult(
                records=records,
                total_count=total_count,
                has_more=(filters.offset + len(records)) < total_count,
                search_time_ms=processing_time
            )

        except Exception as e:
            logger.error(f"Diff search failed: {e}")
            processing_time = (time.time() - start_time) * 1000
            return SearchResult(search_time_ms=processing_time)

    async def get_diff_history(
        self,
        job_id: str,
        limit: int = 10
    ) -> List[DiffRecord]:
        """
        Get diff history for a specific job.

        Args:
            job_id: Generation job ID
            limit: Maximum number of records to return

        Returns:
            List of diff records for the job
        """
        filters = SearchFilters(
            job_id=job_id,
            limit=limit,
            status=StorageStatus.ACTIVE
        )

        result = await self.search_diffs(filters, SearchScope.BY_JOB)
        return result.records

    async def get_user_diffs(
        self,
        user_id: str,
        limit: int = 20,
        offset: int = 0
    ) -> SearchResult:
        """
        Get diffs for a specific user.

        Args:
            user_id: User ID
            limit: Maximum number of records
            offset: Pagination offset

        Returns:
            SearchResult with user's diffs
        """
        filters = SearchFilters(
            user_id=user_id,
            limit=limit,
            offset=offset,
            status=StorageStatus.ACTIVE
        )

        return await self.search_diffs(filters, SearchScope.BY_USER)

    async def archive_old_diffs(self, days_old: int = 30) -> int:
        """
        Archive diffs older than specified days.

        Args:
            days_old: Number of days after which to archive

        Returns:
            Number of diffs archived
        """
        try:
            cutoff_date = datetime.utcnow() - timedelta(days=days_old)

            query = f"""
                UPDATE {self.table_name}
                SET status = $1, updated_at = $2
                WHERE created_at < $3 AND status = $4
            """

            result = await self.db.execute(text(query), (
                StorageStatus.ARCHIVED.value,
                datetime.utcnow(),
                cutoff_date,
                StorageStatus.ACTIVE.value
            ))

            archived_count = result.rowcount
            await self.db.commit()

            logger.info(f"Archived {archived_count} diffs older than {days_old} days")
            return archived_count

        except Exception as e:
            logger.error(f"Failed to archive old diffs: {e}")
            await self.db.rollback()
            return 0

    async def get_storage_stats(self) -> Dict[str, Any]:
        """
        Get storage statistics.

        Returns:
            Dictionary with storage statistics
        """
        try:
            # Get counts by status
            status_query = f"""
                SELECT status, COUNT(*) as count
                FROM {self.table_name}
                GROUP BY status
            """

            status_result = await self.db.execute(text(status_query))
            status_counts = {row[0]: row[1] for row in status_result.fetchall()}

            # Get total statistics
            stats_query = f"""
                SELECT
                    COUNT(*) as total_diffs,
                    AVG(changes) as avg_changes,
                    AVG(risk_score) as avg_risk,
                    SUM(additions) as total_additions,
                    SUM(deletions) as total_deletions,
                    MAX(created_at) as latest_diff
                FROM {self.table_name}
                WHERE status != $1
            """

            stats_result = await self.db.execute(text(stats_query), (StorageStatus.DELETED.value,))
            stats_row = stats_result.fetchone()

            return {
                "status": "operational",
                "total_diffs": stats_row[0] if stats_row[0] else 0,
                "avg_changes_per_diff": float(stats_row[1]) if stats_row[1] else 0.0,
                "avg_risk_score": float(stats_row[2]) if stats_row[2] else 0.0,
                "total_additions": stats_row[3] if stats_row[3] else 0,
                "total_deletions": stats_row[4] if stats_row[4] else 0,
                "latest_diff": stats_row[5].isoformat() if stats_row[5] else None,
                "status_breakdown": status_counts
            }

        except Exception as e:
            logger.error(f"Failed to get storage stats: {e}")
            return {"status": "error", "error": str(e)}

    async def _insert_diff_record(self, record: DiffRecord) -> int:
        """Insert a diff record and return the ID."""
        query = f"""
            INSERT INTO {self.table_name}
            (job_id, user_id, source_file, target_file, source_hash, target_hash,
             diff_content, diff_format, additions, deletions, changes, risk_score,
             impact_level, status, metadata, tags, created_at, updated_at, version)
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14, $15, $16, $17, $18, $19)
            RETURNING id
        """

        params = (
            record.job_id, record.user_id, record.source_file, record.target_file,
            record.source_hash, record.target_hash, record.diff_content, record.diff_format,
            record.additions, record.deletions, record.changes, record.risk_score,
            record.impact_level, record.status.value, json.dumps(record.metadata),
            record.tags, record.created_at, record.updated_at, record.version
        )

        result = await self.db.execute(text(query), params)
        record_id = result.scalar()
        await self.db.commit()

        return record_id

    def _row_to_record(self, row) -> DiffRecord:
        """Convert database row to DiffRecord."""
        return DiffRecord(
            id=row[0],
            job_id=row[1],
            user_id=row[2],
            source_file=row[3],
            target_file=row[4],
            source_hash=row[5],
            target_hash=row[6],
            diff_content=row[7],
            diff_format=row[8],
            additions=row[9],
            deletions=row[10],
            changes=row[11],
            risk_score=float(row[12]),
            impact_level=row[13],
            status=StorageStatus(row[14]),
            metadata=json.loads(row[15]) if row[15] else {},
            tags=row[16] if row[16] else [],
            created_at=row[17],
            updated_at=row[18],
            version=row[19]
        )