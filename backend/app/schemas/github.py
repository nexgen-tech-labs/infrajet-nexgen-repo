"""
GitHub integration schemas for API requests and responses.
"""

from datetime import datetime
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field
from enum import Enum


class GitHubSyncStatus(str, Enum):
    """GitHub sync status enumeration."""
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class GitHubAuthRequest(BaseModel):
    """Request model for GitHub OAuth initiation."""
    state: Optional[str] = Field(None, description="CSRF protection state parameter")


class GitHubAuthResponse(BaseModel):
    """Response model for GitHub OAuth initiation."""
    authorization_url: str = Field(..., description="GitHub OAuth authorization URL")
    state: str = Field(..., description="State parameter for CSRF protection")


class GitHubCallbackRequest(BaseModel):
    """Request model for GitHub OAuth callback."""
    code: str = Field(..., description="Authorization code from GitHub")
    state: str = Field(..., description="State parameter for validation")


class GitHubTokenResponse(BaseModel):
    """Response model for GitHub token exchange."""
    access_token: str = Field(..., description="GitHub access token")
    token_type: str = Field(default="bearer", description="Token type")
    scope: Optional[str] = Field(None, description="Granted scopes")


class GitHubUserProfile(BaseModel):
    """GitHub user profile model."""
    id: int = Field(..., description="GitHub user ID")
    login: str = Field(..., description="GitHub username")
    email: Optional[str] = Field(None, description="User email address")
    name: Optional[str] = Field(None, description="User display name")
    avatar_url: Optional[str] = Field(None, description="Avatar image URL")
    html_url: Optional[str] = Field(None, description="GitHub profile URL")
    company: Optional[str] = Field(None, description="Company name")
    location: Optional[str] = Field(None, description="User location")
    bio: Optional[str] = Field(None, description="User bio")
    public_repos: Optional[int] = Field(None, description="Number of public repositories")
    followers: Optional[int] = Field(None, description="Number of followers")
    following: Optional[int] = Field(None, description="Number of following")
    created_at: Optional[str] = Field(None, description="Account creation date")


class GitHubRepository(BaseModel):
    """GitHub repository model."""
    id: int = Field(..., description="Repository ID")
    name: str = Field(..., description="Repository name")
    full_name: str = Field(..., description="Full repository name (owner/repo)")
    description: Optional[str] = Field(None, description="Repository description")
    private: bool = Field(..., description="Whether repository is private")
    html_url: str = Field(..., description="Repository web URL")
    clone_url: str = Field(..., description="Repository clone URL")
    ssh_url: str = Field(..., description="Repository SSH URL")
    default_branch: str = Field(default="main", description="Default branch name")
    permissions: Optional[Dict[str, bool]] = Field(None, description="User permissions")
    owner: Dict[str, Any] = Field(..., description="Repository owner information")
    created_at: Optional[str] = Field(None, description="Repository creation date")
    updated_at: Optional[str] = Field(None, description="Last update date")
    pushed_at: Optional[str] = Field(None, description="Last push date")


class GitHubRepositoryList(BaseModel):
    """Response model for repository listing."""
    repositories: List[GitHubRepository] = Field(..., description="List of repositories")
    total_count: int = Field(..., description="Total number of repositories")
    page: int = Field(default=1, description="Current page number")
    per_page: int = Field(default=30, description="Items per page")


class GitHubSyncRequest(BaseModel):
    """Request model for GitHub sync operation."""
    project_id: str = Field(..., description="Project ID to sync")
    repository_full_name: str = Field(..., description="Target repository (owner/repo)")
    branch: str = Field(default="main", description="Target branch")
    commit_message: Optional[str] = Field(None, description="Custom commit message")
    sync_all_files: bool = Field(default=True, description="Whether to sync all project files")
    file_paths: Optional[List[str]] = Field(None, description="Specific files to sync")


class GitHubSyncResponse(BaseModel):
    """Response model for GitHub sync operation."""
    sync_id: str = Field(..., description="Sync operation ID")
    status: GitHubSyncStatus = Field(..., description="Sync status")
    repository_full_name: str = Field(..., description="Target repository")
    branch: str = Field(..., description="Target branch")
    commit_sha: Optional[str] = Field(None, description="Commit SHA if successful")
    commit_url: Optional[str] = Field(None, description="Commit URL if successful")
    files_synced: int = Field(default=0, description="Number of files synced")
    error_message: Optional[str] = Field(None, description="Error message if failed")
    created_at: datetime = Field(..., description="Sync creation timestamp")
    completed_at: Optional[datetime] = Field(None, description="Sync completion timestamp")


