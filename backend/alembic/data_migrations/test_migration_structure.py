#!/usr/bin/env python3
"""
Test script to validate migration file structure without database connection.

This script validates that all migration files are properly structured and
contain the expected schema changes for Azure Entra ID integration.
"""

import os
import sys
from pathlib import Path

# Add the project root to the path
sys.path.append(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
)

from logconfig.logger import get_logger

logger = get_logger()


class MigrationStructureValidator:
    """Validator for migration file structure."""

    def __init__(self):
        """Initialize the validator."""
        self.alembic_versions_dir = Path(__file__).parent.parent / "versions"
        self.data_migrations_dir = Path(__file__).parent

    def validate_migration_files_exist(self) -> bool:
        """Validate that all expected migration files exist."""
        logger.info("Validating migration files exist...")

        all_valid = True

        # Expected migration files (partial names to match)
        expected_migrations = [
            "add_azure_entra_fields_to_users",
            "add_github_sync_records_table",
            "add_user_preferences_and_websocket",
            "add_performance_indexes_for_azure_entra",
        ]

        migration_files = list(self.alembic_versions_dir.glob("*.py"))
        migration_names = [f.name for f in migration_files]

        for expected in expected_migrations:
            found = any(expected in name for name in migration_names)
            if found:
                logger.info(f"✓ Found migration for: {expected}")
            else:
                logger.error(f"✗ Missing migration for: {expected}")
                all_valid = False

        return all_valid

    def validate_azure_entra_migration_content(self) -> bool:
        """Validate Azure Entra migration contains expected changes."""
        logger.info("Validating Azure Entra migration content...")

        migration_file = None
        for file in self.alembic_versions_dir.glob(
            "*add_azure_entra_fields_to_users*.py"
        ):
            migration_file = file
            break

        if not migration_file:
            logger.error("✗ Azure Entra migration file not found")
            return False

        content = migration_file.read_text(encoding="utf-8")

        # Check for expected Azure Entra columns
        expected_columns = [
            "azure_entra_id",
            "azure_tenant_id",
            "azure_access_token_hash",
            "azure_refresh_token_hash",
            "azure_token_expires_at",
            "profile_picture_url",
            "organization",
            "department",
            "github_username",
            "github_access_token_hash",
            "github_connected_at",
        ]

        all_valid = True
        for column in expected_columns:
            if column in content:
                logger.info(f"✓ Found column: {column}")
            else:
                logger.error(f"✗ Missing column: {column}")
                all_valid = False

        # Check for password removal
        if "drop_column('users', 'hashed_password')" in content:
            logger.info("✓ Password column removal found")
        else:
            logger.warning("⚠ Password column removal not found")

        return all_valid

    def validate_github_sync_migration_content(self) -> bool:
        """Validate GitHub sync migration contains expected changes."""
        logger.info("Validating GitHub sync migration content...")

        migration_file = None
        for file in self.alembic_versions_dir.glob(
            "*add_github_sync_records_table*.py"
        ):
            migration_file = file
            break

        if not migration_file:
            logger.error("✗ GitHub sync migration file not found")
            return False

        content = migration_file.read_text(encoding="utf-8")

        # Check for expected table creation
        if "github_sync_records" in content and "create_table" in content:
            logger.info("✓ GitHub sync records table creation found")
        else:
            logger.error("✗ GitHub sync records table creation not found")
            return False

        # Check for expected columns
        expected_columns = [
            "project_id",
            "user_id",
            "github_repository",
            "sync_status",
            "last_commit_sha",
        ]

        all_valid = True
        for column in expected_columns:
            if column in content:
                logger.info(f"✓ Found column: {column}")
            else:
                logger.error(f"✗ Missing column: {column}")
                all_valid = False

        return all_valid

    def validate_websocket_migration_content(self) -> bool:
        """Validate WebSocket migration contains expected changes."""
        logger.info("Validating WebSocket migration content...")

        migration_file = None
        for file in self.alembic_versions_dir.glob("*websocket*.py"):
            migration_file = file
            break

        if not migration_file:
            logger.error("✗ WebSocket migration file not found")
            return False

        content = migration_file.read_text(encoding="utf-8")

        # Check for WebSocket sessions table
        if "create_table('websocket_sessions'" in content:
            logger.info("✓ WebSocket sessions table creation found")
        else:
            logger.error("✗ WebSocket sessions table creation not found")
            return False

        # Check for user preferences table
        if "create_table('user_preferences'" in content:
            logger.info("✓ User preferences table creation found")
        else:
            logger.error("✗ User preferences table creation not found")
            return False

        return True

    def validate_performance_indexes_migration(self) -> bool:
        """Validate performance indexes migration contains expected indexes."""
        logger.info("Validating performance indexes migration...")

        migration_file = None
        for file in self.alembic_versions_dir.glob("*performance_indexes*.py"):
            migration_file = file
            break

        if not migration_file:
            logger.error("✗ Performance indexes migration file not found")
            return False

        content = migration_file.read_text(encoding="utf-8")

        # Check for expected indexes
        expected_indexes = [
            "ix_users_azure_tenant_id",
            "ix_users_azure_token_expires_at",
            "ix_users_github_username",
            "ix_github_sync_records_sync_status",
            "ix_websocket_sessions_user_active",
        ]

        all_valid = True
        for index in expected_indexes:
            if index in content:
                logger.info(f"✓ Found index: {index}")
            else:
                logger.error(f"✗ Missing index: {index}")
                all_valid = False

        return all_valid

    def validate_data_migration_scripts(self) -> bool:
        """Validate data migration scripts exist and are properly structured."""
        logger.info("Validating data migration scripts...")

        all_valid = True

        # Check for user migration script
        user_migration_script = (
            self.data_migrations_dir / "migrate_existing_users_to_azure_entra.py"
        )
        if user_migration_script.exists():
            logger.info("✓ User migration script exists")

            content = user_migration_script.read_text(encoding="utf-8")
            if "UserMigrationService" in content:
                logger.info("✓ User migration service class found")
            else:
                logger.error("✗ User migration service class not found")
                all_valid = False
        else:
            logger.error("✗ User migration script not found")
            all_valid = False

        # Check for validation script
        validation_script = self.data_migrations_dir / "validate_azure_entra_schema.py"
        if validation_script.exists():
            logger.info("✓ Schema validation script exists")

            content = validation_script.read_text(encoding="utf-8")
            if "SchemaValidator" in content:
                logger.info("✓ Schema validator class found")
            else:
                logger.error("✗ Schema validator class not found")
                all_valid = False
        else:
            logger.error("✗ Schema validation script not found")
            all_valid = False

        # Check for README
        readme_file = self.data_migrations_dir / "README.md"
        if readme_file.exists():
            logger.info("✓ Migration README exists")
        else:
            logger.warning("⚠ Migration README not found")

        return all_valid

    def run_full_validation(self) -> bool:
        """Run complete migration structure validation."""
        logger.info("Starting comprehensive migration structure validation...")

        all_valid = True

        # Validate all components
        all_valid &= self.validate_migration_files_exist()
        all_valid &= self.validate_azure_entra_migration_content()
        all_valid &= self.validate_github_sync_migration_content()
        all_valid &= self.validate_websocket_migration_content()
        all_valid &= self.validate_performance_indexes_migration()
        all_valid &= self.validate_data_migration_scripts()

        if all_valid:
            logger.info("🎉 All migration structure validations passed!")
            logger.info(
                "Migration files are properly structured and ready for deployment."
            )
        else:
            logger.error("❌ Some migration structure validations failed.")

        return all_valid


def main():
    """Main function to run the validation."""
    validator = MigrationStructureValidator()
    success = validator.run_full_validation()

    if not success:
        sys.exit(1)

    logger.info("Migration structure validation completed successfully!")


if __name__ == "__main__":
    main()
