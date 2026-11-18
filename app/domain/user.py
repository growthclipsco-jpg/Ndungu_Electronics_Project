"""
User domain model matching Milestone 2 Class Diagram (Fig 1.3.6).
Encapsulates role-based authorization (Owner vs Attendant) and lockout rules.
"""

from datetime import datetime
from typing import Optional


class User:
    """Represents a system user (Owner or Attendant) with RBAC logic."""

    ROLE_OWNER = "owner"
    ROLE_ATTENDANT = "attendant"
    MAX_FAILED_ATTEMPTS = 5
    LOCKOUT_DURATION_MINUTES = 15

    def __init__(
        self,
        user_id: int,
        username: str,
        password_hash: str,
        role: str = ROLE_ATTENDANT,
        full_name: str = "",
        is_active: bool = True,
        must_change_password: bool = False,
        failed_login_attempts: int = 0,
        locked_until: Optional[str] = None,
        created_at: Optional[str] = None
    ):
        self.user_id = user_id
        self.username = username
        self.password_hash = password_hash
        self.role = role
        self.full_name = full_name
        self.is_active = bool(is_active)
        self.must_change_password = bool(must_change_password)
        self.failed_login_attempts = failed_login_attempts
        self.locked_until = locked_until
        self.created_at = created_at

    @property
    def is_owner(self) -> bool:
        return self.role == self.ROLE_OWNER

    @property
    def is_attendant(self) -> bool:
        return self.role == self.ROLE_ATTENDANT

    def can_manage_catalog(self) -> bool:
        """Only the owner can create, edit, or archive products and categories."""
        return self.is_owner

    def can_manage_promotions(self) -> bool:
        """Only the owner can configure promotional discounts."""
        return self.is_owner

    def can_manage_users(self) -> bool:
        """Only the owner can create invite tokens and manage attendants."""
        return self.is_owner

    def can_void_sale(self) -> bool:
        """Only the owner can void completed sales."""
        return self.is_owner

    def can_process_sales(self) -> bool:
        """Both owner and active attendant can operate the POS register."""
        return self.is_active

    def is_locked(self, current_time: Optional[datetime] = None) -> bool:
        """Checks whether the user account is currently locked out."""
        if not self.locked_until:
            return False
        now = current_time or datetime.now()
        try:
            lock_time = datetime.fromisoformat(self.locked_until)
            return now < lock_time
        except (ValueError, TypeError):
            return False

    def __repr__(self) -> str:
        return f"<User {self.username} (role={self.role}, active={self.is_active})>"
