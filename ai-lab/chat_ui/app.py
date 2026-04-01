"""
Chat UI: send message to orchestrator, show reply and approval prompts.
Desktop-only v1; run with: python -m chat_ui.app
"""
from __future__ import annotations

import sys
from pathlib import Path

# ai-lab root
_root = Path(__file__).resolve().parents[1]
if str(_root) not in sys.path:
    sys.path.insert(0, str(_root))

from brain.orchestrator.main import run as orchestrator_run
from brain.approval_queue.queue import list_pending, resolve
from agents.feedback_interpreter.interpreter import apply_feedback


def main() -> None:
    try:
        from flask import Flask, request, jsonify, render_template_string
    except ImportError:
        print("Install Flask: pip install flask")
        sys.exit(1)
    app = Flask(__name__)

    HTML = """
    <!DOCTYPE html>
    <html>
    <head><meta charset="utf-8"><title>AI Lab Chat</title></head>
    <body>
    <h1>AI Lab</h1>
    <div id="messages"></div>
    <form id="form">
      <input type="text" id="input" placeholder="Message..." style="width:60%" />
      <button type="submit">Send</button>
    </form>
    <script>
      const messages = document.getElementById('messages');
      const form = document.getElementById('form');
      const input = document.getElementById('input');
      function add(msg, who) {
        const d = document.createElement('div');
        d.innerHTML = '<strong>' + who + ':</strong> ' + msg.replace(/\\n/g, '<br>');
        messages.appendChild(d);
      }
      form.onsubmit = async (e) => {
        e.preventDefault();
        const text = input.value.trim();
        if (!text) return;
        add(text, 'You');
        input.value = '';
        const r = await fetch('/chat', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ message: text }) });
        const j = await r.json();
        add(j.reply || j.error || 'No reply', 'Lab');
      };
    </script>
    </body>
    </html>
    """

    @app.route("/")
    def index():
        return render_template_string(HTML)

    @app.route("/chat", methods=["POST"])
    def chat():
        data = request.get_json() or {}
        message = data.get("message", "").strip()
        if not message:
            return jsonify({"reply": "Empty message."}), 400
        # Approve/deny
        lower = message.lower()
        if lower.startswith("approve ") or lower.startswith("deny "):
            parts = message.split(None, 1)
            action = parts[0].lower()
            id_ = parts[1].strip() if len(parts) > 1 else None
            if id_:
                ok = resolve(id_, action == "approve")
                if ok:
                    apply_feedback(message, {"approval_id": id_})
                    return jsonify({"reply": f"Recorded {action} for {id_}."})
            return jsonify({"reply": "Usage: approve <id> or deny <id>. Pending: " + str([p[0] for p in list_pending()])})
        out = orchestrator_run(message)
        return jsonify({"reply": out["reply"], "approval_request": out.get("approval_request")})

    @app.route("/pending")
    def pending():
        return jsonify([{"id": id_, "spec": spec} for id_, spec in list_pending()])

    print("AI Lab Chat at http://127.0.0.1:5000")
    app.run(host="127.0.0.1", port=5000, debug=False)


if __name__ == "__main__":
    main()
