"""
auth.py — Simulated authentication and access control.
Maps email IDs to the companies they are allowed to access.
"""

import uuid
from typing import Optional 

# ---------------------------------------------------------------------------
# User → Company Access Map
# Adjust company keys to match exactly what you tag PDFs with during ingestion
# ---------------------------------------------------------------------------
USER_ACCESS: dict[str, list[str]] = {
    "alice@email.com":   ["GOOGLE"],
    "bob@email.com":     ["AMD", "META"],
    "charlie@email.com": ["MSFT", "NFLX"],
}

# In-memory session store: token → email
_sessions: dict[str, str] = {}


def login(email: str) -> Optional[dict]:
    """
    Simulate login. Returns a session token + allowed companies if the
    email is recognised, else None.
    """
    email = email.strip().lower()
    if email not in USER_ACCESS:
        return None

    token = str(uuid.uuid4())
    _sessions[token] = email
    return {
        "token": token,
        "email": email,
        "allowed_companies": USER_ACCESS[email],
    }


def get_user(token: str) -> Optional[dict]:
    """Return user info for a valid session token, else None."""
    email = _sessions.get(token)
    if not email:
        return None
    return {
        "email": email,
        "allowed_companies": USER_ACCESS[email],
    }


def logout(token: str) -> bool:
    """Invalidate a session token."""
    return _sessions.pop(token, None) is not None


def list_users() -> list[str]:
    """Return all known user emails (for testing)."""
    return list(USER_ACCESS.keys())
