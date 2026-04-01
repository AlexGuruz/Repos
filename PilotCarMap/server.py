"""
PilotCar Loads Map - Local HTTP server.
Serves web/ static files and API: GET /api/routes, GET /api/drivers, GET /api/config, PATCH /api/routes/:id
"""
import json
import os
import re
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs

ROOT = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(ROOT, "data")
WEB_DIR = os.path.join(ROOT, "web")
CONFIG_PATH = os.path.join(ROOT, "config.json")
ROUTES_PATH = os.path.join(DATA_DIR, "routes.json")
DRIVERS_PATH = os.path.join(DATA_DIR, "drivers.json")
PORT = 8080


def load_json(path, default):
    if os.path.isfile(path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError):
            pass
    return default


def save_json(path, data):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)


def load_config():
    raw = load_json(CONFIG_PATH, {})
    # Resolve API key from file path if set
    key_path = raw.get("google_api_key_path")
    if key_path and os.path.isfile(key_path):
        try:
            with open(key_path, "r", encoding="utf-8") as f:
                raw = dict(raw)
                raw["google_api_key"] = f.read().strip()
        except IOError:
            pass
    return raw


class Handler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        print(f"[{self.log_date_time_string()}] {format % args}")

    def send_json(self, data, status=200):
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(json.dumps(data).encode("utf-8"))

    def send_cors_headers(self):
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, PATCH, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")

    def do_OPTIONS(self):
        self.send_response(204)
        self.send_cors_headers()
        self.end_headers()

    def do_GET(self):
        path = urlparse(self.path).path.rstrip("/") or "/"
        if path == "/api/routes":
            routes = load_json(ROUTES_PATH, [])
            self.send_json(routes)
            return
        if path == "/api/drivers":
            drivers = load_json(DRIVERS_PATH, [])
            self.send_json(drivers)
            return
        if path == "/api/config":
            config = load_config()
            self.send_json({"mapsApiKey": config.get("google_api_key", "")})
            return
        # Static file from web/
        if path == "/":
            path = "/index.html"
        file_path = os.path.join(WEB_DIR, path.lstrip("/"))
        if not os.path.normpath(file_path).startswith(os.path.normpath(WEB_DIR)):
            self.send_error(403)
            return
        if not os.path.isfile(file_path):
            self.send_error(404)
            return
        ext = os.path.splitext(file_path)[1].lower()
        types = {
            ".html": "text/html",
            ".css": "text/css",
            ".js": "application/javascript",
            ".json": "application/json",
            ".ico": "image/x-icon",
        }
        self.send_response(200)
        self.send_header("Content-Type", types.get(ext, "application/octet-stream"))
        self.end_headers()
        with open(file_path, "rb") as f:
            self.wfile.write(f.read())

    def do_PATCH(self):
        path = urlparse(self.path).path
        match = re.match(r"^/api/routes/(.+)$", path)
        if not match:
            self.send_error(404)
            return
        route_id = match.group(1)
        content_length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(content_length).decode("utf-8") if content_length else "{}"
        try:
            payload = json.loads(body)
        except json.JSONDecodeError:
            self.send_json({"error": "Invalid JSON"}, 400)
            return
        routes = load_json(ROUTES_PATH, [])
        updated = None
        for r in routes:
            if str(r.get("id")) == str(route_id):
                if "status" in payload:
                    r["status"] = payload["status"]
                if "assigned_driver" in payload:
                    r["assigned_driver"] = payload["assigned_driver"]
                updated = r
                break
        if updated is None:
            self.send_json({"error": "Route not found"}, 404)
            return
        save_json(ROUTES_PATH, routes)
        self.send_json(updated)


def main():
    os.makedirs(WEB_DIR, exist_ok=True)
    os.makedirs(DATA_DIR, exist_ok=True)
    server = HTTPServer(("127.0.0.1", PORT), Handler)
    print(f"PilotCar Map server at http://127.0.0.1:{PORT}")
    server.serve_forever()


if __name__ == "__main__":
    main()
