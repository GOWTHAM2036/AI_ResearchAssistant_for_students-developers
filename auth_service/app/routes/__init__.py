"""Routes package."""

from .auth_routes import auth_bp
from .protected_routes import protected_bp
from .google_routes import google_bp
from .phone_routes import phone_bp

__all__ = ["auth_bp", "protected_bp", "google_bp", "phone_bp"]
