#!/usr/bin/env python3
"""
Data migration script for existing users to Azure Entra ID system.

This script helps migrate existing users from password-based authentication
to Azure Entra ID authentication system. It should be run after the schema
migrations have been applied.

Usage:
    python alembic/data_migrations/migrate_existing_users_to_azure_entra.py

Requirements:
    - Database schema must be up to date with Azure Entra fields
    - Existing users should have valid email addresses
    - Azure Entra tenant should be configured
"""

import os
import sys
from datetime import datetime
from typing import List, Optional

# Add the project root to the path
sys.path.append(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
)

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from app.models.user import User, UserPreferences
from app.core.settings import get_settings
from logconfig.logger import get_logger

logger = get_logger()


class UserMigrationService:
    """Service for migrating existing users to Azure Entra system."""

    def __init__(self, database_url: str):
        """Initialize the migration service."""
        self.engine = create_engine(database_url)
        self.SessionLocal = sessionmaker(
            autocommit=False, autoflush=False, bind=self.engine
        )

    def get_existing_users_without_azure_entra(self) -> List[User]:
        """Get all users that don't have Azure Entra ID configured."""
        with self.SessionLocal() as session:
            users = (
                session.query(User)
                .filter(User.azure_entra_id.is_(None), User.is_active == True)
                .all()
            )
            return users

    def create_user_preferences_if_missing(self, user: User) -> None:
        """Create default user preferences if they don't exist."""
        with self.SessionLocal() as session:
            # Refresh the user object in this session
            user = session.merge(user)

            if not user.preferences:
                preferences = UserPreferences(
                    user_id=user.id,
                    theme="light",
                    language="en",
                    timezone="UTC",
                    email_notifications=True,
                    realtime_updates=True,
                    auto_sync_github=False,
                )
                session.add(preferences)
                session.commit()
                logger.info(f"Created default preferences for user {user.email}")

    def mark_user_for_azure_migration(self, user: User) -> None:
        """Mark user as requiring Azure Entra migration."""
        with self.SessionLocal() as session:
            # Refresh the user object in this session
            user = session.merge(user)

            # Add a note in the organization field to indicate migration needed
            if not user.organization:
                user.organization = "MIGRATION_REQUIRED"

            # Update the user record
            user.updated_at = datetime.utcnow()
            session.commit()
            logger.info(f"Marked user {user.email} for Azure Entra migration")

    def cleanup_legacy_authentication_data(self) -> None:
        """Clean up any remaining legacy authentication data."""
        with self.SessionLocal() as session:
            # Check if hashed_password column still exists
            try:
                result = session.execute(
                    text(
                        """
                    SELECT column_name 
                    FROM information_schema.columns 
                    WHERE table_name = 'users' AND column_name = 'hashed_password'
                """
                    )
                )

                if result.fetchone():
                    logger.warning(
                        "hashed_password column still exists. This should have been removed by migration."
                    )
                else:
                    logger.info("Legacy password column has been properly removed.")

            except Exception as e:
                logger.error(f"Error checking for legacy columns: {e}")

    def validate_migration_readiness(self) -> bool:
        """Validate that the database is ready for Azure Entra migration."""
        with self.SessionLocal() as session:
            try:
                # Check if Azure Entra columns exist
                result = session.execute(
                    text(
                        """
                    SELECT column_name 
                    FROM information_schema.columns 
                    WHERE table_name = 'users' 
                    AND column_name IN ('azure_entra_id', 'azure_tenant_id', 'azure_access_token_hash')
                """
                    )
                )

                columns = [row[0] for row in result.fetchall()]
                required_columns = [
                    "azure_entra_id",
                    "azure_tenant_id",
                    "azure_access_token_hash",
                ]

                missing_columns = set(required_columns) - set(columns)
                if missing_columns:
                    logger.error(
                        f"Missing required Azure Entra columns: {missing_columns}"
                    )
                    return False

                # Check if GitHub sync records table exists
                result = session.execute(
                    text(
                        """
                    SELECT table_name 
                    FROM information_schema.tables 
                    WHERE table_name = 'github_sync_records'
                """
                    )
                )

                if not result.fetchone():
                    logger.error("github_sync_records table does not exist")
                    return False

                # Check if WebSocket sessions table exists
                result = session.execute(
                    text(
                        """
                    SELECT table_name 
                    FROM information_schema.tables 
                    WHERE table_name = 'websocket_sessions'
                """
                    )
                )

                if not result.fetchone():
                    logger.error("websocket_sessions table does not exist")
                    return False

                logger.info("Database schema validation passed")
                return True

            except Exception as e:
                logger.error(f"Error validating migration readiness: {e}")
                return False

    def generate_migration_report(self) -> dict:
        """Generate a report of the migration status."""
        with self.SessionLocal() as session:
            # Count total users
            total_users = session.query(User).count()

            # Count users with Azure Entra ID
            azure_users = (
                session.query(User).filter(User.azure_entra_id.isnot(None)).count()
            )

            # Count users without Azure Entra ID
            legacy_users = (
                session.query(User).filter(User.azure_entra_id.is_(None)).count()
            )

            # Count users with GitHub connected
            github_users = (
                session.query(User).filter(User.github_username.isnot(None)).count()
            )

            # Count active users
            active_users = session.query(User).filter(User.is_active == True).count()

            # Count users with preferences
            users_with_preferences = session.query(User).join(UserPreferences).count()

            report = {
                "total_users": total_users,
                "azure_entra_users": azure_users,
                "legacy_users": legacy_users,
                "github_connected_users": github_users,
                "active_users": active_users,
                "users_with_preferences": users_with_preferences,
                "migration_completion_percentage": (
                    (azure_users / total_users * 100) if total_users > 0 else 0
                ),
            }

            return report

    def run_migration(self, dry_run: bool = True) -> None:
        """Run the complete migration process."""
        logger.info("Starting Azure Entra user migration process")

        # Validate migration readiness
        if not self.validate_migration_readiness():
            logger.error(
                "Database is not ready for migration. Please run schema migrations first."
            )
            return

        # Get users that need migration
        users_to_migrate = self.get_existing_users_without_azure_entra()
        logger.info(
            f"Found {len(users_to_migrate)} users that need Azure Entra migration"
        )

        if dry_run:
            logger.info("DRY RUN MODE - No changes will be made")

        # Process each user
        for user in users_to_migrate:
            logger.info(f"Processing user: {user.email}")

            if not dry_run:
                # Create user preferences if missing
                self.create_user_preferences_if_missing(user)

                # Mark user for Azure migration
                self.mark_user_for_azure_migration(user)

        # Clean up legacy data
        if not dry_run:
            self.cleanup_legacy_authentication_data()

        # Generate migration report
        report = self.generate_migration_report()
        logger.info("Migration Report:")
        for key, value in report.items():
            logger.info(f"  {key}: {value}")

        if dry_run:
            logger.info(
                "Migration completed in DRY RUN mode. Run with --execute to apply changes."
            )
        else:
            logger.info("Migration completed successfully!")


def main():
    """Main function to run the migration."""
    import argparse

    parser = argparse.ArgumentParser(
        description="Migrate existing users to Azure Entra ID system"
    )
    parser.add_argument(
        "--execute",
        action="store_true",
        help="Execute the migration (default is dry run)",
    )
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

    # Initialize migration service
    migration_service = UserMigrationService(database_url)

    # Run migration
    dry_run = not args.execute
    migration_service.run_migration(dry_run=dry_run)


if __name__ == "__main__":
    main()
