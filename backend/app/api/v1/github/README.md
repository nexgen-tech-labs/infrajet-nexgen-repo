# GitHub Integration API

This module provides comprehensive GitHub integration for the Infrajet platform, supporting both OAuth authentication and GitHub App operations for repository management and synchronization.

## Overview

The GitHub integration consists of two main components:

### 1. GitHub OAuth Integration (`routes.py`)
Handles user authentication and repository synchronization through OAuth2 flow. Allows users to connect their GitHub accounts and sync project files to repositories.

### 2. GitHub App Integration (`app_routes.py`)
Provides GitHub App-based operations including repository creation, file pushing, webhook handling, and installation management. Enables automated operations without requiring individual user tokens.

## Features

- **OAuth Authentication**: Secure user login and repository access via GitHub OAuth2
- **Repository Synchronization**: Sync project files from Azure File Share to GitHub repositories
- **GitHub App Operations**: Create repositories, push files, handle webhooks
- **Installation Management**: Manage GitHub App installations and permissions
- **Conflict Detection**: Check for sync conflicts before operations
- **Sync History & Metrics**: Track synchronization operations and performance
- **Webhook Support**: Handle GitHub App webhook events
- **Real-time Updates**: WebSocket integration for sync status updates

## Environment Variables

### GitHub OAuth Configuration
```bash
GITHUB_CLIENT_ID=your-github-oauth-app-client-id
GITHUB_CLIENT_SECRET=your-github-oauth-app-client-secret
GITHUB_REDIRECT_URI=http://localhost:8000/api/v1/github/auth/callback
```

### GitHub App Configuration
```bash
GITHUB_APP_ID=your-github-app-id
GITHUB_APP_NAME=your-github-app-name-slug
GITHUB_CLIENT_ID=your-github-app-client-id
GITHUB_CLIENT_SECRET=your-github-app-client-secret
GITHUB_PRIVATE_KEY=your-github-app-private-key
GITHUB_WEBHOOK_SECRET=your-webhook-secret  # Optional for development
```

## API Endpoints

### GitHub OAuth Integration

#### Authentication

**`GET /api/v1/github/auth/login`**
Initiate GitHub OAuth authentication flow.

**Query Parameters:**
- `state` (optional): CSRF protection state parameter

**Response:** `GitHubAuthResponse`
```json
{
  "authorization_url": "https://github.com/login/oauth/authorize?...",
  "state": "csrf_protection_token"
}
```

**`POST /api/v1/github/auth/callback`**
Handle GitHub OAuth callback and connect account.

**Request Body:** `GitHubCallbackRequest`
```json
{
  "code": "authorization_code_from_github",
  "state": "csrf_protection_token"
}
```

**Response:** `GitHubUserProfile`

#### Connection Management

**`GET /api/v1/github/connection/status`**
Get GitHub connection status for the current user.

**Response:** `GitHubConnectionStatus`
```json
{
  "connected": true,
  "username": "github_username",
  "connected_at": "2023-01-01T00:00:00Z",
  "repositories_count": 25,
  "permissions": ["repo", "user:email"]
}
```

**`POST /api/v1/github/disconnect`**
Disconnect GitHub account from the current user.

**Request Body:** `GitHubDisconnectRequest`
```json
{
  "revoke_token": true
}
```

#### Repository Operations

**`GET /api/v1/github/repositories`**
Get user's GitHub repositories.

**Query Parameters:**
- `page` (default: 1): Page number
- `per_page` (default: 30, max: 100): Items per page

**Response:** `GitHubRepositoryList`

**`GET /api/v1/github/repositories/{owner}/{repo}`**
Get a specific repository by owner and name.

**Response:** `GitHubRepository`

#### Synchronization Operations

**`POST /api/v1/github/sync/project`**
Sync an entire project to a GitHub repository.

**Request Body:** `GitHubProjectSyncRequest`
```json
{
  "project_id": "project-uuid",
  "repository_full_name": "owner/repo",
  "branch": "main",
  "commit_message": "Sync from Infrajet",
  "check_conflicts": true
}
```

**Response:** `GitHubSyncResponse`

**`POST /api/v1/github/sync/manual-trigger`**
Manually trigger a synchronization operation with custom parameters.

**Request Body:** `GitHubSyncRequest`
```json
{
  "project_id": "project-uuid",
  "repository_full_name": "owner/repo",
  "branch": "main",
  "commit_message": "Manual sync",
  "sync_all_files": true,
  "file_paths": ["main.tf", "variables.tf"]
}
```

**`GET /api/v1/github/sync/history/{project_id}`**
Get synchronization history for a project.

