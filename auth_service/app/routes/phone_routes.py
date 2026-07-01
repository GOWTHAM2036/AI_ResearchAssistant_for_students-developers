"""
Phone OTP Routes
Blueprint: phone_bp — prefix /api/auth/phone

Flow:
  1. User enters phone number → POST /api/auth/phone/send-otp
  2. Server generates a 6-digit OTP, stores it in memory (dev) or sends via SMS (prod)
  3. User enters OTP → POST /api/auth/phone/verify-otp
  4. Server verifies OTP, creates/finds user, returns JWT

NOTE: In development, the OTP is returned in the response for testing.
      In production, integrate Twilio / AWS SNS / similar SMS service.
"""

import os
import random
import time
import logging
from flask import Blueprint, request

from ..extensions import db
from ..models.user import User
from ..utils.jwt_utils import generate_access_token
from ..utils.response_helpers import success_response, error_response

logger = logging.getLogger(__name__)

phone_bp = Blueprint("phone_auth", __name__)

# ── In-memory OTP store (dev only — use Redis/DB in production) ────────────
# Format: { "+1234567890": { "otp": "123456", "expires": <timestamp>, "attempts": 0 } }
_otp_store: dict = {}

OTP_LENGTH = 6
OTP_EXPIRY_SECONDS = 300   # 5 minutes
MAX_VERIFY_ATTEMPTS = 5    # lock out after 5 wrong attempts


def _generate_otp() -> str:
    """Generate a cryptographically-reasonable 6-digit OTP."""
    return str(random.randint(100000, 999999))


def _normalize_phone(phone: str) -> str:
    """Basic phone normalization — strip spaces, ensure + prefix."""
    phone = phone.strip().replace(" ", "").replace("-", "")
    if not phone.startswith("+"):
        # Assume Indian number if no country code
        if len(phone) == 10:
            phone = "+91" + phone
        else:
            phone = "+" + phone
    return phone


def _cleanup_expired():
    """Remove expired OTPs from the store."""
    now = time.time()
    expired = [k for k, v in _otp_store.items() if v["expires"] < now]
    for k in expired:
        del _otp_store[k]


# ── POST /api/auth/phone/send-otp ─────────────────────────────────────────

@phone_bp.route("/send-otp", methods=["POST"])
def send_otp():
    """
    Generate and send an OTP to the given phone number.

    Request body (JSON):
        { "phone": "+919876543210" }

    In development, the OTP is included in the response for testing.
    In production, this would trigger an SMS via Twilio/AWS SNS.

    Responses:
        200 — OTP sent successfully
        400 — Invalid phone number
        429 — Rate limited (OTP already sent recently)
    """
    payload = request.get_json(silent=True)
    if not payload or not payload.get("phone"):
        return error_response("Phone number is required.", status_code=400)

    phone = _normalize_phone(payload["phone"])

    # Basic validation
    if len(phone) < 10 or not phone[1:].isdigit():
        return error_response("Invalid phone number format. Use +<country_code><number>.", status_code=400)

    _cleanup_expired()

    # Rate limiting: don't send another OTP if one was sent in last 60 seconds
    existing = _otp_store.get(phone)
    if existing and existing["expires"] - OTP_EXPIRY_SECONDS + 60 > time.time():
        return error_response(
            "OTP already sent. Please wait before requesting a new one.",
            status_code=429,
        )

    # Generate OTP
    otp = _generate_otp()
    _otp_store[phone] = {
        "otp": otp,
        "expires": time.time() + OTP_EXPIRY_SECONDS,
        "attempts": 0,
    }

    logger.info("OTP generated for %s: %s", phone, otp)

    # ── In production, send SMS here: ──
    # twilio_client.messages.create(body=f"Your OTP: {otp}", to=phone, from_=TWILIO_FROM)

    response_data = {
        "phone": phone,
        "message": "OTP sent successfully.",
        "expires_in": OTP_EXPIRY_SECONDS,
    }

    # Include OTP in response ONLY in development (for testing convenience)
    is_dev = os.environ.get("FLASK_ENV", "development") == "development"
    if is_dev:
        response_data["otp_dev_only"] = otp

    return success_response(data=response_data, message="OTP sent.", status_code=200)


# ── POST /api/auth/phone/verify-otp ───────────────────────────────────────

@phone_bp.route("/verify-otp", methods=["POST"])
def verify_otp():
    """
    Verify the OTP and authenticate the user.

    Request body (JSON):
        { "phone": "+919876543210", "otp": "123456", "name": "Optional Name" }

    If the phone number is new, a user account is created automatically.

    Responses:
        200 — OTP verified, returns JWT + user data
        400 — Missing fields
        401 — Invalid or expired OTP
        429 — Too many attempts
    """
    payload = request.get_json(silent=True)
    if not payload:
        return error_response("Request body must be valid JSON.", status_code=400)

    phone = payload.get("phone", "")
    otp_input = payload.get("otp", "")
    name = payload.get("name", "").strip()

    if not phone or not otp_input:
        return error_response("Phone and OTP are required.", status_code=400)

    phone = _normalize_phone(phone)
    _cleanup_expired()

    # Lookup OTP record
    record = _otp_store.get(phone)
    if not record:
        return error_response("No OTP found. Please request a new one.", status_code=401)

    # Check expiry
    if record["expires"] < time.time():
        del _otp_store[phone]
        return error_response("OTP has expired. Please request a new one.", status_code=401)

    # Check attempts
    if record["attempts"] >= MAX_VERIFY_ATTEMPTS:
        del _otp_store[phone]
        return error_response("Too many failed attempts. Request a new OTP.", status_code=429)

    # Verify OTP
    if record["otp"] != otp_input.strip():
        record["attempts"] += 1
        remaining = MAX_VERIFY_ATTEMPTS - record["attempts"]
        return error_response(
            f"Invalid OTP. {remaining} attempt(s) remaining.",
            status_code=401,
        )

    # ── OTP verified — clean up ───────────────────────────────────────────
    del _otp_store[phone]

    # ── Find or create user ───────────────────────────────────────────────
    user = User.query.filter_by(phone=phone).first()

    if not user:
        # Create new phone user
        user = User(
            name=name or f"User {phone[-4:]}",
            phone=phone,
            email=None,           # phone users may not have email
            password_hash=None,   # phone users don't have a password
            auth_provider="phone",
        )
        db.session.add(user)
        db.session.commit()
        logger.info("New phone user created: id=%s phone=%s", user.id, phone)

    # ── Generate JWT ──────────────────────────────────────────────────────
    token = generate_access_token(
        identity=user.id,
        additional_claims={"phone": user.phone, "name": user.name, "provider": "phone"},
    )

    return success_response(
        data={
            "access_token": token,
            "token_type": "Bearer",
            "user": user.to_dict(),
        },
        message="Phone verified. Login successful.",
        status_code=200,
    )
