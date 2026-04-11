"""
Lightweight local server for JobAgent Navigator.
Replaces `python -m http.server` — serves static files AND handles
PATCH /api/jobs/<job_key> to write status/date changes back to job_database.json.

Usage: python server.py
Then open: http://localhost:5000
"""
import os
import json
import http.server
import urllib.parse
from datetime import datetime

PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
DB_FILE = os.path.join(PROJECT_ROOT, "data", "job_database.json")
PORT = 5000


class JobAgentHandler(http.server.SimpleHTTPRequestHandler):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=PROJECT_ROOT, **kwargs)

    def do_PATCH(self):
        """Handle PATCH /api/jobs/<job_key> to update a job record."""
        if not self.path.startswith("/api/jobs/"):
            self.send_error(404)
            return

        job_key = urllib.parse.unquote(self.path[len("/api/jobs/"):])

        content_length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(content_length)
        updates = json.loads(body)

        with open(DB_FILE, "r", encoding="utf-8") as f:
            db = json.load(f)

        if job_key not in db:
            self.send_response(404)
            self.end_headers()
            self.wfile.write(json.dumps({"error": "Job not found"}).encode())
            return

        # Apply allowed updates
        allowed_fields = {"status", "date_applied", "date_rejected",
                          "rejection_reason", "notes", "score", "fit_summary"}
        for field, value in updates.items():
            if field in allowed_fields:
                db[job_key][field] = value

        # Auto-stamp dates when status transitions
        if "status" in updates:
            if updates["status"] == "Applied" and not db[job_key].get("date_applied"):
                db[job_key]["date_applied"] = datetime.now().strftime("%Y-%m-%d")
            if updates["status"] == "Rejected" and not db[job_key].get("date_rejected"):
                db[job_key]["date_rejected"] = datetime.now().strftime("%Y-%m-%d")

        with open(DB_FILE, "w", encoding="utf-8") as f:
            json.dump(db, f, indent=4, ensure_ascii=False)

        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(json.dumps({"ok": True, "job": db[job_key]}).encode())

    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, PATCH, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    def log_message(self, format, *args):
        # Suppress noisy favicon/font requests
        first = str(args[0]) if args else ""
        if any(x in first for x in ["favicon", "fonts.g"]):
            return
        super().log_message(format, *args)


if __name__ == "__main__":
    import webbrowser
    print(f"\n{'='*45}")
    print(f"  JobAgent Navigator running on port {PORT}")
    print(f"  http://localhost:{PORT}/Job_Navigator.html")
    print(f"{'='*45}\n")
    webbrowser.open(f"http://localhost:{PORT}/Job_Navigator.html")
    with http.server.HTTPServer(("", PORT), JobAgentHandler) as httpd:
        httpd.serve_forever()