**Response:** `GitHubSyncHistory`

**`GET /api/v1/github/sync/status/{project_id}`**
Get current synchronization status for a project.

**Response:**
```json
{
  "project_id": "project-uuid",
  "status": "completed",
  "repository": "owner/repo",
  "last_sync_at": "2023-01-01T00:00:00Z",
  "last_commit_sha": "abc123",
  "total_syncs": 5,
  "last_successful_sync": "2023-01-01T00:00:00Z"
}
```

**`POST /api/v1/github/sync/check-conflicts`**
Check for potential conflicts before syncing a project.

**Request Body:** `GitHubSyncConflictCheckRequest`
**Response:** `GitHubSyncConflictCheckResponse`

**`POST /api/v1/github/sync/retry`**
Retry a failed synchronization operation.

**Request Body:** `GitHubSyncRetryRequest`
**Response:** `GitHubSyncResponse`

**`GET /api/v1/github/sync/metrics`**
Get synchronization metrics and statistics for the user.

**Response:**
```json
{
  "user_id": 1,
  "total_syncs": 10,
  "successful_syncs": 8,
  "failed_syncs": 2,
  "total_files_synced": 45,
  "total_conflicts_resolved": 3,
  "average_sync_duration": 2.5,
  "last_sync_at": "2023-01-01T00:00:00Z",
  "connected_repositories": 3
}
```

### GitHub App Integration

#### Installation Management

**`GET /api/v1/github/installations`**
Get GitHub App installations accessible to a user.

**Headers:**
- `X-GitHub-Token`: User's GitHub access token

**Response:** `List[GitHubInstallation]`

**`POST /api/v1/github/installation/token`**
Get installation access token for repository operations.

**Request Body:** `GitHubAppAuthRequest`
```json
{
  "installation_id": 12345
}
```

**Response:** `GitHubAppTokenResponse`

#### Repository Operations

**`POST /api/v1/github/repositories`**
Create a new repository using GitHub App.

**Request Body:** `GitHubAppCreateRepoRequest`
```json
{
  "installation_id": 12345,
  "name": "my-repo",
  "description": "Infrastructure repository",
  "private": true,
  "owner": "my-org"
}
```

**Response:** `GitHubAppRepository`

**`POST /api/v1/github/repositories/push`**
Push files to a repository using GitHub App.

**Request Body:** `GitHubAppPushRequest`
```json
{
  "installation_id": 12345,
  "repo_owner": "my-org",
  "repo_name": "my-repo",
  "files": {
    "main.tf": "terraform { required_version = \">= 1.0\" }",
    "variables.tf": "variable \"region\" { type = string }"
  },
  "commit_message": "Add infrastructure files",
  "branch": "main"
}
```

**Response:**
```json
{
  "success": true,
  "commit_sha": "abc123...",
  "files_pushed": 2,
  "repository_url": "https://github.com/my-org/my-repo",
  "commit_url": "https://github.com/my-org/my-repo/commit/abc123",
  "branch": "main"
}
```

**`POST /api/v1/github/repositories/sync`**
Sync files to repository with conflict detection.

**Request Body:** `GitHubAppSyncRequest`
```json
{
  "installation_id": 12345,
  "repo_owner": "my-org",
  "repo_name": "my-repo",
  "files": {
    "main.tf": "terraform { required_version = \">= 1.0\" }",
    "variables.tf": "variable \"region\" { type = string }"
  },
  "commit_message": "Sync infrastructure files",
  "branch": "main"
}
```

**Response:** `GitHubAppSyncResponse`

**`POST /api/v1/github/repositories/validate-access`**
Validate user access to repository through GitHub App installation.

**Request Body:** `GitHubAppValidateAccessRequest`
```json
{
  "user_access_token": "gho_...",
  "installation_id": 12345,
  "repo_owner": "my-org",
  "repo_name": "my-repo"
}
```

**Response:** `GitHubAppValidateAccessResponse`

#### Installation URL Generation

**`GET /api/v1/github/install`**
Generate GitHub App installation URL for users to install the app.

**Query Parameters:**
- `state` (optional): State parameter for tracking installations
- `suggested_target_id` (optional): Organization ID to suggest for installation

**Response:** `GitHubAppInstallUrlResponse`
```json
{
  "installation_url": "https://github.com/apps/your-app/installations/new",
  "app_name": "your-app",
  "state": "optional-state-param",
  "github_app_url": "https://github.com/apps/your-app"
}
```

#### Webhook Handling

**`POST /api/v1/github/webhook`**
Handle GitHub App webhook events.

**Headers:**
- `X-GitHub-Event`: GitHub event type
- `X-Hub-Signature-256`: GitHub signature for validation

