"""
Authentication Service
Contains all business logic for registration and login.
Routes are thin — they delegate to this service.
"""

from marshmallow import ValidationError

from ..extensions import db
from ..models.user import User
from ..utils.password_utils import hash_password, verify_password
from ..utils.jwt_utils import generate_access_token
from .validators import register_schema, login_schema


# ── Custom service-level exceptions ───────────────────────────────────────────

class AuthError(Exception):
    """
    Raised when authentication fails due to a business-rule violation.

    Attributes:
        message:     Human-readable error description.
        status_code: HTTP status to return to the client.
    """

    def __init__(self, message: str, status_code: int = 400):
        super().__init__(message)
        self.message = message
        self.status_code = status_code


# ── Registration ───────────────────────────────────────────────────────────────

def register_user(payload: dict) -> dict:
    """
    Validate input, hash password, and persist a new User record.

    Args:
        payload: Raw JSON dict from the request body.

    Returns:
        Safe user dict (no password_hash).

    Raises:
        AuthError: On validation failure or duplicate email (400).
    """
    # 1. Validate input fields
    try:
        data = register_schema.load(payload)
    except ValidationError as exc:
        raise AuthError(
            message="Validation failed.",
            status_code=400,
        ) from exc

    # 2. Check for duplicate email (case-insensitive)
    existing = User.query.filter(
        db.func.lower(User.email) == data["email"].lower()
    ).first()
    if existing:
        raise AuthError("Email is already registered.", status_code=409)

    # 3. Hash password — NEVER store plain text
    password_hash = hash_password(data["password"])

    # 4. Persist user
    user = User(
        name=data["name"].strip(),
        email=data["email"].lower().strip(),
        password_hash=password_hash,
    )
    db.session.add(user)
    db.session.commit()

    return user.to_dict()


# ── Login ──────────────────────────────────────────────────────────────────────

def login_user(payload: dict) -> dict:
    """
    Validate credentials and return a signed JWT access token.

    Args:
        payload: Raw JSON dict from the request body.

    Returns:
        Dict containing the access_token and user info.

    Raises:
        AuthError: On validation failure (400) or bad credentials (401).
    """
    # 1. Validate input fields
    try:
        data = login_schema.load(payload)
    except ValidationError as exc:
        raise AuthError("Validation failed.", status_code=400) from exc

    # 2. Lookup user (always case-insensitive)
    user = User.query.filter(
        db.func.lower(User.email) == data["email"].lower()
    ).first()

    # 3. Verify password — use constant-time comparison via bcrypt
    #    Use the same error message for both "user not found" and "wrong password"
    #    to prevent user-enumeration attacks.
    if not user or not verify_password(data["password"], user.password_hash):
        raise AuthError("Invalid email or password.", status_code=401)

    # 4. Generate JWT with user ID as identity and email as additional claim
    token = generate_access_token(
        identity=user.id,
        additional_claims={"email": user.email, "name": user.name},
    )

    return {
        "access_token": token,
        "token_type": "Bearer",
        "user": user.to_dict(),
    }
