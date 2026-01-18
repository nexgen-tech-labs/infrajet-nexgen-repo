"""
Troubleshooting guide service for providing user-friendly error messages
and step-by-step resolution guides for common issues.
"""

from typing import Dict, List, Optional, Any
from enum import Enum
from dataclasses import dataclass

from ..exceptions.base_exceptions import BaseApplicationError
from ..exceptions.azure_entra_exceptions import AzureEntraError
from ..exceptions.github_exceptions import GitHubError
from ..exceptions.websocket_exceptions import WebSocketError
from ..exceptions.security_exceptions import SecurityError


class TroubleshootingCategory(Enum):
    """Categories of troubleshooting guides."""

    AUTHENTICATION = "authentication"
    AUTHORIZATION = "authorization"
    CONNECTIVITY = "connectivity"
    CONFIGURATION = "configuration"
    INTEGRATION = "integration"
    SECURITY = "security"
    PERFORMANCE = "performance"
    DATA = "data"


@dataclass
class TroubleshootingStep:
    """A single troubleshooting step."""

    step_number: int
    title: str
    description: str
    action: str
    expected_result: str
    additional_info: Optional[str] = None
    is_technical: bool = False


@dataclass
class TroubleshootingGuide:
    """Complete troubleshooting guide for an error."""

    error_code: str
    title: str
    description: str
    category: TroubleshootingCategory
    severity: str
    estimated_time: str
    prerequisites: List[str]
    steps: List[TroubleshootingStep]
    related_links: List[Dict[str, str]]
    contact_support: bool = False
    escalation_criteria: Optional[str] = None


