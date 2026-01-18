"""
Azure Entra ID (Azure AD) configuration and utilities.
"""

import secrets
import time
from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta
import logging
import jwt
import aiohttp
from msal import ConfidentialClientApplication
from pydantic import BaseModel, Field, field_validator, model_validator

logger = logging.getLogger(__name__)


class AzureEntraConfig(BaseModel):
    """Azure Entra ID configuration settings."""

    client_id: str = Field(..., description="Azure AD application client ID")
    client_secret: str = Field(..., description="Azure AD application client secret")
    tenant_id: str = Field(..., description="Azure AD tenant ID")
    authority: Optional[str] = Field(None, description="Azure AD authority URL")
    redirect_uri: str = Field(..., description="OAuth2 redirect URI")
    scopes: List[str] = Field(
        default=["openid", "profile", "email", "User.Read"],
        description="OAuth2 scopes to request",
    )
    session_timeout_minutes: int = Field(
        default=60, description="Session timeout in minutes"
    )
    validate_issuer: bool = Field(
        default=True, description="Whether to validate token issuer"
    )
    validate_audience: bool = Field(
        default=True, description="Whether to validate token audience"
    )

    @model_validator(mode="after")
    def build_authority_url(self) -> "AzureEntraConfig":
        """Build authority URL if not provided."""
        if not self.authority and self.tenant_id:
            self.authority = f"https://login.microsoftonline.com/{self.tenant_id}"
        elif not self.authority:
            self.authority = "https://login.microsoftonline.com/common"
        return self

    @field_validator("scopes")
    @classmethod
    def validate_scopes(cls, v: List[str]) -> List[str]:
        """Ensure required scopes are present."""
        required_scopes = {"openid", "profile", "email"}
        current_scopes = set(v)

        # Add missing required scopes
        missing_scopes = required_scopes - current_scopes
        if missing_scopes:
            v.extend(list(missing_scopes))

        return v

    def get_msal_config(self) -> dict:
        """Get configuration dictionary for MSAL library."""
        return {
            "client_id": self.client_id,
            "client_credential": self.client_secret,
            "authority": self.authority,
        }

    def get_oauth2_config(self) -> dict:
        """Get OAuth2 configuration for authentication flow."""
        return {
            "client_id": self.client_id,
            "redirect_uri": self.redirect_uri,
            "scopes": self.scopes,
            "authority": self.authority,
        }

    def is_configured(self) -> bool:
        """Check if Azure Entra is properly configured."""
        return bool(
            self.client_id
            and self.client_secret
            and self.tenant_id
            and self.redirect_uri
        )


class AzureTokenResponse(BaseModel):
    """Azure Entra token response model."""

    access_token: str
    refresh_token: Optional[str] = None
    id_token: Optional[str] = None
    token_type: str = "Bearer"
    expires_in: int
    scope: Optional[str] = None


class AzureUserProfile(BaseModel):
    """Azure Entra user profile model."""

    id: str = Field(..., description="Azure AD object ID")
    email: str
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


class TokenValidationResult(BaseModel):
    """Token validation result model."""

    is_valid: bool
    user_id: Optional[str] = None
    email: Optional[str] = None
    tenant_id: Optional[str] = None
    expires_at: Optional[float] = None
    error: Optional[str] = None
    scopes: Optional[List[str]] = None