class GitHubSyncRecord(BaseModel):
    """GitHub sync record model."""
    id: int = Field(..., description="Sync record ID")
    project_id: str = Field(..., description="Associated project ID")
    user_id: int = Field(..., description="User who initiated sync")
    github_repository: str = Field(..., description="Target repository")
    last_sync_at: Optional[datetime] = Field(None, description="Last sync timestamp")
    sync_status: GitHubSyncStatus = Field(..., description="Current sync status")
    last_commit_sha: Optional[str] = Field(None, description="Last commit SHA")
    sync_errors: Optional[str] = Field(None, description="Sync error details")
    created_at: datetime = Field(..., description="Record creation timestamp")
    updated_at: datetime = Field(..., description="Record update timestamp")


class GitHubSyncHistory(BaseModel):
    """GitHub sync history response."""
    project_id: str = Field(..., description="Project ID")
    repository_full_name: str = Field(..., description="Repository name")
    sync_records: List[GitHubSyncRecord] = Field(..., description="Sync history records")
    total_syncs: int = Field(..., description="Total number of syncs")
    last_successful_sync: Optional[datetime] = Field(None, description="Last successful sync")
    current_status: GitHubSyncStatus = Field(..., description="Current sync status")


class GitHubConnectionStatus(BaseModel):
    """GitHub connection status model."""
    connected: bool = Field(..., description="Whether GitHub is connected")
    username: Optional[str] = Field(None, description="Connected GitHub username")
    connected_at: Optional[datetime] = Field(None, description="Connection timestamp")
    repositories_count: Optional[int] = Field(None, description="Number of accessible repositories")
    permissions: Optional[List[str]] = Field(None, description="Granted permissions")


class GitHubDisconnectRequest(BaseModel):
    """Request model for GitHub disconnection."""
    revoke_token: bool = Field(default=True, description="Whether to revoke the GitHub token")


class GitHubDisconnectResponse(BaseModel):
    """Response model for GitHub disconnection."""
    success: bool = Field(..., description="Whether disconnection was successful")
    message: str = Field(..., description="Status message")
    token_revoked: bool = Field(..., description="Whether token was revoked")


class GitHubFileSync(BaseModel):
    """Model for individual file sync information."""
    file_path: str = Field(..., description="File path in repository")
    content: str = Field(..., description="File content")
    commit_message: str = Field(..., description="Commit message for this file")
    branch: str = Field(default="main", description="Target branch")


class GitHubBulkSyncRequest(BaseModel):
    """Request model for bulk file sync."""
    repository_full_name: str = Field(..., description="Target repository")
    files: List[GitHubFileSync] = Field(..., description="Files to sync")
    base_commit_message: str = Field(..., description="Base commit message")
    create_pull_request: bool = Field(default=False, description="Whether to create a PR")
    pr_title: Optional[str] = Field(None, description="Pull request title")
    pr_description: Optional[str] = Field(None, description="Pull request description")


class GitHubBulkSyncResponse(BaseModel):
    """Response model for bulk file sync."""
    sync_id: str = Field(..., description="Bulk sync operation ID")
    repository_full_name: str = Field(..., description="Target repository")
    files_processed: int = Field(..., description="Number of files processed")
    files_successful: int = Field(..., description="Number of files successfully synced")
    files_failed: int = Field(..., description="Number of files that failed")
    commit_shas: List[str] = Field(..., description="List of commit SHAs created")
    pull_request_url: Optional[str] = Field(None, description="Pull request URL if created")
    errors: List[str] = Field(default_factory=list, description="List of errors encountered")


class GitHubWebhookEvent(BaseModel):
    """GitHub webhook event model."""
    event_type: str = Field(..., description="GitHub event type")
    repository: GitHubRepository = Field(..., description="Repository information")
    sender: Dict[str, Any] = Field(..., description="Event sender information")
    payload: Dict[str, Any] = Field(..., description="Event payload")
    received_at: datetime = Field(..., description="Event received timestamp")


class GitHubErrorResponse(BaseModel):
    """GitHub API error response model."""
    error: str = Field(..., description="Error type")
    error_description: Optional[str] = Field(None, description="Detailed error description")
    error_code: Optional[int] = Field(None, description="HTTP error code")
    documentation_url: Optional[str] = Field(None, description="GitHub documentation URL")


