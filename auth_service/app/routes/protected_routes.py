"""
Protected Routes
Blueprint: protected_bp — prefix /api

Demonstrates JWT-guarded endpoints.
Add all routes that require authentication to this blueprint.
"""

import logging
from flask import Blueprint
from flask_jwt_extended import jwt_required

from ..extensions import db
from ..utils.jwt_utils import get_current_user_id, get_jwt_claims
from ..utils.response_helpers import success_response, error_response
from ..models.user import User

logger = logging.getLogger(__name__)

protected_bp = Blueprint("protected", __name__)


# ── GET /api/protected ─────────────────────────────────────────────────────────

@protected_bp.route("/protected", methods=["GET"])
@jwt_required()  # returns 401 automatically if token is missing or invalid
def protected():
    """
    A sample protected resource — requires a valid Bearer token.

    Headers:
        Authorization: Bearer <access_token>

    Responses:
        200 — Returns the authenticated user's profile
        401 — Missing, expired, or invalid token
        404 — User not found (token valid but user deleted from DB)
    """
    user_id = get_current_user_id()
    claims = get_jwt_claims()

    # Optionally fetch fresh data from DB (ensures user still exists / isn't banned)
    user = db.session.get(User, int(user_id))
    if not user:
        return error_response("User not found.", status_code=404)

    logger.info("Protected resource accessed by user_id=%s", user_id)

    return success_response(
        data={
            "user": user.to_dict(),
            "token_claims": {
                "sub": claims.get("sub"),
                "exp": claims.get("exp"),
                "email": claims.get("email"),
            },
        },
        message="Access granted.",
    )


# ── GET /api/me ────────────────────────────────────────────────────────────────

@protected_bp.route("/me", methods=["GET"])
@jwt_required()
def me():
    """
    Returns the currently authenticated user's profile.
    Alias for /protected — a common convention in REST APIs.

    Headers:
        Authorization: Bearer <access_token>
    """
    user_id = get_current_user_id()
    user = db.session.get(User, int(user_id))
    if not user:
        return error_response("User not found.", status_code=404)

    return success_response(data={"user": user.to_dict()})
