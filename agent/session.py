import json
import os
import sys
import time
import urllib.request

# Ensure root directory is in sys.path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import config

class UserSession:
    """
    Manages authenticated session state, live API tokens, and RBAC permissions.
    """
    def __init__(self):
        self.email = config.DEFAULT_USER_EMAIL
        self.password = config.DEFAULT_USER_PASSWORD
        self.company_id = config.DEFAULT_USER_COMPANY
        self.token = None
        self.user_data = None
        self.token_expiry = None
        # Default active permissions for authenticated user
        # 'profile.update' can be revoked to test Scenario 05 (Unauthorized Update)
        self.permissions = ["profile.view", "profile.update", "service.view", "service.create"]

    def login(self, force: bool = False) -> bool:
        """Authenticates with the existing Laravel business system API."""
        if not force and self.token and self.token_expiry and time.time() < self.token_expiry:
            return True

        login_url = f"{config.API_BASE_URL}/login"
        payload = json.dumps({
            "email": self.email,
            "password": self.password,
            "company_id": self.company_id
        }).encode("utf-8")

        req = urllib.request.Request(
            login_url,
            data=payload,
            headers={"Content-Type": "application/json", "Accept": "application/json"}
        )

        try:
            with urllib.request.urlopen(req, timeout=10) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                if data.get("status") is True or data.get("success") is True:
                    token_info = data["data"]
                    self.token = token_info.get("access_token") or token_info.get("token")
                    if self.token and self.token.startswith("Bearer "):
                        self.token = self.token[7:]
                    self.user_data = token_info.get("passenger") or token_info.get("user")
                    # Set token expiration (typically 14 days, setting 24h safe buffer)
                    self.token_expiry = time.time() + 86400
                    print(f"[Session] Logged in successfully as {self.email} (ID: {self.user_data.get('id')})")
                    return True
                else:
                    print(f"[Session] Login failed: {data.get('message')}")
                    return False
        except Exception as e:
            print(f"[Session] Login exception: {e}")
            return False

    def get_token(self) -> str:
        """Returns valid Bearer access token, refreshing if needed."""
        if not self.token or not self.token_expiry or time.time() >= self.token_expiry:
            self.login()
        return self.token

    def has_permission(self, permission: str) -> bool:
        """Checks if active session possesses the requested permission."""
        return permission in self.permissions

    def grant_permission(self, permission: str):
        if permission not in self.permissions:
            self.permissions.append(permission)

    def revoke_permission(self, permission: str):
        if permission in self.permissions:
            self.permissions.remove(permission)

    def set_permissions(self, permissions: list[str]):
        self.permissions = list(permissions)

    def reset_default(self):
        """Resets permissions to default authorized state."""
        self.permissions = ["profile.view", "profile.update", "service.view", "service.create"]

    def get_summary(self) -> dict:
        """Returns safe summary of current session (never exposing full secret tokens)."""
        if not self.token:
            self.login()

        user_name = "User"
        user_id = None
        user_phone = ""
        if self.user_data:
            first = self.user_data.get("first_name", "")
            last = self.user_data.get("last_name", "")
            user_name = f"{first} {last}".strip() or self.user_data.get("name", "User")
            user_id = self.user_data.get("id")
            user_phone = self.user_data.get("cellular_phone_1", "")

        return {
            "authenticated": self.token is not None,
            "user_id": user_id,
            "name": user_name,
            "email": self.email,
            "phone": user_phone,
            "company_id": self.company_id,
            "permissions": list(self.permissions),
            "can_update_profile": self.has_permission("profile.update"),
            "token_masked": f"{self.token[:8]}...{self.token[-6:]}" if self.token else None
        }

# Global session instance
_session_instance = None

def get_current_session() -> UserSession:
    global _session_instance
    if _session_instance is None:
        _session_instance = UserSession()
        _session_instance.login()
    return _session_instance
