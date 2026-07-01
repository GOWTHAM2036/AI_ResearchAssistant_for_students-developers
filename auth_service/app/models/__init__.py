"""Models package — export all models so Flask-Migrate can detect them."""

from .user import User

__all__ = ["User"]
