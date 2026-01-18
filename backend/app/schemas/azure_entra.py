"""
Azure Entra ID response schemas.

This module defines Pydantic models for Azure Entra ID authentication
responses and user profile data.
"""

from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, EmailStr, Field

from app.schemas.user import User


class AzureEntraLoginResponse(BaseModel):
    """Response model for Azure Entra login."""
    
    user: User
    access_token: str
    refresh_token: str
    expires_at: datetime
    azure_profile: "AzureUserProfileResponse"


class AzureUserProfileResponse(BaseModel):
    """Azure Entra user profile response."""
    
    id: str = Field(..., description="Azure AD object ID")
    email: EmailStr
    name: Optional[str] = None
    given_name: Optional[str] = None
    family_name: Optional[str] = None
    preferred_username: Optional[str] = None
    tenant_id: Optional[str] = None
    upn: Optional[str] = None  # User Principal Name
    picture: Optional[str] = None
    job_title: Optional[str] = None
    department: Optional[str] = None
    company_name: Optional[str] = None
    
    @property
    def full_name(self) -> Optional[str]:
        """Get full name from available name fields."""
        if self.name:
            return self.name
        if self.given_name and self.family_name:
            return f"{self.given_name} {self.family_name}"
        return self.given_name or self.family_name


class AzureTokenRefreshRequest(BaseModel):
    """Request model for token refresh."""
    
    refresh_token: str = Field(..., description="Refresh token to use for getting new access token")


class AzureLogoutRequest(BaseModel):
    """Request model for logout."""
    
    refresh_token: str = Field(..., description="Refresh token to revoke")


class AzureAuthStateResponse(BaseModel):
    """Response model for authentication state."""
    
    authorization_url: str = Field(..., description="Azure Entra authorization URL")
    state: str = Field(..., description="State parameter for CSRF protection")


class AzureCallbackRequest(BaseModel):
    """Request model for OAuth callback."""
    
    code: Optional[str] = Field(None, description="Authorization code from Azure")
    state: Optional[str] = Field(None, description="State parameter for validation")
    error: Optional[str] = Field(None, description="Error code if authentication failed")
    error_description: Optional[str] = Field(None, description="Error description")


class UserProfileWithAzure(User):
    """Extended user profile with Azure Entra information."""
    
    azure_entra_id: Optional[str] = None
    azure_tenant_id: Optional[str] = None
    profile_picture_url: Optional[str] = None
    organization: Optional[str] = None
    department: Optional[str] = None
    azure_token_expires_at: Optional[datetime] = None
    github_username: Optional[str] = None
    github_connected_at: Optional[datetime] = None
    
    class Config:
        from_attributes = True


class AzureAuthenticationStatus(BaseModel):
    """Authentication status response."""
    
    is_authenticated: bool
    user_id: Optional[int] = None
    azure_entra_id: Optional[str] = None
    token_expires_at: Optional[datetime] = None
    requires_refresh: bool = False