class GitHubSyncConflict(BaseModel):
    """GitHub sync conflict information."""
    file_path: str = Field(..., description="File path with conflict")
    has_conflict: bool = Field(..., description="Whether conflict exists")
    conflict_reason: Optional[str] = Field(None, description="Reason for conflict")
    existing_sha: Optional[str] = Field(None, description="SHA of existing file")
    existing_size: int = Field(default=0, description="Size of existing file")
    resolution_strategy: Optional[str] = Field(None, description="Suggested resolution strategy")


class GitHubSyncRetryRequest(BaseModel):
    """Request model for retrying failed sync."""
    sync_record_id: int = Field(..., description="ID of sync record to retry")
    max_retries: int = Field(default=3, description="Maximum retry attempts")


class GitHubSyncConflictCheckRequest(BaseModel):
    """Request model for checking sync conflicts."""
    project_id: str = Field(..., description="Project ID to check")
    repository_full_name: str = Field(..., description="Target repository")
    branch: str = Field(default="main", description="Target branch")


class GitHubSyncConflictCheckResponse(BaseModel):
    """Response model for sync conflict check."""
    project_id: str = Field(..., description="Project ID")
    repository_full_name: str = Field(..., description="Target repository")
    branch: str = Field(..., description="Target branch")
    conflicts: List[GitHubSyncConflict] = Field(..., description="List of conflicts found")
    total_conflicts: int = Field(..., description="Total number of conflicts")
    can_auto_resolve: int = Field(..., description="Number of conflicts that can be auto-resolved")


class GitHubProjectSyncRequest(BaseModel):
    """Request model for syncing entire project from Azure."""
    project_id: str = Field(..., description="Project ID to sync")
    repository_full_name: str = Field(..., description="Target repository")
    branch: str = Field(default="main", description="Target branch")
    commit_message: Optional[str] = Field(None, description="Custom commit message")
    check_conflicts: bool = Field(default=True, description="Whether to check for conflicts first")


class GitHubSyncMetrics(BaseModel):
    """GitHub sync metrics and statistics."""
    total_syncs: int = Field(..., description="Total number of syncs")
    successful_syncs: int = Field(..., description="Number of successful syncs")
    failed_syncs: int = Field(..., description="Number of failed syncs")
    total_files_synced: int = Field(..., description="Total files synced")
    total_conflicts_resolved: int = Field(..., description="Total conflicts resolved")
    average_sync_duration: Optional[float] = Field(None, description="Average sync duration in seconds")
    last_sync_at: Optional[datetime] = Field(None, description="Last sync timestamp")


class GitHubSyncStatusUpdate(BaseModel):
    """Real-time sync status update."""
    sync_id: str = Field(..., description="Sync operation ID")
    status: GitHubSyncStatus = Field(..., description="Current sync status")
    progress_percentage: int = Field(default=0, description="Sync progress percentage")
    current_file: Optional[str] = Field(None, description="Currently processing file")
    files_completed: int = Field(default=0, description="Number of files completed")
    total_files: int = Field(default=0, description="Total number of files to sync")
    error_message: Optional[str] = Field(None, description="Error message if failed")
    estimated_completion: Optional[datetime] = Field(None, description="Estimated completion time")


# GitHub App specific schemas
class GitHubInstallation(BaseModel):
    """GitHub App installation model."""
    id: int = Field(..., description="Installation ID")
    account_login: str = Field(..., description="Account login name")
    account_type: str = Field(..., description="Account type (User or Organization)")
    permissions: Dict[str, str] = Field(default_factory=dict, description="Installation permissions")
    events: List[str] = Field(default_factory=list, description="Subscribed events")
    created_at: datetime = Field(..., description="Installation creation timestamp")
    updated_at: datetime = Field(..., description="Installation update timestamp")


class GitHubAppRepository(BaseModel):
    """GitHub App repository model (extends base repository)."""
    id: int = Field(..., description="Repository ID")
    name: str = Field(..., description="Repository name")
    full_name: str = Field(..., description="Full repository name (owner/repo)")
    description: Optional[str] = Field(None, description="Repository description")
    private: bool = Field(..., description="Whether repository is private")
    html_url: str = Field(..., description="Repository web URL")
    clone_url: str = Field(..., description="Repository clone URL")
    created_at: datetime = Field(..., description="Repository creation timestamp")
    updated_at: datetime = Field(..., description="Repository update timestamp")


