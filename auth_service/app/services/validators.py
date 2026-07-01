"""
Input Validation Schemas
Uses marshmallow for declarative field-level validation.
Schemas are reused by services — never duplicate validation logic in routes.
"""

import re
from marshmallow import Schema, fields, validate, validates, ValidationError


# ── Reusable validators ────────────────────────────────────────────────────────

def _validate_email_format(value: str) -> None:
    """Strict RFC-5322-inspired email check (faster than regex in 99% of cases)."""
    pattern = r"^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$"
    if not re.match(pattern, value):
        raise ValidationError("Invalid email format.")


def _validate_password_strength(value: str) -> None:
    """
    Enforce basic password policy:
    - At least 8 characters
    - Contains at least one uppercase letter
    - Contains at least one digit
    """
    if len(value) < 8:
        raise ValidationError("Password must be at least 8 characters long.")
    if not re.search(r"[A-Z]", value):
        raise ValidationError("Password must contain at least one uppercase letter.")
    if not re.search(r"\d", value):
        raise ValidationError("Password must contain at least one digit.")


# ── Registration Schema ────────────────────────────────────────────────────────

class RegisterSchema(Schema):
    """Validates the POST /api/auth/register request body."""

    name = fields.Str(
        required=True,
        validate=validate.Length(min=2, max=120, error="Name must be 2–120 characters."),
        error_messages={"required": "Name is required."},
    )

    email = fields.Email(
        required=True,
        error_messages={"required": "Email is required.", "invalid": "Invalid email address."},
    )

    password = fields.Str(
        required=True,
        load_only=True,  # never serialize/expose password
        error_messages={"required": "Password is required."},
    )

    @validates("email")
    def validate_email_field(self, value: str) -> None:
        _validate_email_format(value)

    @validates("password")
    def validate_password_field(self, value: str) -> None:
        _validate_password_strength(value)


# ── Login Schema ───────────────────────────────────────────────────────────────

class LoginSchema(Schema):
    """Validates the POST /api/auth/login request body."""

    email = fields.Email(
        required=True,
        error_messages={"required": "Email is required.", "invalid": "Invalid email address."},
    )

    password = fields.Str(
        required=True,
        load_only=True,
        error_messages={"required": "Password is required."},
    )


# ── Singleton instances (reuse across requests) ────────────────────────────────
register_schema = RegisterSchema()
login_schema = LoginSchema()
