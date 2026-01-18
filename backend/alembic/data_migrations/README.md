# Azure Entra ID Database Migration Guide

This directory contains data migration scripts and utilities for migrating the existing infrastructure code generation system to use Azure Entra ID authentication.

## Overview

The migration process involves:

1. **Schema Migrations**: Adding new tables and columns for Azure Entra ID integration
2. **Data Migration**: Migrating existing users to the new authentication system
3. **Performance Optimization**: Adding indexes for better query performance
4. **Validation**: Ensuring all migrations were applied correctly

## Migration Files

### Schema Migrations (Alembic)

These migrations are automatically applied using Alembic:

- `1fe8ca7c007a_add_azure_entra_fields_to_users.py` - Adds Azure Entra ID fields to users table
- `8915fd1fe2df_add_github_sync_records_table.py` - Creates GitHub sync records table
- `0b70656934f4_add_user_preferences_and_websocket_.py` - Adds user preferences and WebSocket sessions tables
- `adc694485be9_add_performance_indexes_for_azure_entra_.py` - Adds performance optimization indexes

### Data Migration Scripts

These scripts handle data migration and validation:

- `migrate_existing_users_to_azure_entra.py` - Migrates existing users to Azure Entra system
- `validate_azure_entra_schema.py` - Validates that all schema changes were applied correctly

## Migration Process

### Prerequisites

1. **Backup your database** before running any migrations
2. Ensure you have the latest code with all model changes
3. Configure Azure Entra ID application in Azure portal
4. Update environment variables with Azure Entra credentials

### Step 1: Run Schema Migrations

Apply all database schema changes using Alembic:

```bash
# Check current migration status
alembic current

# Apply all pending migrations
alembic upgrade head

# Verify migrations were applied
alembic current
```

### Step 2: Validate Schema

Run the schema validation script to ensure all changes were applied correctly:

```bash
python alembic/data_migrations/validate_azure_entra_schema.py
```

This will check:

- All required tables exist
- All required columns exist with correct types
- All indexes are in place
- Foreign key constraints are properly configured
- Data integrity is maintained

### Step 3: Migrate Existing Users (if any)

If you have existing users in the system, run the data migration script:

```bash
# Dry run first to see what will be changed
python alembic/data_migrations/migrate_existing_users_to_azure_entra.py

# Execute the migration
python alembic/data_migrations/migrate_existing_users_to_azure_entra.py --execute
```

This script will:

- Create default user preferences for existing users
- Mark users as requiring Azure Entra migration
- Clean up any legacy authentication data
- Generate a migration report

### Step 4: Test the Migration

1. Start the application
2. Test Azure Entra authentication flow
3. Verify user profile synchronization
4. Test GitHub integration (if applicable)
5. Verify real-time features work correctly

## Database Schema Changes

### Users Table

New columns added:

- `azure_entra_id` - Azure AD object ID (unique)
- `azure_tenant_id` - Azure AD tenant ID
- `azure_access_token_hash` - Hashed access token
- `azure_refresh_token_hash` - Hashed refresh token
- `azure_token_expires_at` - Token expiration timestamp
- `profile_picture_url` - User profile picture URL
- `organization` - User's organization
- `department` - User's department
- `github_username` - Connected GitHub username
- `github_access_token_hash` - Hashed GitHub token
- `github_connected_at` - GitHub connection timestamp

Removed columns:

- `hashed_password` - No longer needed with Azure Entra

### New Tables

#### github_sync_records

Tracks GitHub repository synchronization:

- Project to repository mapping
- Sync status and history
- Error tracking and retry logic
- Performance metrics

#### websocket_sessions

Manages real-time WebSocket connections:

- Session tracking and heartbeat
- User connection mapping
- Connection metadata

#### user_preferences

Stores user preferences and settings:

- UI preferences (theme, language)
- Notification settings
- Integration preferences

### Performance Indexes

Added indexes for common query patterns:

- Azure Entra authentication lookups
- GitHub sync status queries
- WebSocket session management
- User activity tracking

## Troubleshooting

### Common Issues

1. **Migration fails with foreign key constraint error**

   - Ensure all referenced tables exist before running migrations
   - Check that user IDs in related tables are valid

2. **Schema validation fails**

   - Run `alembic upgrade head` to ensure all migrations are applied
   - Check database connection and permissions

3. **Existing users can't authenticate**

   - Run the user migration script to prepare existing users
   - Ensure Azure Entra configuration is correct

4. **Performance issues after migration**
   - Ensure the performance indexes migration was applied
   - Run `ANALYZE` on PostgreSQL to update query statistics

### Rollback Procedure

If you need to rollback the migration:

```bash
# Rollback to before Azure Entra changes
alembic downgrade <previous_revision_id>

# Note: This will lose Azure Entra user data
```

**Warning**: Rolling back will remove all Azure Entra integration data. Ensure you have backups before proceeding.

## Monitoring and Maintenance

### Post-Migration Monitoring

1. **Monitor authentication performance**

   - Track Azure Entra token validation times
   - Monitor token refresh success rates

2. **GitHub sync monitoring**

   - Track sync success/failure rates
   - Monitor sync duration and performance

3. **WebSocket connection health**
   - Monitor connection counts and stability
   - Track heartbeat and reconnection rates

### Regular Maintenance

1. **Clean up expired tokens**

   - Implement cleanup job for expired refresh tokens
   - Remove old WebSocket sessions

2. **Monitor database performance**

   - Check index usage and effectiveness
   - Monitor query performance

3. **Update statistics**
   - Run `ANALYZE` regularly on PostgreSQL
   - Monitor table sizes and growth

## Support

If you encounter issues during migration:

1. Check the application logs for detailed error messages
2. Run the validation script to identify specific problems
3. Ensure all environment variables are correctly configured
4. Verify Azure Entra application configuration

For additional support, refer to the main application documentation or contact the development team.
