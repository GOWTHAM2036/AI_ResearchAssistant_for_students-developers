"""
Configuration Classes
Each class holds settings for a different environment.
Load via get_config(env_name). Secret keys are always read from env vars.
"""

import os
from datetime import timedelta
from dotenv import load_dotenv

# Load .env file when this module is imported (works in dev & CI)
load_dotenv()


class BaseConfig:
    """Shared settings across all environments."""

    # ── Security ───────────────────────────────────────────────────────────────
    SECRET_KEY: str = os.environ.get("SECRET_KEY", "change-me-in-production!")

    # ── JWT ────────────────────────────────────────────────────────────────────
    JWT_SECRET_KEY: str = os.environ.get("JWT_SECRET_KEY", "jwt-change-me-in-production!")
    JWT_ACCESS_TOKEN_EXPIRES: timedelta = timedelta(hours=1)
    JWT_ALGORITHM: str = "HS256"

    # ── Database ───────────────────────────────────────────────────────────────
    # Default to SQLite for local dev; override DATABASE_URL for PostgreSQL.
    # PostgreSQL example:  postgresql://user:pass@localhost:5432/auth_db
    _raw_db_url = os.environ.get("DATABASE_URL", "sqlite:///auth.db")
    if _raw_db_url and _raw_db_url.startswith("postgres://"):
        _raw_db_url = _raw_db_url.replace("postgres://", "postgresql://", 1)
    SQLALCHEMY_DATABASE_URI: str = _raw_db_url
    SQLALCHEMY_TRACK_MODIFICATIONS: bool = False

    # ── Google OAuth ───────────────────────────────────────────────────────────
    GOOGLE_CLIENT_ID: str = os.environ.get("GOOGLE_CLIENT_ID", "")

    # ── bcrypt ─────────────────────────────────────────────────────────────────
    BCRYPT_LOG_ROUNDS: int = 12  # cost factor — increase for stricter security


class DevelopmentConfig(BaseConfig):
    """Development-specific settings."""
    DEBUG: bool = True
    BCRYPT_LOG_ROUNDS: int = 4  # Faster hashing during development


class TestingConfig(BaseConfig):
    """Testing-specific settings."""
    TESTING: bool = True
    SQLALCHEMY_DATABASE_URI: str = "sqlite:///:memory:"  # in-memory DB per test run
    BCRYPT_LOG_ROUNDS: int = 4
    JWT_ACCESS_TOKEN_EXPIRES: timedelta = timedelta(seconds=10)  # short-lived for tests


class ProductionConfig(BaseConfig):
    """Production settings — relies entirely on environment variables."""

    DEBUG: bool = False

    # In production, DATABASE_URL MUST be set; never fall back to SQLite.
    SQLALCHEMY_DATABASE_URI: str = os.environ.get("DATABASE_URL", "")


# ── Config registry ────────────────────────────────────────────────────────────
_CONFIG_MAP: dict = {
    "development": DevelopmentConfig,
    "testing": TestingConfig,
    "production": ProductionConfig,
}


def get_config(env: str = "development"):
    """Return the config class for the given environment name."""
    config_class = _CONFIG_MAP.get(env)
    if config_class is None:
        raise ValueError(f"Unknown environment '{env}'. Choose from: {list(_CONFIG_MAP.keys())}")
    
    if env == "production" and not os.environ.get("DATABASE_URL"):
        raise KeyError("DATABASE_URL environment variable is required in production environment.")
        
    return config_class
