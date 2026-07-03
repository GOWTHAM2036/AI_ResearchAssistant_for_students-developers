"""
Flask Application Factory
Initializes Flask app, database, and registers all blueprints.
"""

from flask import Flask, render_template
from .extensions import db, migrate, bcrypt, jwt
from .config import get_config


def create_app(env: str = "development") -> Flask:
    """
    Application factory pattern — creates and configures the Flask app.

    Args:
        env: Environment name ('development', 'testing', 'production')

    Returns:
        Configured Flask application instance.
    """
    app = Flask(__name__)

    # ── Load config ───────────────────────────────────────────────────────────
    app.config.from_object(get_config(env))

    # ── Initialize extensions ─────────────────────────────────────────────────
    db.init_app(app)
    migrate.init_app(app, db)
    bcrypt.init_app(app)
    jwt.init_app(app)

    # ── Register blueprints ───────────────────────────────────────────────────
    from .routes.auth_routes import auth_bp
    from .routes.protected_routes import protected_bp
    from .routes.google_routes import google_bp
    from .routes.phone_routes import phone_bp

    app.register_blueprint(auth_bp, url_prefix="/api/auth")
    app.register_blueprint(protected_bp, url_prefix="/api")
    app.register_blueprint(google_bp, url_prefix="/api/auth/google")
    app.register_blueprint(phone_bp, url_prefix="/api/auth/phone")

    # ── Create DB tables if they don't exist (dev/test only) ──────────────────
    with app.app_context():
        db.create_all()

    # ── Serve the login / register page at root ───────────────────────────────
    @app.route("/")
    def index():
        return render_template("auth.html")

    return app
