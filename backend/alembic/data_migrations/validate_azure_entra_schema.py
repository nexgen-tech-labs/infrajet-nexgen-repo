#!/usr/bin/env python3
"""
Database schema validation script for Azure Entra ID integration.

This script validates that all required database changes for Azure Entra ID
integration have been properly applied, including tables, columns, indexes,
and constraints.

Usage:
    python alembic/data_migrations/validate_azure_entra_schema.py
"""

import os
import sys
from typing import List, Dict, Any, Optional

# Add the project root to the path
sys.path.append(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
)

from sqlalchemy import create_engine, text, inspect
from sqlalchemy.orm import sessionmaker
from app.core.settings import get_settings
from logconfig.logger import get_logger

logger = get_logger()


class SchemaValidator:
    """Validator for Azure Entra database schema."""

    def __init__(self, database_url: str):
        """Initialize the schema validator."""
        self.engine = create_engine(database_url)
        self.SessionLocal = sessionmaker(
            autocommit=False, autoflush=False, bind=self.engine
        )
        self.inspector = inspect(self.engine)

    def validate_table_exists(self, table_name: str) -> bool:
        """Validate that a table exists."""
        tables = self.inspector.get_table_names()
        exists = table_name in tables

        if exists:
            logger.info(f"✓ Table '{table_name}' exists")
        else:
            logger.error(f"✗ Table '{table_name}' does not exist")

        return exists

    def validate_column_exists(
        self, table_name: str, column_name: str, expected_type: Optional[str] = None
    ) -> bool:
        """Validate that a column exists in a table."""
        try:
            columns = self.inspector.get_columns(table_name)
            column_names = [col["name"] for col in columns]

            if column_name not in column_names:
                logger.error(
                    f"✗ Column '{column_name}' does not exist in table '{table_name}'"
                )
                return False

            # Check column type if specified
            if expected_type:
                column_info = next(
                    (col for col in columns if col["name"] == column_name), None
                )
                if column_info:
                    actual_type = str(column_info["type"]).upper()
                    if expected_type.upper() not in actual_type:
                        logger.warning(
                            f"⚠ Column '{column_name}' type is '{actual_type}', expected '{expected_type}'"
                        )

            logger.info(f"✓ Column '{table_name}.{column_name}' exists")
            return True

        except Exception as e:
            logger.error(f"✗ Error checking column '{table_name}.{column_name}': {e}")
            return False

    def validate_index_exists(self, table_name: str, index_name: str) -> bool:
        """Validate that an index exists."""
        try:
            indexes = self.inspector.get_indexes(table_name)
            index_names = [idx["name"] for idx in indexes]

            exists = index_name in index_names

            if exists:
                logger.info(f"✓ Index '{index_name}' exists on table '{table_name}'")
            else:
                logger.error(
                    f"✗ Index '{index_name}' does not exist on table '{table_name}'"
                )

            return exists

        except Exception as e:
            logger.error(
                f"✗ Error checking index '{index_name}' on table '{table_name}': {e}"
            )
            return False

    def validate_foreign_key_exists(
        self, table_name: str, column_name: str, referenced_table: str
    ) -> bool:
        """Validate that a foreign key constraint exists."""
        try:
            foreign_keys = self.inspector.get_foreign_keys(table_name)

            for fk in foreign_keys:
                if (
                    column_name in fk["constrained_columns"]
                    and fk["referred_table"] == referenced_table
                ):
                    logger.info(
                        f"✓ Foreign key '{table_name}.{column_name}' -> '{referenced_table}' exists"
                    )
                    return True

            logger.error(
                f"✗ Foreign key '{table_name}.{column_name}' -> '{referenced_table}' does not exist"
            )
            return False

        except Exception as e:
            logger.error(
                f"✗ Error checking foreign key '{table_name}.{column_name}': {e}"
            )
            return False

    def validate_users_table_schema(self) -> bool:
        """Validate the users table schema for Azure Entra integration."""
        logger.info("Validating users table schema...")

        all_valid = True

        # Check table exists
        all_valid &= self.validate_table_exists("users")

        # Check Azure Entra columns
        azure_columns = [
            ("azure_entra_id", "VARCHAR"),
            ("azure_tenant_id", "VARCHAR"),
            ("azure_access_token_hash", "VARCHAR"),
            ("azure_refresh_token_hash", "VARCHAR"),
            ("azure_token_expires_at", "TIMESTAMP"),
            ("profile_picture_url", "VARCHAR"),
            ("organization", "VARCHAR"),
            ("department", "VARCHAR"),
        ]

        for column_name, expected_type in azure_columns:
            all_valid &= self.validate_column_exists(
                "users", column_name, expected_type
            )

        # Check GitHub integration columns
        github_columns = [
            ("github_username", "VARCHAR"),
            ("github_access_token_hash", "VARCHAR"),
            ("github_connected_at", "TIMESTAMP"),
        ]

        for column_name, expected_type in github_columns:
            all_valid &= self.validate_column_exists(
                "users", column_name, expected_type
            )

        # Check essential indexes
        user_indexes = [
            "ix_users_azure_entra_id",
            "ix_users_email",
            "ix_users_id",
        ]

        for index_name in user_indexes:
            all_valid &= self.validate_index_exists("users", index_name)

        return all_valid

    def validate_github_sync_records_table(self) -> bool:
        """Validate the github_sync_records table schema."""
        logger.info("Validating github_sync_records table schema...")

        all_valid = True

        # Check table exists
        all_valid &= self.validate_table_exists("github_sync_records")

        # Check required columns
        required_columns = [
            ("id", "INTEGER"),
            ("project_id", "VARCHAR"),
            ("user_id", "INTEGER"),
            ("github_repository", "VARCHAR"),
            ("last_sync_at", "TIMESTAMP"),
            ("sync_status", "VARCHAR"),
            ("last_commit_sha", "VARCHAR"),
            ("sync_errors", "TEXT"),
            ("files_synced_count", "INTEGER"),
            ("conflicts_resolved_count", "INTEGER"),
            ("sync_duration_seconds", "INTEGER"),
            ("retry_count", "INTEGER"),
            ("branch_name", "VARCHAR"),
            ("created_at", "TIMESTAMP"),
            ("updated_at", "TIMESTAMP"),
        ]

        for column_name, expected_type in required_columns:
            all_valid &= self.validate_column_exists(
                "github_sync_records", column_name, expected_type
            )

        # Check foreign keys
        all_valid &= self.validate_foreign_key_exists(
            "github_sync_records", "user_id", "users"
        )
        all_valid &= self.validate_foreign_key_exists(
            "github_sync_records", "project_id", "projects"
        )

        return all_valid

    def validate_websocket_sessions_table(self) -> bool:
        """Validate the websocket_sessions table schema."""
        logger.info("Validating websocket_sessions table schema...")

        all_valid = True

        # Check table exists
        all_valid &= self.validate_table_exists("websocket_sessions")

        # Check required columns
        required_columns = [
            ("id", "INTEGER"),
            ("session_id", "VARCHAR"),
            ("user_id", "INTEGER"),
            ("connected_at", "TIMESTAMP"),
            ("last_heartbeat", "TIMESTAMP"),
            ("session_metadata", "JSON"),
            ("is_active", "BOOLEAN"),
            ("disconnected_at", "TIMESTAMP"),
            ("ip_address", "VARCHAR"),
            ("user_agent", "TEXT"),
            ("created_at", "TIMESTAMP"),
            ("updated_at", "TIMESTAMP"),
        ]

        for column_name, expected_type in required_columns:
            all_valid &= self.validate_column_exists(
                "websocket_sessions", column_name, expected_type
            )

        # Check foreign keys
        all_valid &= self.validate_foreign_key_exists(
            "websocket_sessions", "user_id", "users"
        )

        # Check unique index on session_id
        all_valid &= self.validate_index_exists(
            "websocket_sessions", "ix_websocket_sessions_session_id"
        )

        return all_valid

    def validate_user_preferences_table(self) -> bool:
        """Validate the user_preferences table schema."""
        logger.info("Validating user_preferences table schema...")

        all_valid = True

        # Check table exists
        all_valid &= self.validate_table_exists("user_preferences")

        # Check required columns
        required_columns = [
            ("id", "INTEGER"),
            ("user_id", "INTEGER"),
            ("theme", "VARCHAR"),
            ("language", "VARCHAR"),
            ("timezone", "VARCHAR"),
            ("email_notifications", "BOOLEAN"),
            ("realtime_updates", "BOOLEAN"),
            ("auto_sync_github", "BOOLEAN"),
            ("additional_settings", "JSON"),
            ("created_at", "TIMESTAMP"),
            ("updated_at", "TIMESTAMP"),
        ]

        for column_name, expected_type in required_columns:
            all_valid &= self.validate_column_exists(
                "user_preferences", column_name, expected_type
            )

        # Check foreign keys
        all_valid &= self.validate_foreign_key_exists(
            "user_preferences", "user_id", "users"
        )

        return all_valid

    def validate_performance_indexes(self) -> bool:
        """Validate that performance optimization indexes exist."""
        logger.info("Validating performance optimization indexes...")

        all_valid = True

        # Users table performance indexes
        user_performance_indexes = [
            "ix_users_azure_tenant_id",
            "ix_users_azure_token_expires_at",
            "ix_users_github_username",
            "ix_users_last_login",
            "ix_users_organization",
            "ix_users_active_azure",
            "ix_users_github_connected",
        ]

        for index_name in user_performance_indexes:
            # Note: Some indexes might not exist yet if the performance migration hasn't been run
            exists = self.validate_index_exists("users", index_name)
            if not exists:
                logger.warning(
                    f"⚠ Performance index '{index_name}' missing - run performance migration"
                )

        # GitHub sync records performance indexes
        github_performance_indexes = [
            "ix_github_sync_records_sync_status",
            "ix_github_sync_records_last_sync_at",
            "ix_github_sync_records_user_project",
            "ix_github_sync_records_repository",
            "ix_github_sync_records_branch",
        ]

        for index_name in github_performance_indexes:
            exists = self.validate_index_exists("github_sync_records", index_name)
            if not exists:
                logger.warning(
                    f"⚠ Performance index '{index_name}' missing - run performance migration"
                )

        return all_valid

    def validate_data_integrity(self) -> bool:
        """Validate data integrity constraints."""
        logger.info("Validating data integrity...")

        all_valid = True

        with self.SessionLocal() as session:
            try:
                # Check for users with Azure Entra ID but no tenant ID
                result = session.execute(
                    text(
                        """
                    SELECT COUNT(*) 
                    FROM users 
                    WHERE azure_entra_id IS NOT NULL 
                    AND azure_tenant_id IS NULL
                """
                    )
                )

                count = result.scalar()
                if count > 0:
                    logger.warning(
                        f"⚠ Found {count} users with Azure Entra ID but no tenant ID"
                    )
                else:
                    logger.info("✓ All Azure Entra users have tenant IDs")

                # Check for orphaned GitHub sync records
                result = session.execute(
                    text(
                        """
                    SELECT COUNT(*) 
                    FROM github_sync_records gsr
                    LEFT JOIN users u ON gsr.user_id = u.id
                    WHERE u.id IS NULL
                """
                    )
                )

                count = result.scalar()
                if count > 0:
                    logger.error(f"✗ Found {count} orphaned GitHub sync records")
                    all_valid = False
                else:
                    logger.info("✓ No orphaned GitHub sync records found")

                # Check for orphaned WebSocket sessions
                result = session.execute(
                    text(
                        """
                    SELECT COUNT(*) 
                    FROM websocket_sessions ws
                    LEFT JOIN users u ON ws.user_id = u.id
                    WHERE u.id IS NULL
                """
                    )
                )

                count = result.scalar()
                if count > 0:
                    logger.error(f"✗ Found {count} orphaned WebSocket sessions")
                    all_valid = False
                else:
                    logger.info("✓ No orphaned WebSocket sessions found")

            except Exception as e:
                logger.error(f"✗ Error validating data integrity: {e}")
                all_valid = False

        return all_valid

    def run_full_validation(self) -> bool:
        """Run complete schema validation."""
        logger.info("Starting comprehensive Azure Entra schema validation...")

        all_valid = True

        # Validate all table schemas
        all_valid &= self.validate_users_table_schema()
        all_valid &= self.validate_github_sync_records_table()
        all_valid &= self.validate_websocket_sessions_table()
        all_valid &= self.validate_user_preferences_table()

        # Validate performance indexes (warnings only)
        self.validate_performance_indexes()

        # Validate data integrity
        all_valid &= self.validate_data_integrity()

        if all_valid:
            logger.info("🎉 All schema validations passed!")
        else:
            logger.error(
                "❌ Some schema validations failed. Please check the logs above."
            )

        return all_valid


def main():
    """Main function to run the validation."""
    import argparse

    parser = argparse.ArgumentParser(description="Validate Azure Entra database schema")
    parser.add_argument("--database-url", help="Database URL (defaults to settings)")

    args = parser.parse_args()

    # Get database URL
    settings = get_settings()
    database_url = args.database_url or settings.DATABASE_URL

    # Convert asyncpg URL to psycopg2 for synchronous operations
    if database_url and "postgresql+asyncpg://" in database_url:
        database_url = database_url.replace(
            "postgresql+asyncpg://", "postgresql+psycopg2://"
        )
    if not database_url:
        logger.error("Database URL not provided and not found in settings")
        sys.exit(1)

    # Initialize validator
    validator = SchemaValidator(database_url)

    # Run validation
    success = validator.run_full_validation()

    if not success:
        sys.exit(1)


if __name__ == "__main__":
    main()
