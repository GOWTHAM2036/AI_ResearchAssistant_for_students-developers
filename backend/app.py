"""
Flask Application — serves the frontend and provides SSE streaming
for the multi-agent pipeline, with integrated JWT authentication.
"""
import os
import sys
from datetime import timedelta

# Add project root to path so `backend.*` and `auth_service.*` imports work
_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _PROJECT_ROOT)

from flask import Flask, Response, request, jsonify, send_from_directory, render_template, redirect, url_for
from flask_cors import CORS
from backend.orchestrator import Orchestrator
from backend.config import FLASK_HOST, FLASK_PORT, FLASK_DEBUG, GROQ_API_KEY
from backend.history_store import init_history_store, list_history_entries, get_history_entry

# ── Auth system imports ──────────────────────────────────
from auth_service.app.extensions import db, bcrypt, jwt
from auth_service.app.routes.auth_routes import auth_bp
from auth_service.app.routes.protected_routes import protected_bp
from auth_service.app.routes.google_routes import google_bp
from auth_service.app.routes.phone_routes import phone_bp

app = Flask(
    __name__,
    static_folder=os.path.join(_PROJECT_ROOT, "frontend"),
    template_folder=os.path.join(_PROJECT_ROOT, "auth_service", "app", "templates"),
)
CORS(app)

# ── Auth config ──────────────────────────────────────────
from dotenv import load_dotenv
load_dotenv(os.path.join(_PROJECT_ROOT, ".env"))

app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "dev-secret-key-change-me")
app.config["JWT_SECRET_KEY"] = os.environ.get("JWT_SECRET_KEY", "dev-jwt-secret-change-me-in-prod-min-32bytes!")
app.config["JWT_ACCESS_TOKEN_EXPIRES"] = timedelta(hours=1)
app.config["SQLALCHEMY_DATABASE_URI"] = os.environ.get("DATABASE_URL", f"sqlite:///{os.path.join(_PROJECT_ROOT, 'auth.db')}")
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
app.config["BCRYPT_LOG_ROUNDS"] = 4  # fast for dev, increase for prod
app.config["GOOGLE_CLIENT_ID"] = os.environ.get("GOOGLE_CLIENT_ID", "")

# ── Initialize auth extensions ───────────────────────────
db.init_app(app)
bcrypt.init_app(app)
jwt.init_app(app)

# ── Register auth blueprints ─────────────────────────────
app.register_blueprint(auth_bp, url_prefix="/api/auth")
app.register_blueprint(protected_bp, url_prefix="/api")
app.register_blueprint(google_bp, url_prefix="/api/auth/google")
app.register_blueprint(phone_bp, url_prefix="/api/auth/phone")

# ── Create DB tables ─────────────────────────────────────
with app.app_context():
    from auth_service.app.models.user import User  # noqa: F401 — needed so SQLAlchemy knows the model
    db.create_all()

init_history_store()


# ── Health check ─────────────────────────────────────────

@app.route("/api/health")
def health():
    return jsonify({
        "status": "ok",
        "groq_configured": bool(GROQ_API_KEY and GROQ_API_KEY != "your_groq_api_key_here"),
        "agents": ["Manager", "Researcher", "Analyst", "Writer", "Delivery"],
    })


@app.route("/api/history", methods=["GET"])
def history_list():
    limit_raw = request.args.get("limit", "20").strip()
    try:
        limit = int(limit_raw)
    except ValueError:
        limit = 20
    items = list_history_entries(limit=limit)
    return jsonify({"items": items})


@app.route("/api/history/<int:entry_id>", methods=["GET"])
def history_detail(entry_id: int):
    entry = get_history_entry(entry_id)
    if not entry:
        return jsonify({"error": "History entry not found"}), 404
    return jsonify(entry)


# ── Run pipeline (SSE stream) ───────────────────────────

@app.route("/api/run", methods=["POST"])
def run_pipeline():
    data = request.get_json(force=True)
    topic = data.get("topic", "").strip()
    email = data.get("email", "").strip()

    if not topic:
        return jsonify({"error": "Topic is required"}), 400

    if len(topic) > 150:
        return jsonify({'error': 'Topic too long. Keep it under 150 characters.'}), 400
    if any(kw in topic.lower() for kw in ['you are an expert', 'rewrite', 'flask', 'app.py', 'ignore previous']):
        return jsonify({'error': 'Invalid topic detected.'}), 400

    if not GROQ_API_KEY or GROQ_API_KEY == "your_groq_api_key_here":
        return jsonify({"error": "GROQ_API_KEY not configured. Add it to your .env file."}), 500

    orch = Orchestrator()

    def generate():
        try:
            yield from orch.run(topic=topic, email=email)
        except Exception as e:
            import json, time
            yield f"data: {json.dumps({'type': 'error', 'agent': 'System', 'message': str(e)})}\n\n"
            yield f"data: {json.dumps({'type': 'pipeline', 'status': 'error', 'message': str(e)})}\n\n"

    return Response(
        generate(),
        mimetype="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive",
        },
    )


# ── Entry/login routes ──────────────────────────────────

@app.route("/")
def root():
    """Canonical entry route — redirect to /login."""
    return redirect(url_for("login_page"))


@app.route("/login")
def login_page():
    """Serve the login/register page."""
    return render_template("auth.html")


# ── Serve main app at /dashboard (after login) ──────────

@app.route("/dashboard")
def dashboard():
    """Serve the main AI Research Assistant frontend.
    Auth check is done client-side — if no token in localStorage,
    the frontend JS redirects to /login."""
    return send_from_directory(app.static_folder, "index.html")


# ── Logout route ────────────────────────────────────────

@app.route("/logout")
def logout():
    """Redirect to login page. Token is cleared client-side."""
    return redirect(url_for('login_page'))


@app.route("/<path:path>")
def static_files(path):
    return send_from_directory(app.static_folder, path)


# ── Run ─────────────────────────────────────────────────

if __name__ == "__main__":
    print("\n" + "=" * 60)
    print("  AI Research Crew - Multi-Agent System")
    print("=" * 60)
    print(f"  Server:  http://localhost:{FLASK_PORT}")
    groq_ok = GROQ_API_KEY and GROQ_API_KEY != "your_groq_api_key_here"
    print(f"  Groq:    {'[OK] Configured' if groq_ok else '[!!] NOT SET - add GROQ_API_KEY to .env'}")
    print("=" * 60 + "\n")
    app.run(host=FLASK_HOST, port=FLASK_PORT, debug=FLASK_DEBUG, threaded=True)
