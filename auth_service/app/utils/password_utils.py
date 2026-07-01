"""
Password Utility
Wraps Flask-Bcrypt to keep hashing logic in one place.
Changing the hashing library only requires edits here.
"""

from ..extensions import bcrypt


def hash_password(plain_text: str) -> str:
    """
    Hash a plain-text password using bcrypt.

    Args:
        plain_text: The user's raw password.

    Returns:
        A bcrypt hash string safe to store in the database.
    """
    # generate_password_hash returns bytes; decode to str for SQLAlchemy String column
    return bcrypt.generate_password_hash(plain_text).decode("utf-8")


def verify_password(plain_text: str, password_hash: str) -> bool:
    """
    Verify a plain-text password against its stored hash.

    Args:
        plain_text:    The password submitted by the user.
        password_hash: The bcrypt hash retrieved from the database.

    Returns:
        True if the passwords match, False otherwise.
    """
    return bcrypt.check_password_hash(password_hash, plain_text)
