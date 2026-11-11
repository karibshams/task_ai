import json
import os
import sys
from flask import Flask, render_template, request, jsonify

# Ensure root directory is in sys.path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import config
from agent.assistant import get_assistant
from agent.session import get_current_session
from rag.vector_store import get_vector_store

app = Flask(__name__, static_folder="static", template_folder="templates")
app.secret_key = config.SECRET_KEY

# Ensure vector store is initialized at startup
print("[Startup] Initializing Policy Vector Store...")
get_vector_store()

# Ensure user session is initialized
print("[Startup] Initializing Authenticated User Session...")
session = get_current_session()

# In-memory conversation store for web chat sessions
chat_histories = {}

@app.route("/")
def index():
    """Renders the main Chat Interface."""
    return render_template("index.html")

@app.route("/api/session", methods=["GET"])
def get_session_info():
    """Returns current authenticated session status and RBAC permissions."""
    return jsonify({
        "success": True,
        "session": session.get_summary()
    })

@app.route("/api/session/permissions", methods=["POST"])
def toggle_permissions():
    """Allows toggling permissions (e.g. for testing Scenario 04 vs 05)."""
    data = request.get_json() or {}
    permission = data.get("permission")
    enabled = data.get("enabled")

    if permission:
        if enabled:
            session.grant_permission(permission)
        else:
            session.revoke_permission(permission)
    elif "permissions" in data:
        session.set_permissions(data["permissions"])

    return jsonify({
        "success": True,
        "message": f"Updated permission '{permission}' to {enabled}",
        "session": session.get_summary()
    })

@app.route("/api/session/reset", methods=["POST"])
def reset_session():
    """Resets session to default authenticated state."""
    session.reset_default()
    return jsonify({
        "success": True,
        "message": "Session reset to default permissions.",
        "session": session.get_summary()
    })

@app.route("/api/chat", methods=["POST"])
def chat_endpoint():
    """
    Main Chat API Endpoint.
    Accepts: { "message": "...", "session_id": "optional" }
    Returns: { "reply": "...", "tool_calls": [...], "profile": {...}, "security_alert": bool, "session_user": {...} }
    """
    data = request.get_json() or {}
    user_message = data.get("message", "").strip()
    session_id = data.get("session_id", "default_session")

    if not user_message:
        return jsonify({
            "success": False,
            "error": "Empty message"
        }), 400

    # Retrieve history
    history = chat_histories.get(session_id, [])

    # Process message with Agent
    assistant = get_assistant()
    result = assistant.chat(user_message, history=history)

    # Update in-memory history
    history.append({"role": "user", "parts": [{"text": user_message}]})
    history.append({"role": "model", "parts": [{"text": result["reply"]}]})
    chat_histories[session_id] = history[-10:]  # Keep last 10 turns

    return jsonify({
        "success": True,
        "reply": result["reply"],
        "tool_calls": result.get("tool_calls", []),
        "profile": result.get("profile"),
        "security_alert": result.get("security_alert", False),
        "session_user": session.get_summary()
    })

@app.route("/api/chat/clear", methods=["POST"])
def clear_chat():
    """Clears conversation history for the session."""
    data = request.get_json() or {}
    session_id = data.get("session_id", "default_session")
    chat_histories[session_id] = []
    return jsonify({"success": True, "message": "Chat history cleared."})

@app.route("/api/policy/search", methods=["GET"])
def search_policy():
    """Direct search endpoint for the policy knowledge base."""
    query = request.args.get("q", "").strip()
    if not query:
        return jsonify({"success": False, "error": "Query parameter 'q' required"}), 400

    store = get_vector_store()
    results = store.search(query, top_k=5)
    return jsonify({
        "success": True,
        "query": query,
        "results": results
    })

@app.route("/api/test/run", methods=["POST"])
def run_automated_tests():
    """Runs all 7 scenarios programmatically and returns the test results."""
    import subprocess
    result = subprocess.run(
        [sys.executable, "-m", "unittest", "tests/test_scenarios.py"],
        capture_output=True,
        text=True
    )
    return jsonify({
        "success": result.returncode == 0,
        "returncode": result.returncode,
        "stdout": result.stdout,
        "stderr": result.stderr
    })

if __name__ == "__main__":
    print(f"==================================================")
    print(f" AI Business Assistant Server Starting")
    print(f" URL: http://localhost:{config.PORT}")
    print(f" LLM Model: {config.MODEL_NAME}")
    print(f" API Base: {config.API_BASE_URL}")
    print(f" Authenticated User: {session.email}")
    print(f"==================================================")
    app.run(host=config.HOST, port=config.PORT, debug=False)

