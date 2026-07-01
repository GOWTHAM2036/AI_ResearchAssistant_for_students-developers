"""
Flask Extension Instances
All extensions are instantiated here (without app) and initialized
inside the application factory via init_app(). This prevents circular imports.
"""

from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from flask_bcrypt import Bcrypt
from flask_jwt_extended import JWTManager

# ── SQLAlchemy ORM ─────────────────────────────────────────────────────────────
db = SQLAlchemy()

# ── Alembic-based migrations ───────────────────────────────────────────────────
migrate = Migrate()

# ── Password hashing ───────────────────────────────────────────────────────────
bcrypt = Bcrypt()

# ── JWT authentication ─────────────────────────────────────────────────────────
jwt = JWTManager()
