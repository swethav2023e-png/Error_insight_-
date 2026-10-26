from flask import Flask, render_template, request, jsonify
from pathlib import Path
from collections import Counter
from datetime import datetime
import json
import os
import sqlite3
import tempfile

app = Flask(__name__)
ROOT = Path(__file__).resolve().parent

# Local development uses a database in the project directory.
# Vercel uses /tmp, which is writable but ephemeral. For persistent history,
# replace SQLite with a hosted database service.
IS_VERCEL = bool(os.environ.get("VERCEL"))
DB_PATH = Path(tempfile.gettempdir()) / "error_insight.db" if IS_VERCEL else ROOT / "error_insight.db"

SEVERITY = {
    "critical": "Critical", "fatal": "Critical", "error": "Error",
    "exception": "Error", "warning": "Warning", "warn": "Warning", "info": "Info",
}
GUIDE = {
    "Database": (
        "Database service unavailable, invalid credentials, or failed SQL connection.",
        "Check the database service, connection string, credentials and connection pool.",
    ),
    "Authentication": (
        "Invalid credentials, expired session/token, or authorization configuration.",
        "Verify credentials, token expiry, roles and authentication configuration.",
    ),
    "Network": (
        "Timeout, DNS issue, unreachable service, or unstable network connection.",
        "Check connectivity, DNS, service health, timeout values and retry settings.",
    ),
    "File System": (
        "Missing file/path or insufficient permissions.",
        "Verify file existence, path, permissions and available disk space.",
    ),
    "Memory": (
        "High memory usage, memory leak, or insufficient RAM.",
        "Inspect memory usage, identify leaks and reduce unnecessary object retention.",
    ),
    "Application": (
        "Unexpected runtime, validation, or application logic failure.",
        "Inspect the stack trace, validate inputs and review the affected module.",
    ),
}

