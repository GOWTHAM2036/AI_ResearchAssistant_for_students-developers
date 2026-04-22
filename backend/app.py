"""
Flask Application — serves the frontend and provides SSE streaming
for the multi-agent pipeline.
"""
import os
import sys

# Add project root to path so `backend.*` imports work
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from flask import Flask, Response, request, jsonify, send_from_directory
from flask_cors import CORS
from backend.orchestrator import Orchestrator
from backend.config import FLASK_HOST, FLASK_PORT, FLASK_DEBUG, GROQ_API_KEY
from backend.history_store import init_history_store, list_history_entries, get_history_entry

app = Flask(
    __name__,
    static_folder=os.path.join(os.path.dirname(os.path.dirname(__file__)), "frontend"),
)
CORS(app)
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


# ── Serve frontend ──────────────────────────────────────

@app.route("/")
def index():
    return send_from_directory(app.static_folder, "index.html")


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
