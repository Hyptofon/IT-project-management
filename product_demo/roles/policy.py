"""S-02 local teaching fragment: authorization, not authentication or SSO."""

from __future__ import annotations

import json
import os
import tempfile
from enum import Enum
from pathlib import Path
from typing import Callable, TypeVar


class Role(str, Enum):
    APPLICANT = "applicant"
    APPROVER = "approver"
    ADMIN = "admin"


class Action(str, Enum):
    SEARCH = "search"
    SUBMIT_REQUEST = "submit_request"
    READ_OWN_REQUEST = "read_own_request"
    CANCEL_OWN_REQUEST = "cancel_own_request"
    APPROVE_REQUEST = "approve_request"
    EDIT_CATALOG = "edit_catalog"
    ASSIGN_ROLE = "assign_role"


PERMISSIONS = {
    Role.APPLICANT: frozenset({Action.SEARCH, Action.SUBMIT_REQUEST,
                             Action.READ_OWN_REQUEST, Action.CANCEL_OWN_REQUEST}),
    Role.APPROVER: frozenset({Action.APPROVE_REQUEST}),
    Role.ADMIN: frozenset({Action.EDIT_CATALOG, Action.ASSIGN_ROLE}),
}


class AccessDenied(PermissionError):
    """The protected callback must not run after this exception."""


Result = TypeVar("Result")


class RoleStore:
    """Single-process JSON fixture store. The operator controls synthetic identity."""

    def __init__(self, path: Path):
        self.path = Path(path)
        with self.path.open(encoding="utf-8") as stream:
            data = json.load(stream)
        if (not isinstance(data, dict) or set(data) != {"accounts"}
                or not isinstance(data["accounts"], dict)
                or any(not isinstance(key, str) or not key
                       for key in data["accounts"])):
            raise ValueError("Invalid fixture store")
        self._accounts = data["accounts"]

    @classmethod
    def initialize(cls, path: Path) -> RoleStore:
        """Bootstrap synthetic admin only; never overwrite an existing file."""
        data = {"accounts": {"T-admin": "admin", "T-applicant": None,
                             "T-approver": None}}
        with Path(path).open("x", encoding="utf-8") as stream:
            json.dump(data, stream, ensure_ascii=False, indent=2)
            stream.write("\n")
        return cls(path)

    def role_for(self, account: str) -> Role | None:
        try:
            return Role(self._accounts.get(account))
        except (ValueError, TypeError):
            return None

    def allows(self, account: str, action: str | Action) -> bool:
        try:
            operation = Action(action)
        except (ValueError, TypeError):
            return False
        return operation in PERMISSIONS.get(self.role_for(account), frozenset())

    def guarded(self, account: str, action: str | Action,
                operation: Callable[[], Result]) -> Result:
        if not self.allows(account, action):
            raise AccessDenied("Forbidden operation")
        return operation()

    def assign(self, actor: str, subject: str, role: str | Role) -> None:
        if not self.allows(actor, Action.ASSIGN_ROLE):
            raise AccessDenied("Only admin may assign roles")
        value = Role(role)
        if subject not in self._accounts:
            raise ValueError("Unknown synthetic account")
        candidate = dict(self._accounts)
        candidate[subject] = value.value
        # Write a candidate atomically before changing this object's state.
        temporary = None
        try:
            with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8",
                                             dir=self.path.parent, delete=False) as stream:
                temporary = Path(stream.name)
                json.dump({"accounts": candidate}, stream, ensure_ascii=False, indent=2)
                stream.write("\n")
            os.replace(temporary, self.path)
            self._accounts = candidate
        finally:
            if temporary is not None and temporary.exists():
                temporary.unlink()