**Response:** `GitHubAppWebhookResponse`

#### Health Check

**`GET /api/v1/github/health`**
GitHub App service health check.

**Response:**
```json
{
  "service": "GitHub App",
  "status": "healthy",
  "checks": {
    "configuration": "✓ Valid",
    "jwt_generation": "✓ Working",
    "api_connectivity": "✓ Connected"
  }
}
```

## Authentication

### OAuth Endpoints
All OAuth endpoints require authentication via Bearer token in the Authorization header:
```
Authorization: Bearer <your_jwt_token>
```

### GitHub App Endpoints
GitHub App endpoints use Supabase authentication:
- Most endpoints require `get_current_user_id` dependency
- Webhook endpoint uses signature validation
- Some endpoints require `X-GitHub-Token` header for user tokens

## Error Handling

The API returns standard HTTP status codes:
- `200`: Success
- `400`: Bad Request (invalid parameters, GitHub not connected)
- `401`: Unauthorized (invalid token, failed signature validation)
- `403`: Forbidden (insufficient permissions)
- `404`: Not Found (repository, project, or installation not found)
- `422`: Validation Error
- `429`: Too Many Requests (rate limited)
- `500`: Internal Server Error
- `501`: Not Implemented (placeholder endpoints)

Error responses follow this format:
```json
{
  "detail": "Error message describing what went wrong"
}
```

## Setup Instructions

### 1. GitHub OAuth App Setup
1. Go to GitHub Settings → Developer settings → OAuth Apps
2. Create a new OAuth App with:
   - **Homepage URL**: `http://localhost:8000` (or your domain)
   - **Authorization callback URL**: `http://localhost:8000/api/v1/github/auth/callback`
3. Copy Client ID and Client Secret to environment variables

### 2. GitHub App Setup
1. Go to GitHub Settings → Developer settings → GitHub Apps
2. Create a new GitHub App with:
   - **Webhook URL**: `https://your-domain.com/api/v1/github/webhook`
   - **Webhook secret**: Generate a secure random string (optional for development)
3. Generate and download private key
4. Configure permissions:
   - Repository permissions: `Contents: Read & write`, `Metadata: Read`
   - Organization permissions: `Members: Read` (if using org repos)
5. Subscribe to events: `Installation`, `Installation repositories`, `Push`
6. Copy App ID, Client ID, Client Secret, and private key to environment variables

### 3. Environment Configuration
Add the following to your `.env` file:
```bash
# GitHub OAuth
GITHUB_CLIENT_ID=your-oauth-client-id
GITHUB_CLIENT_SECRET=your-oauth-client-secret

# GitHub App
GITHUB_APP_ID=your-app-id
GITHUB_CLIENT_ID=your-app-client-id
GITHUB_CLIENT_SECRET=your-app-client-secret
GITHUB_PRIVATE_KEY=-----BEGIN RSA PRIVATE KEY-----\n...\n-----END RSA PRIVATE KEY-----
GITHUB_WEBHOOK_SECRET=your-webhook-secret
```

## Security Considerations

- **Token Encryption**: GitHub OAuth tokens are encrypted before database storage
- **CSRF Protection**: OAuth flow uses state parameters for CSRF prevention
- **Signature Validation**: Webhook signatures are validated (when secret is configured)
- **Rate Limiting**: GitHub API rate limits are handled with retry logic
- **Permission Validation**: Repository access is validated before operations
- **Token Scoping**: Installation tokens have limited scope and expiration

## Implementation Details

### File Storage Integration
- Project files are stored in Azure File Share
- Sync operations retrieve files from Azure before pushing to GitHub
- Placeholder implementations exist for Azure integration

### WebSocket Integration
- Real-time sync status updates via WebSocket connections
- Progress tracking for long-running operations
- Error notifications and completion status

### Database Models
- `User` model includes GitHub connection fields
- `GitHubSyncRecord` tracks sync operations and history
- Installation and repository metadata stored for app operations

### Service Architecture
- `GitHubIntegrationService`: Handles OAuth and repository operations
- `GitHubAppService`: Manages GitHub App authentication and operations
- Separate services for different authentication methods
- Comprehensive error handling and logging

### Current Limitations
- Some sync endpoints have placeholder implementations
- Azure File Share integration is not fully implemented
- Metrics and retry functionality partially implemented
- Conflict resolution is basic

## Development Notes

- `GITHUB_WEBHOOK_SECRET` is optional for development (webhooks accepted without validation)
- Use placeholder implementations for testing sync operations
- GitHub App provides more automation capabilities than OAuth
- Consider implementing proper conflict resolution for production use