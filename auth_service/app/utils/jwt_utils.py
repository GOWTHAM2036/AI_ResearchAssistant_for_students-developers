"""
JWT Utility
Centralises token creation and claim extraction.
All JWT logic lives here — routes never import flask_jwt_extended directly.
"""

from flask_jwt_extended import create_access_token, get_jwt_identity, get_jwt
from typing import Any


def generate_access_token(identity: Any, additional_claims: dict | None = None) -> str:
    """
    Generate a signed JWT access token.

    Args:
        identity:          The subject of the token (typically user ID as str).
        additional_claims: Extra claims to embed (e.g., {"email": "..."}).

    Returns:
        Signed JWT string.
    """
    return create_access_token(
        identity=str(identity),
        additional_claims=additional_claims or {},
    )


def get_current_user_id() -> str:
    """
    Extract the user ID from the current request's JWT.
    Must be called inside a @jwt_required() decorated route.

    Returns:
        User ID as a string (matches the identity passed at token creation).
    """
    return get_jwt_identity()


def get_jwt_claims() -> dict:
    """
    Return all claims from the current request's JWT payload.
    Useful for reading additional_claims like email or roles.
    """
    return get_jwt()
