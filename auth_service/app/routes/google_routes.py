"""
Google OAuth Routes
Blueprint: google_bp — prefix /api/auth/google

Flow:
  1. Frontend uses Google Identity Services (GSI) to get an ID token
  2. Frontend POSTs { "credential": "<id_token>" } to /api/auth/google
  3. Backend verifies the token with Google, creates/finds the user, returns JWT
"""

import os
import logging
import requests as http_requests
from flask import Blueprint, request, current_app

from ..extensions import db
from ..models.user import User
from ..utils.jwt_utils import generate_access_token
from ..utils.response_helpers import success_response, error_response

logger = logging.getLogger(__name__)

google_bp = Blueprint("google_auth", __name__)

# Google token verification endpoint
GOOGLE_TOKEN_INFO_URL = "https://oauth2.googleapis.com/tokeninfo"


@google_bp.route("", methods=["POST"])
def google_login():
    """
    Authenticate via Google ID token.

    Request body (JSON):
        { "credential": "<google_id_token>" }

    The token is verified by calling Google's tokeninfo endpoint.
    If valid, the user is created (if new) or logged in (if existing).

    Responses:
        200 — Login successful, returns JWT + user data
        400 — Missing or invalid token
        401 — Token verification failed
        500 — Unexpected error
    """
    payload = request.get_json(silent=True)
    if not payload or not payload.get("credential"):
        return error_response("Google credential token is required.", status_code=400)

    id_token = payload["credential"]

    try:
        # ── Verify token with Google ──────────────────────────────────────────
        google_resp = http_requests.get(
            GOOGLE_TOKEN_INFO_URL,
            params={"id_token": id_token},
            timeout=10,
        )

        if google_resp.status_code != 200:
            print(f"[GOOGLE AUTH ERROR] Google token verification failed (status {google_resp.status_code}): {google_resp.text}", flush=True)
            logger.warning("Google token verification failed: %s", google_resp.text)
            return error_response(f"Invalid Google token: {google_resp.text}", status_code=401)

        google_data = google_resp.json()

        # Validate the audience (client ID) matches ours
        expected_client_id = current_app.config.get("GOOGLE_CLIENT_ID", "")
        if expected_client_id and google_data.get("aud") != expected_client_id:
            print(f"[GOOGLE AUTH ERROR] Token audience mismatch. Expected: {expected_client_id}, Got: {google_data.get('aud')}", flush=True)
            return error_response("Token audience mismatch.", status_code=401)

        google_sub = google_data.get("sub")       # unique Google user ID
        email = google_data.get("email", "")
        name = google_data.get("name", email.split("@")[0] if email else "Google User")

        if not google_sub:
            print("[GOOGLE AUTH ERROR] Invalid token payload: missing 'sub' claim.", flush=True)
            return error_response("Invalid token payload.", status_code=401)

        # ── Find or create user ───────────────────────────────────────────────
        user = User.query.filter_by(google_id=google_sub).first()

        if not user and email:
            # Check if a user with this email already exists (registered via email)
            user = User.query.filter(db.func.lower(User.email) == email.lower()).first()
            if user:
                # Link Google account to existing user
                user.google_id = google_sub
                if user.auth_provider == "email":
                    user.auth_provider = "email"  # keep original provider
                db.session.commit()

        if not user:
            # Create new user from Google data
            user = User(
                name=name,
                email=email.lower() if email else None,
                google_id=google_sub,
                auth_provider="google",
                password_hash=None,   # Google users don't have a password
            )
            db.session.add(user)
            db.session.commit()
            logger.info("New Google user created: id=%s email=%s", user.id, user.email)

        # ── Generate JWT ──────────────────────────────────────────────────────
        token = generate_access_token(
            identity=user.id,
            additional_claims={"email": user.email, "name": user.name, "provider": "google"},
        )

        return success_response(
            data={
                "access_token": token,
                "token_type": "Bearer",
                "user": user.to_dict(),
            },
            message="Google login successful.",
            status_code=200,
        )

    except http_requests.RequestException as exc:
        logger.error("Failed to verify Google token: %s", exc)
        return error_response("Could not verify Google token. Try again.", status_code=500)

    except Exception as exc:
        logger.exception("Unexpected error during Google login: %s", exc)
        return error_response("An unexpected error occurred.", status_code=500)
