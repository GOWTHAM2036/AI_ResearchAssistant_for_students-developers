"""
Authentication Routes
Blueprint: auth_bp — prefix /api/auth

Endpoints:
    POST /api/auth/register  → Create new user account
    POST /api/auth/login     → Authenticate and receive JWT
    POST /api/auth/logout    → Logout (client-side token discard + notes)
"""

import logging
from flask import Blueprint, request
from marshmallow import ValidationError

from ..services.auth_service import register_user, login_user, AuthError
from ..utils.response_helpers import success_response, error_response

logger = logging.getLogger(__name__)

auth_bp = Blueprint("auth", __name__)


# ── POST /api/auth/register ────────────────────────────────────────────────────

@auth_bp.route("/register", methods=["POST"])
def register():
    """
    Register a new user.

    Request body (JSON):
        {
            "name":     "Alice Smith",
            "email":    "alice@example.com",
            "password": "Secret123"
        }

    Responses:
        201 — User created successfully
        400 — Validation error (missing / invalid fields)
        409 — Email already registered
        500 — Unexpected server error
    """
    payload = request.get_json(silent=True)
    if not payload:
        return error_response("Request body must be valid JSON.", status_code=400)

    try:
        user = register_user(payload)
        logger.info("New user registered: id=%s email=%s", user["id"], user["email"])
        return success_response(
            data={"user": user},
            message="Account created successfully.",
            status_code=201,
        )

    except AuthError as exc:
        return error_response(exc.message, status_code=exc.status_code)

    except Exception as exc:  # noqa: BLE001
        logger.exception("Unexpected error during registration: %s", exc)
        return error_response("An unexpected error occurred.", status_code=500)


# ── POST /api/auth/login ───────────────────────────────────────────────────────

@auth_bp.route("/login", methods=["POST"])
def login():
    """
    Authenticate a user and return a JWT access token.

    Request body (JSON):
        {
            "email":    "alice@example.com",
            "password": "Secret123"
        }

    Responses:
        200 — Login successful; returns access_token
        400 — Validation error
        401 — Invalid credentials
        500 — Unexpected server error
    """
    payload = request.get_json(silent=True)
    if not payload:
        return error_response("Request body must be valid JSON.", status_code=400)

    try:
        result = login_user(payload)
        logger.info("User logged in: email=%s", payload.get("email"))
        return success_response(
            data=result,
            message="Login successful.",
            status_code=200,
        )

    except AuthError as exc:
        return error_response(exc.message, status_code=exc.status_code)

    except Exception as exc:  # noqa: BLE001
        logger.exception("Unexpected error during login: %s", exc)
        return error_response("An unexpected error occurred.", status_code=500)


# ── POST /api/auth/logout ──────────────────────────────────────────────────────

@auth_bp.route("/logout", methods=["POST"])
def logout():
    """
    Logout endpoint.

    Strategy: The client discards the token locally (stateless logout).
    For server-side invalidation, implement a token blocklist in Redis/DB and
    call blocklist_token(get_jwt()["jti"]) here before responding.

    Responses:
        200 — Logout acknowledged
    """
    # NOTE: For a server-side blocklist, add:
    #   from flask_jwt_extended import jwt_required, get_jwt
    #   jti = get_jwt()["jti"]
    #   blocklist.add(jti)  # store in Redis / DB
    return success_response(
        message="Logged out successfully. Please delete the token on the client.",
        status_code=200,
    )
