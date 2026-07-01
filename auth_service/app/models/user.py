"""
User Model
Represents the `users` table. Schema is database-agnostic (SQLite & PostgreSQL).
Supports email/password, Google OAuth, and phone-number login.
"""

from datetime import datetime, timezone
from ..extensions import db


class User(db.Model):
    """
    ORM model for the `users` table.

    Columns:
        id            — Auto-increment primary key
        name          — User's display name
        email         — Unique login identifier (indexed for fast lookups)
        password_hash — bcrypt hash; plain text is NEVER stored (nullable for OAuth/phone users)
        phone         — Phone number (optional, unique if provided)
        google_id     — Google account sub (unique, set when user logs in via Google)
        auth_provider — How the user registered: 'email', 'google', or 'phone'
        created_at    — UTC timestamp of account creation
    """

    __tablename__ = "users"

    # ── Core columns ──────────────────────────────────────────────────────────
    id: int = db.Column(db.Integer, primary_key=True, autoincrement=True)

    name: str = db.Column(
        db.String(120),
        nullable=False,
    )

    email: str = db.Column(
        db.String(255),
        nullable=True,   # phone-only users may not have email initially
        unique=True,
        index=True,
    )

    password_hash: str = db.Column(
        db.String(255),
        nullable=True,   # Google/phone users don't have a password
    )

    # ── OAuth & phone columns ─────────────────────────────────────────────────
    phone: str = db.Column(
        db.String(20),
        nullable=True,
        unique=True,
        index=True,
    )

    google_id: str = db.Column(
        db.String(255),
        nullable=True,
        unique=True,
    )

    auth_provider: str = db.Column(
        db.String(20),
        nullable=False,
        default="email",   # 'email' | 'google' | 'phone'
    )

    created_at: datetime = db.Column(
        db.DateTime,
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )

    # ── Representation ────────────────────────────────────────────────────────
    def __repr__(self) -> str:
        return f"<User id={self.id} email={self.email!r} provider={self.auth_provider}>"

    # ── Serialization ─────────────────────────────────────────────────────────
    def to_dict(self) -> dict:
        """Return a safe public representation (no password_hash)."""
        result = {
            "id": self.id,
            "name": self.name,
            "email": self.email,
            "auth_provider": self.auth_provider,
            "created_at": self.created_at.isoformat(),
        }
        if self.phone:
            result["phone"] = self.phone
        return result
