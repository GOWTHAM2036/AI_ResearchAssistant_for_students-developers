"""
Application Entry Point
Run with:  python run.py
Or use:    flask --app run:app run
"""

import os
import logging
from app import create_app

# ── Logging setup ──────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)

# ── Create app from environment ────────────────────────────────────────────────
env = os.environ.get("FLASK_ENV", "development")
app = create_app(env=env)

if __name__ == "__main__":
    app.run(
        host="0.0.0.0",
        port=int(os.environ.get("PORT", 5000)),
        debug=(env == "development"),
    )