class TroubleshootingGuideService:
    """
    Service for providing comprehensive troubleshooting guides
    and user-friendly error resolution steps.
    """

    def __init__(self):
        self.guides: Dict[str, TroubleshootingGuide] = {}
        self._initialize_guides()

    def get_troubleshooting_guide(
        self, error_code: str, user_context: Optional[Dict[str, Any]] = None
    ) -> Optional[TroubleshootingGuide]:
        """
        Get troubleshooting guide for a specific error code.

        Args:
            error_code: Error code to get guide for
            user_context: Optional user context for personalization

        Returns:
            Troubleshooting guide if available
        """
        guide = self.guides.get(error_code)

        if guide and user_context:
            # Personalize the guide based on user context
            guide = self._personalize_guide(guide, user_context)

        return guide

    def get_quick_fix_suggestions(self, error_code: str) -> List[str]:
        """
        Get quick fix suggestions for common issues.

        Args:
            error_code: Error code to get suggestions for

        Returns:
            List of quick fix suggestions
        """
        quick_fixes = {
            "AZURE_TOKEN_EXPIRED": [
                "Sign out and sign back in to refresh your session",
                "Clear your browser cache and cookies",
                "Try using an incognito/private browser window",
            ],
            "GITHUB_AUTH_FAILED": [
                "Reconnect your GitHub account in profile settings",
                "Check if your GitHub account has the necessary permissions",
                "Verify your GitHub account is not suspended",
            ],
            "WEBSOCKET_CONNECTION_FAILED": [
                "Refresh the page to re-establish connection",
                "Check your internet connection",
                "Disable browser extensions that might block WebSockets",
            ],
            "RATE_LIMIT_EXCEEDED": [
                "Wait a few minutes before trying again",
                "Reduce the frequency of your requests",
                "Contact support if you need higher rate limits",
            ],
        }

        return quick_fixes.get(
            error_code,
            [
                "Try refreshing the page",
                "Check your internet connection",
                "Contact support if the issue persists",
            ],
        )

    def get_guides_by_category(
        self, category: TroubleshootingCategory
    ) -> List[TroubleshootingGuide]:
        """
        Get all troubleshooting guides for a specific category.

        Args:
            category: Category to filter by

        Returns:
            List of guides in the category
        """
        return [guide for guide in self.guides.values() if guide.category == category]

    def search_guides(self, query: str) -> List[TroubleshootingGuide]:
        """
        Search troubleshooting guides by keyword.

        Args:
            query: Search query

        Returns:
            List of matching guides
        """
        query_lower = query.lower()
        matching_guides = []

        for guide in self.guides.values():
            if (
                query_lower in guide.title.lower()
                or query_lower in guide.description.lower()
                or query_lower in guide.error_code.lower()
            ):
                matching_guides.append(guide)

        return matching_guides

    def _initialize_guides(self):
        """Initialize all troubleshooting guides."""

        # Azure Entra authentication guides
        self._add_azure_entra_guides()

        # GitHub integration guides
        self._add_github_guides()

        # WebSocket connectivity guides
        self._add_websocket_guides()

        # Security-related guides
        self._add_security_guides()

        # General application guides
        self._add_general_guides()

    def _add_azure_entra_guides(self):
        """Add Azure Entra specific troubleshooting guides."""

        # Token expired guide
        self.guides["AZURE_TOKEN_EXPIRED"] = TroubleshootingGuide(
            error_code="AZURE_TOKEN_EXPIRED",
            title="Azure Authentication Session Expired",
            description="Your Azure authentication session has expired and needs to be renewed.",
            category=TroubleshootingCategory.AUTHENTICATION,
            severity="medium",
            estimated_time="2-3 minutes",
            prerequisites=["Valid Azure account", "Network connectivity"],
            steps=[
                TroubleshootingStep(
                    step_number=1,
                    title="Sign Out",
                    description="Sign out of your current session",
                    action="Click the profile menu and select 'Sign Out'",
                    expected_result="You should be redirected to the login page",
                ),
                TroubleshootingStep(
                    step_number=2,
                    title="Clear Browser Data",
                    description="Clear cached authentication data",
                    action="Clear your browser cache and cookies for this site",
                    expected_result="Browser data is cleared",
                    additional_info="This ensures old authentication tokens are removed",
                ),
                TroubleshootingStep(
                    step_number=3,
                    title="Sign In Again",
                    description="Authenticate with Azure again",
                    action="Click 'Sign In' and complete the Azure authentication flow",
                    expected_result="You should be successfully authenticated and redirected to the dashboard",
                ),
            ],
            related_links=[
                {"title": "Azure Authentication Help", "url": "/help/azure-auth"},
                {"title": "Browser Cache Clearing Guide", "url": "/help/clear-cache"},
            ],
            contact_support=False,
        )

        # Invalid token guide
        self.guides["AZURE_TOKEN_INVALID"] = TroubleshootingGuide(
            error_code="AZURE_TOKEN_INVALID",
            title="Invalid Azure Authentication Token",
            description="The authentication token is invalid or corrupted.",
            category=TroubleshootingCategory.AUTHENTICATION,
            severity="medium",
            estimated_time="3-5 minutes",
            prerequisites=["Valid Azure account"],
            steps=[
                TroubleshootingStep(
                    step_number=1,
                    title="Try Incognito Mode",
                    description="Test authentication in a private browser window",
                    action="Open an incognito/private window and try signing in",
                    expected_result="Authentication should work in incognito mode",
                    additional_info="This helps identify if the issue is with cached data",
                ),
                TroubleshootingStep(
                    step_number=2,
                    title="Clear All Site Data",
                    description="Remove all stored data for this site",
                    action="Go to browser settings and clear all data for this website",
                    expected_result="All cached data is removed",
                    is_technical=True,
                ),
                TroubleshootingStep(
                    step_number=3,
                    title="Restart Browser",
                    description="Close and reopen your browser",
                    action="Close all browser windows and restart the browser",
                    expected_result="Browser starts fresh without cached data",
                ),
                TroubleshootingStep(
                    step_number=4,
                    title="Authenticate Again",
                    description="Complete the authentication process",
                    action="Navigate to the site and sign in with Azure",
                    expected_result="Authentication completes successfully",
                ),
            ],
            related_links=[
                {"title": "Browser Troubleshooting", "url": "/help/browser-issues"},
            ],
            contact_support=True,
            escalation_criteria="If the issue persists after following all steps",
        )

    def _add_github_guides(self):
        """Add GitHub integration troubleshooting guides."""

        # GitHub authentication failed
        self.guides["GITHUB_AUTH_FAILED"] = TroubleshootingGuide(
            error_code="GITHUB_AUTH_FAILED",
            title="GitHub Authentication Failed",
            description="Unable to authenticate with GitHub for repository access.",
            category=TroubleshootingCategory.INTEGRATION,
            severity="medium",
            estimated_time="5-10 minutes",
            prerequisites=["Valid GitHub account", "Repository access permissions"],
            steps=[
                TroubleshootingStep(
                    step_number=1,
                    title="Check GitHub Status",
                    description="Verify GitHub services are operational",
                    action="Visit https://www.githubstatus.com/ to check service status",
                    expected_result="GitHub services should show as operational",
                ),
                TroubleshootingStep(
                    step_number=2,
                    title="Verify Account Access",
                    description="Ensure your GitHub account is accessible",
                    action="Log into GitHub directly at https://github.com",
                    expected_result="You should be able to access your GitHub account",
                ),
                TroubleshootingStep(
                    step_number=3,
                    title="Reconnect GitHub",
                    description="Remove and re-add GitHub integration",
                    action="Go to Profile Settings > Connected Services > Disconnect GitHub, then reconnect",
                    expected_result="GitHub integration should be re-established",
                ),
                TroubleshootingStep(
                    step_number=4,
                    title="Check Permissions",
                    description="Verify repository permissions",
                    action="Ensure you have write access to the target repository",
                    expected_result="You should have appropriate permissions",
                    is_technical=True,
                ),
            ],
            related_links=[
                {"title": "GitHub Integration Guide", "url": "/help/github-setup"},
                {"title": "Repository Permissions", "url": "/help/github-permissions"},
            ],
            contact_support=True,
        )

        # GitHub rate limit
        self.guides["GITHUB_RATE_LIMIT_EXCEEDED"] = TroubleshootingGuide(
            error_code="GITHUB_RATE_LIMIT_EXCEEDED",
            title="GitHub API Rate Limit Exceeded",
            description="Too many requests have been made to GitHub's API.",
            category=TroubleshootingCategory.PERFORMANCE,
            severity="low",
            estimated_time="1-60 minutes (wait time)",
            prerequisites=["GitHub integration"],
            steps=[
                TroubleshootingStep(
                    step_number=1,
                    title="Wait for Reset",
                    description="GitHub rate limits reset automatically",
                    action="Wait for the specified time before making more requests",
                    expected_result="Rate limit should reset after the wait period",
                    additional_info="Rate limits typically reset every hour",
                ),
                TroubleshootingStep(
                    step_number=2,
                    title="Reduce Request Frequency",
                    description="Limit the number of operations",
                    action="Avoid rapid successive GitHub operations",
                    expected_result="Fewer rate limit errors",
                ),
                TroubleshootingStep(
                    step_number=3,
                    title="Batch Operations",
                    description="Combine multiple changes into single commits",
                    action="Group related file changes together",
                    expected_result="More efficient use of API calls",
                    is_technical=True,
                ),
            ],
            related_links=[
                {
                    "title": "GitHub Rate Limits",
                    "url": "https://docs.github.com/en/rest/overview/resources-in-the-rest-api#rate-limiting",
                },
            ],
            contact_support=False,
        )

    def _add_websocket_guides(self):
        """Add WebSocket connectivity troubleshooting guides."""

        # WebSocket connection failed
        self.guides["WEBSOCKET_CONNECTION_FAILED"] = TroubleshootingGuide(
            error_code="WEBSOCKET_CONNECTION_FAILED",
            title="Real-time Connection Failed",
            description="Unable to establish real-time connection for live updates.",
            category=TroubleshootingCategory.CONNECTIVITY,
            severity="medium",
            estimated_time="5-10 minutes",
            prerequisites=["Network connectivity", "Modern browser"],
            steps=[
                TroubleshootingStep(
                    step_number=1,
                    title="Refresh the Page",
                    description="Reload the page to retry connection",
                    action="Press F5 or click the browser refresh button",
                    expected_result="Page reloads and attempts to reconnect",
                ),
                TroubleshootingStep(
                    step_number=2,
                    title="Check Network Connection",
                    description="Verify internet connectivity",
                    action="Try accessing other websites to confirm connectivity",
                    expected_result="Other websites should load normally",
                ),
                TroubleshootingStep(
                    step_number=3,
                    title="Disable Browser Extensions",
                    description="Some extensions can block WebSocket connections",
                    action="Temporarily disable ad blockers and security extensions",
                    expected_result="Extensions are disabled",
                    additional_info="Re-enable extensions after testing",
                ),
                TroubleshootingStep(
                    step_number=4,
                    title="Check Firewall Settings",
                    description="Ensure WebSocket traffic is allowed",
                    action="Verify firewall allows WebSocket connections on port 443/80",
                    expected_result="WebSocket traffic is permitted",
                    is_technical=True,
                ),
                TroubleshootingStep(
                    step_number=5,
                    title="Try Different Browser",
                    description="Test with another browser",
                    action="Open the application in a different browser",
                    expected_result="Connection should work in another browser",
                ),
            ],
            related_links=[
                {"title": "WebSocket Support", "url": "/help/websocket-support"},
                {
                    "title": "Browser Compatibility",
                    "url": "/help/browser-compatibility",
                },
            ],
            contact_support=True,
            escalation_criteria="If connection fails in multiple browsers",
        )

    def _add_security_guides(self):
        """Add security-related troubleshooting guides."""

        # Suspicious activity detected
        self.guides["SUSPICIOUS_ACTIVITY_DETECTED"] = TroubleshootingGuide(
            error_code="SUSPICIOUS_ACTIVITY_DETECTED",
            title="Suspicious Activity Detected",
            description="Unusual activity has been detected on your account.",
            category=TroubleshootingCategory.SECURITY,
            severity="high",
            estimated_time="10-15 minutes",
            prerequisites=["Account access"],
            steps=[
                TroubleshootingStep(
                    step_number=1,
                    title="Review Recent Activity",
                    description="Check your recent account activity",
                    action="Go to Profile Settings > Security > Recent Activity",
                    expected_result="You can see recent login attempts and actions",
                ),
                TroubleshootingStep(
                    step_number=2,
                    title="Verify Legitimate Activity",
                    description="Confirm if the activity was performed by you",
                    action="Review the flagged activities and timestamps",
                    expected_result="You can identify which activities are legitimate",
                ),
                TroubleshootingStep(
                    step_number=3,
                    title="Change Password",
                    description="Update your account password as a precaution",
                    action="Go to your Azure account settings and change your password",
                    expected_result="Password is successfully updated",
                    additional_info="Use a strong, unique password",
                ),
                TroubleshootingStep(
                    step_number=4,
                    title="Enable Two-Factor Authentication",
                    description="Add an extra layer of security",
                    action="Enable 2FA in your Azure account settings",
                    expected_result="Two-factor authentication is active",
                ),
                TroubleshootingStep(
                    step_number=5,
                    title="Review Connected Devices",
                    description="Check for unauthorized device access",
                    action="Review and remove any unrecognized devices from your account",
                    expected_result="Only your devices have access",
                ),
            ],
            related_links=[
                {"title": "Account Security Guide", "url": "/help/account-security"},
                {"title": "Two-Factor Authentication Setup", "url": "/help/2fa-setup"},
            ],
            contact_support=True,
            escalation_criteria="If you identify unauthorized activity",
        )

    def _add_general_guides(self):
        """Add general application troubleshooting guides."""

        # Service unavailable
        self.guides["SERVICE_UNAVAILABLE"] = TroubleshootingGuide(
            error_code="SERVICE_UNAVAILABLE",
            title="Service Temporarily Unavailable",
            description="The service is temporarily unavailable due to maintenance or high load.",
            category=TroubleshootingCategory.CONNECTIVITY,
            severity="low",
            estimated_time="5-30 minutes (wait time)",
            prerequisites=["Network connectivity"],
            steps=[
                TroubleshootingStep(
                    step_number=1,
                    title="Wait and Retry",
                    description="Service issues are usually temporary",
                    action="Wait 5-10 minutes and try again",
                    expected_result="Service should become available",
                ),
                TroubleshootingStep(
                    step_number=2,
                    title="Check Service Status",
                    description="Verify if there are known issues",
                    action="Check our status page for service updates",
                    expected_result="You can see current service status",
                ),
                TroubleshootingStep(
                    step_number=3,
                    title="Try Different Network",
                    description="Test with different internet connection",
                    action="Try accessing from mobile data or different WiFi",
                    expected_result="Service works on different network",
                ),
            ],
            related_links=[
                {"title": "Service Status", "url": "/status"},
            ],
            contact_support=True,
            escalation_criteria="If service remains unavailable for more than 30 minutes",
        )

    def _personalize_guide(
        self, guide: TroubleshootingGuide, user_context: Dict[str, Any]
    ) -> TroubleshootingGuide:
        """
        Personalize a troubleshooting guide based on user context.

        Args:
            guide: Original guide
            user_context: User context information

        Returns:
            Personalized guide
        """
        # Create a copy of the guide
        personalized_guide = TroubleshootingGuide(
            error_code=guide.error_code,
            title=guide.title,
            description=guide.description,
            category=guide.category,
            severity=guide.severity,
            estimated_time=guide.estimated_time,
            prerequisites=guide.prerequisites.copy(),
            steps=[
                TroubleshootingStep(
                    step_number=step.step_number,
                    title=step.title,
                    description=step.description,
                    action=step.action,
                    expected_result=step.expected_result,
                    additional_info=step.additional_info,
                    is_technical=step.is_technical,
                )
                for step in guide.steps
            ],
            related_links=guide.related_links.copy(),
            contact_support=guide.contact_support,
            escalation_criteria=guide.escalation_criteria,
        )

        # Filter technical steps based on user role
        user_role = user_context.get("role", "user")
        if user_role not in ["admin", "developer"]:
            personalized_guide.steps = [
                step for step in personalized_guide.steps if not step.is_technical
            ]

        return personalized_guide


# Global instance
troubleshooting_guide_service = TroubleshootingGuideService()