def get_connection():
    """Open a SQLite connection and ensure its parent directory exists."""
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH), timeout=10)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    """Create the SQLite database and required indexes."""
    with get_connection() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS error_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                source_id TEXT,
                timestamp TEXT NOT NULL,
                type TEXT NOT NULL,
                message TEXT NOT NULL,
                severity TEXT NOT NULL,
                created_at TEXT NOT NULL
            )
        """)
        conn.execute("CREATE INDEX IF NOT EXISTS idx_error_logs_timestamp ON error_logs(timestamp)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_error_logs_type ON error_logs(type)")

def sev(value):
    return SEVERITY.get(str(value).lower().strip(), "Error")

def detect_type(message):
    text = str(message).lower()
    rules = {
        "Database": ["database", "mysql", "postgres", "sql", "db ", "query failed"],
        "Authentication": ["login", "authentication", "unauthorized", "token", "password"],
        "Network": ["timeout", "network", "dns", "socket", "unreachable", "connection reset"],
        "File System": ["file not found", "no such file", "directory", "path", "permission"],
        "Memory": ["memory", "heap", "ram", "out of memory"],
    }
    for name, words in rules.items():
        if any(word in text for word in words):
            return name
    return "Application"

def normalize_rows(rows):
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    normalized = []
    for index, row in enumerate(rows, 1):
        if not isinstance(row, dict):
            continue
        message = row.get("message") or row.get("error") or row.get("description") or "Unknown error"
        error_type = row.get("type") or row.get("category") or detect_type(message)
        normalized.append({
            "id": row.get("id", index),
            "timestamp": str(row.get("timestamp") or now),
            "type": str(error_type),
            "message": str(message),
            "severity": sev(row.get("severity", "Error")),
        })
    return normalized

def analyze(rows):
    output = normalize_rows(rows)
    type_counts = Counter(item["type"] for item in output)
    severity_counts = Counter(item["severity"] for item in output)
    rank = {"Critical": 4, "Error": 3, "Warning": 2, "Info": 1}
    recurring = []
    for error_type, count in type_counts.most_common():
        level = max(
            (item["severity"] for item in output if item["type"] == error_type),
            key=lambda value: rank.get(value, 0),
            default="Error",
        )
        cause, solution = GUIDE.get(error_type, GUIDE["Application"])
        recurring.append({
            "type": error_type, "count": count, "severity": level,
            "cause": cause, "solution": solution,
        })
    return {
        "total": len(output),
        "unique_types": len(type_counts),
        "critical": severity_counts["Critical"],
        "warning": severity_counts["Warning"],
        "error": severity_counts["Error"],
        "info": severity_counts["Info"],
        "type_counts": dict(type_counts),
        "severity_counts": dict(severity_counts),
        "recurring": recurring[:6],
        "recent": output[-10:][::-1],
    }

def save_rows(rows, source="upload"):
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    records = []
    for item in normalize_rows(rows):
        records.append((
            str(item.get("id", "")), item["timestamp"], item["type"],
            item["message"], item["severity"], now,
        ))
    if not records:
        return 0
    with get_connection() as conn:
        conn.executemany("""
            INSERT INTO error_logs (source_id, timestamp, type, message, severity, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
        """, records)
    return len(records)

def demo_rows():
    for path in (ROOT / "data" / "errors.json", ROOT / "errors.json"):
        if path.is_file():
            with path.open("r", encoding="utf-8") as file:
                data = json.load(file)
            if isinstance(data, dict):
                rows = data.get("errors", [])
                return rows if isinstance(rows, list) else []
            return data if isinstance(data, list) else []
    return []

@app.route("/")
def index():
    return render_template("index.html")

@app.get("/api/demo")
def demo():
    try:
        return jsonify(analyze(demo_rows()))
    except (OSError, json.JSONDecodeError):
        app.logger.exception("Unable to load demo data")
        return jsonify({"error": "Unable to load demo data. Check errors.json."}), 500

@app.post("/api/analyze")
def api_analyze():
    if "file" not in request.files:
        return jsonify({"error": "Please select an errors.json file."}), 400
    uploaded = request.files["file"]
    try:
        data = json.load(uploaded)
        rows = data.get("errors", data) if isinstance(data, dict) else data
        if not isinstance(rows, list):
            return jsonify({"error": "JSON must contain an array of errors."}), 400
        result = analyze(rows)
        try:
            result["saved_to_database"] = save_rows(rows, uploaded.filename or "upload")
        except (sqlite3.Error, OSError):
            app.logger.exception("Unable to save records to SQLite")
            result["saved_to_database"] = 0
            result["database_warning"] = "Analysis succeeded, but records could not be saved."
        return jsonify(result)
    except (json.JSONDecodeError, UnicodeDecodeError, ValueError) as exc:
        return jsonify({"error": f"Invalid JSON file: {exc}"}), 400

@app.get("/api/history")
def api_history():
    try:
        limit = min(max(int(request.args.get("limit", 100)), 1), 1000)
    except (TypeError, ValueError):
        limit = 100
    try:
        with get_connection() as conn:
            rows = conn.execute("""
                SELECT id, source_id, timestamp, type, message, severity, created_at
                FROM error_logs ORDER BY id DESC LIMIT ?
            """, (limit,)).fetchall()
        return jsonify({"total_returned": len(rows), "records": [dict(row) for row in rows]})
    except (sqlite3.Error, OSError):
        app.logger.exception("Unable to read SQLite history")
        return jsonify({"error": "History is temporarily unavailable.", "records": [], "total_returned": 0}), 503

@app.get("/api/health")
def api_health():
    try:
        with get_connection() as conn:
            count = conn.execute("SELECT COUNT(*) FROM error_logs").fetchone()[0]
        return jsonify({
            "status": "ok", "database": "SQLite", "database_file": DB_PATH.name,
            "stored_error_records": count,
            "storage_note": "Vercel /tmp is temporary." if IS_VERCEL else "Local SQLite storage.",
        })
    except (sqlite3.Error, OSError):
        app.logger.exception("SQLite health check failed")
        return jsonify({"status": "error", "database": "SQLite unavailable"}), 503

# Initialize when imported by Vercel. Log initialization problems so they can be
# diagnosed; endpoints that need SQLite will return a clear error if unavailable.
try:
    init_db()
except (sqlite3.Error, OSError):
    app.logger.exception("SQLite initialization failed")

if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000, debug=True)