class GitHubWebhookEvent(BaseModel):
    """GitHub App webhook event model."""
    action: str = Field(..., description="Webhook action")
    installation: Optional[GitHubInstallation] = Field(None, description="Installation information")
    repositories: Optional[List[GitHubAppRepository]] = Field(None, description="Affected repositories")
    sender: Dict[str, Any] = Field(..., description="Event sender information")


class GitHubAppTokenResponse(BaseModel):
    """GitHub App installation token response."""
    token: str = Field(..., description="Installation access token")
    expires_at: str = Field(..., description="Token expiration timestamp")
    permissions: Dict[str, str] = Field(default_factory=dict, description="Token permissions")
    repository_selection: str = Field(..., description="Repository selection scope")


class GitHubAppAuthRequest(BaseModel):
    """GitHub App authentication request."""
    installation_id: int = Field(..., description="GitHub App installation ID")


class GitHubAppCreateRepoRequest(BaseModel):
    """GitHub App repository creation request."""
    installation_id: int = Field(..., description="GitHub App installation ID")
    name: str = Field(..., description="Repository name")
    description: Optional[str] = Field(None, description="Repository description")
    private: bool = Field(default=True, description="Whether repository should be private")
    owner: Optional[str] = Field(None, description="Repository owner (for organizations)")


class GitHubAppPushRequest(BaseModel):
    """GitHub App push files request."""
    installation_id: int = Field(..., description="GitHub App installation ID")
    repo_owner: str = Field(..., description="Repository owner")
    repo_name: str = Field(..., description="Repository name")
    files: Dict[str, str] = Field(..., description="Files to push (path -> content)")
    commit_message: str = Field(..., description="Commit message")
    branch: str = Field(default="main", description="Target branch")


class GitHubAppSyncRequest(BaseModel):
    """GitHub App sync repository request."""
    installation_id: int = Field(..., description="GitHub App installation ID")
    repo_owner: str = Field(..., description="Repository owner")
    repo_name: str = Field(..., description="Repository name")
    files: Dict[str, str] = Field(..., description="Files to sync (path -> content)")
    commit_message: str = Field(..., description="Commit message")
    branch: str = Field(default="main", description="Target branch")


class GitHubAppSyncResponse(BaseModel):
    """GitHub App sync repository response."""
    success: bool = Field(..., description="Whether sync was successful")
    commit_sha: Optional[str] = Field(None, description="Commit SHA if successful")
    files_synced: int = Field(..., description="Number of files synced")
    repository_url: str = Field(..., description="Repository URL")
    commit_url: Optional[str] = Field(None, description="Commit URL if successful")


class GitHubAppValidateAccessRequest(BaseModel):
    """GitHub App validate access request."""
    user_access_token: str = Field(..., description="User's GitHub access token")
    installation_id: int = Field(..., description="GitHub App installation ID")
    repo_owner: str = Field(..., description="Repository owner")
    repo_name: str = Field(..., description="Repository name")


class GitHubAppValidateAccessResponse(BaseModel):
    """GitHub App validate access response."""
    has_access: bool = Field(..., description="Whether user has access")
    installation_found: bool = Field(..., description="Whether installation was found")
    repository_accessible: bool = Field(..., description="Whether repository is accessible")


class GitHubAppWebhookRequest(BaseModel):
    """GitHub App webhook request."""
    event_type: str = Field(..., description="GitHub event type")
    payload: Dict[str, Any] = Field(..., description="Webhook payload")
    signature: str = Field(..., description="GitHub signature header")


class GitHubAppWebhookResponse(BaseModel):
    """GitHub App webhook response."""
    handled: bool = Field(..., description="Whether event was handled")
    message: str = Field(..., description="Response message")
    error: Optional[str] = Field(None, description="Error message if failed")


class GitHubAppInstallUrlRequest(BaseModel):
    """GitHub App installation URL request."""
    state: Optional[str] = Field(None, description="Optional state parameter for tracking")
    suggested_target_id: Optional[int] = Field(None, description="Suggested organization ID for installation")


class GitHubAppInstallUrlResponse(BaseModel):
    """GitHub App installation URL response."""
    installation_url: str = Field(..., description="GitHub App installation URL")
    app_name: str = Field(..., description="GitHub App name/slug")
    state: Optional[str] = Field(None, description="State parameter if provided")
    github_app_url: str = Field(..., description="Direct link to GitHub App page")