class AzureEntraService:
    """Azure Entra ID authentication service for OAuth2 flows."""

    def __init__(self, config: AzureEntraConfig):
        """Initialize the Azure Entra service with configuration."""
        self.config = config
        self._msal_app = None
        self._session = None

    @property
    def msal_app(self) -> ConfidentialClientApplication:
        """Get or create MSAL application instance."""
        if self._msal_app is None:
            self._msal_app = ConfidentialClientApplication(
                client_id=self.config.client_id,
                client_credential=self.config.client_secret,
                authority=self.config.authority,
            )
        return self._msal_app

    @property
    async def session(self) -> aiohttp.ClientSession:
        """Get or create aiohttp session for API calls."""
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession()
        return self._session

    async def close(self):
        """Close the aiohttp session."""
        if self._session and not self._session.closed:
            await self._session.close()

    async def get_authorization_url(self, state: Optional[str] = None) -> str:
        """
        Generate Azure Entra authorization URL for OAuth2 flow.

        Args:
            state: Optional state parameter for CSRF protection

        Returns:
            Authorization URL string
        """
        if state is None:
            state = secrets.token_urlsafe(32)

        try:
            auth_url = self.msal_app.get_authorization_request_url(
                scopes=self.config.scopes,
                state=state,
                redirect_uri=self.config.redirect_uri,
            )
            logger.info(f"Generated authorization URL for state: {state}")
            return auth_url
        except Exception as e:
            logger.error(f"Failed to generate authorization URL: {str(e)}")
            raise AzureEntraError(f"Failed to generate authorization URL: {str(e)}")

    async def exchange_code_for_tokens(
        self, code: str, state: str
    ) -> AzureTokenResponse:
        """
        Exchange authorization code for access and refresh tokens.

        Args:
            code: Authorization code from callback
            state: State parameter for validation

        Returns:
            AzureTokenResponse with tokens and metadata
        """
        try:
            result = self.msal_app.acquire_token_by_authorization_code(
                code=code,
                scopes=self.config.scopes,
                redirect_uri=self.config.redirect_uri,
            )

            if "error" in result:
                error_msg = result.get(
                    "error_description", result.get("error", "Unknown error")
                )
                logger.error(f"Token exchange failed: {error_msg}")
                raise AuthorizationError(f"Token exchange failed: {error_msg}")

            logger.info(f"Successfully exchanged code for tokens")
            return AzureTokenResponse(
                access_token=result["access_token"],
                refresh_token=result.get("refresh_token"),
                id_token=result.get("id_token"),
                token_type=result.get("token_type", "Bearer"),
                expires_in=result.get("expires_in", 3600),
                scope=result.get("scope"),
            )
        except Exception as e:
            if isinstance(e, AzureEntraError):
                raise
            logger.error(f"Failed to exchange code for tokens: {str(e)}")
            raise AzureEntraError(f"Failed to exchange code for tokens: {str(e)}")

    async def refresh_access_token(self, refresh_token: str) -> AzureTokenResponse:
        """
        Refresh access token using refresh token.

        Args:
            refresh_token: Valid refresh token

        Returns:
            AzureTokenResponse with new tokens
        """
        try:
            result = self.msal_app.acquire_token_by_refresh_token(
                refresh_token=refresh_token,
                scopes=self.config.scopes,
            )

            if "error" in result:
                error_msg = result.get(
                    "error_description", result.get("error", "Unknown error")
                )
                logger.error(f"Token refresh failed: {error_msg}")
                raise TokenExpiredError(f"Token refresh failed: {error_msg}")

            logger.info("Successfully refreshed access token")
            return AzureTokenResponse(
                access_token=result["access_token"],
                refresh_token=result.get(
                    "refresh_token", refresh_token
                ),  # Keep old if new not provided
                id_token=result.get("id_token"),
                token_type=result.get("token_type", "Bearer"),
                expires_in=result.get("expires_in", 3600),
                scope=result.get("scope"),
            )
        except Exception as e:
            if isinstance(e, AzureEntraError):
                raise
            logger.error(f"Failed to refresh token: {str(e)}")
            raise AzureEntraError(f"Failed to refresh token: {str(e)}")

    async def get_user_profile(self, access_token: str) -> AzureUserProfile:
        """
        Retrieve user profile from Microsoft Graph API.

        Args:
            access_token: Valid access token

        Returns:
            AzureUserProfile with user information
        """
        try:
            session = await self.session
            headers = {
                "Authorization": f"Bearer {access_token}",
                "Content-Type": "application/json",
            }

            # Get user profile from Microsoft Graph
            async with session.get(
                "https://graph.microsoft.com/v1.0/me", headers=headers
            ) as response:
                if response.status == 401:
                    raise InvalidTokenError("Access token is invalid or expired")
                elif response.status != 200:
                    error_text = await response.text()
                    raise AzureEntraError(f"Failed to get user profile: {error_text}")

                profile_data = await response.json()

            # Get user photo if available
            photo_url = None
            try:
                async with session.get(
                    "https://graph.microsoft.com/v1.0/me/photo/$value", headers=headers
                ) as photo_response:
                    if photo_response.status == 200:
                        # In a real implementation, you might want to store this photo
                        # For now, we'll just note that it's available
                        photo_url = "https://graph.microsoft.com/v1.0/me/photo/$value"
            except Exception:
                # Photo is optional, don't fail if we can't get it
                pass

            logger.info(
                f"Retrieved user profile for: {profile_data.get('userPrincipalName')}"
            )
            return AzureUserProfile(
                id=profile_data["id"],
                email=profile_data.get("mail")
                or profile_data.get("userPrincipalName", ""),
                name=profile_data.get("displayName"),
                given_name=profile_data.get("givenName"),
                family_name=profile_data.get("surname"),
                preferred_username=profile_data.get("userPrincipalName"),
                upn=profile_data.get("userPrincipalName"),
                picture=photo_url,
                job_title=profile_data.get("jobTitle"),
                department=profile_data.get("department"),
                company_name=profile_data.get("companyName"),
            )
        except Exception as e:
            if isinstance(e, AzureEntraError):
                raise
            logger.error(f"Failed to get user profile: {str(e)}")
            raise AzureEntraError(f"Failed to get user profile: {str(e)}")

    async def validate_token(self, token: str) -> TokenValidationResult:
        """
        Validate Azure Entra JWT token.

        Args:
            token: JWT token to validate

        Returns:
            TokenValidationResult with validation status and claims
        """
        try:
            # First, decode without verification to get the header
            unverified_header = jwt.get_unverified_header(token)
            unverified_payload = jwt.decode(token, options={"verify_signature": False})

            # Get the key ID from header
            kid = unverified_header.get("kid")
            if not kid:
                return TokenValidationResult(
                    is_valid=False, error="Token missing key ID (kid) in header"
                )

            # Get signing keys from Azure
            signing_keys = await self._get_signing_keys()
            if kid not in signing_keys:
                return TokenValidationResult(
                    is_valid=False, error=f"Signing key {kid} not found"
                )

            # Verify the token
            try:
                payload = jwt.decode(
                    token,
                    key=signing_keys[kid],
                    algorithms=["RS256"],
                    audience=(
                        self.config.client_id if self.config.validate_audience else None
                    ),
                    issuer=(
                        f"{self.config.authority}/v2.0"
                        if self.config.validate_issuer
                        else None
                    ),
                )
            except jwt.ExpiredSignatureError:
                return TokenValidationResult(is_valid=False, error="Token has expired")
            except jwt.InvalidTokenError as e:
                return TokenValidationResult(
                    is_valid=False, error=f"Invalid token: {str(e)}"
                )

            logger.info(
                f"Successfully validated token for user: {payload.get('preferred_username')}"
            )
            return TokenValidationResult(
                is_valid=True,
                user_id=payload.get("oid"),  # Object ID
                email=payload.get("preferred_username") or payload.get("email"),
                tenant_id=payload.get("tid"),
                expires_at=payload.get("exp"),
                scopes=payload.get("scp", "").split() if payload.get("scp") else None,
            )

        except Exception as e:
            logger.error(f"Token validation failed: {str(e)}")
            return TokenValidationResult(
                is_valid=False, error=f"Token validation failed: {str(e)}"
            )

    async def revoke_token(self, token: str) -> bool:
        """
        Revoke an access token.

        Args:
            token: Token to revoke

        Returns:
            True if revocation was successful
        """
        try:
            session = await self.session

            # Azure doesn't have a standard revocation endpoint for access tokens
            # But we can try to revoke via the logout endpoint
            revoke_url = f"{self.config.authority}/oauth2/v2.0/logout"

            data = {
                "token": token,
                "client_id": self.config.client_id,
                "client_secret": self.config.client_secret,
            }

            async with session.post(revoke_url, data=data) as response:
                # Azure logout endpoint typically returns 200 even for invalid tokens
                success = response.status in [200, 204]
                if success:
                    logger.info("Successfully revoked token")
                else:
                    logger.warning(
                        f"Token revocation returned status: {response.status}"
                    )
                return success

        except Exception as e:
            logger.error(f"Failed to revoke token: {str(e)}")
            return False

    async def _get_signing_keys(self) -> Dict[str, str]:
        """
        Get JWT signing keys from Azure's JWKS endpoint.

        Returns:
            Dictionary mapping key IDs to public keys
        """
        try:
            session = await self.session
            jwks_url = f"{self.config.authority}/discovery/v2.0/keys"

            async with session.get(jwks_url) as response:
                if response.status != 200:
                    raise AzureEntraError(
                        f"Failed to get signing keys: HTTP {response.status}"
                    )

                jwks_data = await response.json()

            # Convert JWKS to usable keys
            signing_keys = {}
            for key_data in jwks_data.get("keys", []):
                if key_data.get("use") == "sig" and key_data.get("kty") == "RSA":
                    kid = key_data.get("kid")
                    if kid:
                        # Convert JWK to PEM format for PyJWT
                        public_key = jwt.algorithms.RSAAlgorithm.from_jwk(key_data)
                        signing_keys[kid] = public_key

            return signing_keys

        except Exception as e:
            logger.error(f"Failed to get signing keys: {str(e)}")
            raise AzureEntraError(f"Failed to get signing keys: {str(e)}")


# Exception classes for Azure Entra errors
class AzureEntraError(Exception):
    """Base exception for Azure Entra errors."""

    pass


class TokenExpiredError(AzureEntraError):
    """Raised when a token has expired."""

    pass


class InvalidTokenError(AzureEntraError):
    """Raised when a token is invalid."""

    pass


class AuthorizationError(AzureEntraError):
    """Raised when authorization fails."""

    pass


class TenantNotAllowedError(AzureEntraError):
    """Raised when tenant is not allowed."""

    pass
