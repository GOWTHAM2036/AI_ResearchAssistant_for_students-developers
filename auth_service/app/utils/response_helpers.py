"""
Response Helpers
Standardised JSON response envelope to keep all API responses consistent.

Success envelope:
    { "success": true, "data": { ... }, "message": "..." }

Error envelope:
    { "success": false, "error": "...", "details": { ... } }
"""

from flask import jsonify
from typing import Any


def success_response(data: Any = None, message: str = "OK", status_code: int = 200):
    """
    Build a standardised success response.

    Args:
        data:        Payload to return (dict, list, or None).
        message:     Human-readable status message.
        status_code: HTTP status code (default 200).

    Returns:
        Flask Response with JSON body and correct status.
    """
    body = {
        "success": True,
        "message": message,
    }
    if data is not None:
        body["data"] = data

    return jsonify(body), status_code


def error_response(error: str, details: Any = None, status_code: int = 400):
    """
    Build a standardised error response.

    Args:
        error:       Short error description (e.g. "Email already registered").
        details:     Optional structured error details (e.g. field-level errors).
        status_code: HTTP status code (default 400).

    Returns:
        Flask Response with JSON body and correct status.
    """
    body: dict = {
        "success": False,
        "error": error,
    }
    if details is not None:
        body["details"] = details

    return jsonify(body), status_code
