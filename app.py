from flask import Flask, render_template, request, jsonify
from pathlib import Path
from collections import Counter
import json
import sqlite3
from datetime import datetime

app = Flask(__name__)
ROOT = Path(__file__).resolve().parent
DB_PATH = ROOT / "error_insight.db"

SEVERITY = {"critical":"Critical","fatal":"Critical","error":"Error",
            "exception":"Error","warning":"Warning","warn":"Warning","info":"Info"}

GUIDE = {
    "Database": ("Database service unavailable, invalid credentials, or failed SQL connection.",
                 "Check the database service, connection string, credentials and connection pool."),
    "Authentication": ("Invalid credentials, expired session/token, or authorization configuration.",
                       "Verify credentials, token expiry, roles and authentication configuration."),
    "Network": ("Timeout, DNS issue, unreachable service, or unstable network connection.",
                "Check connectivity, DNS, service health, timeout values and retry settings."),
    "File System": ("Missing file/path or insufficient permissions.",
                    "Verify file existence, path, permissions and available disk space."),
    "Memory": ("High memory usage, memory leak, or insufficient RAM.",
               "Inspect memory usage, identify leaks and reduce unnecessary object retention."),
    "Application": ("Unexpected runtime, validation, or application logic failure.",
                    "Inspect the stack trace, validate inputs and review the affected module.")
}

def get_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    """Create the persistent database and error log table on first run."""
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

def save_rows(rows, source="upload"):
    """Persist analyzed error records to SQLite."""
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    records = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        msg = row.get("message") or row.get("error") or row.get("description") or "Unknown error"
        typ = row.get("type") or row.get("category") or detect_type(msg)
        records.append((
            str(row.get("id", "")), str(row.get("timestamp") or now),
            str(typ), str(msg), sev(row.get("severity", "Error")), now
        ))
    with get_connection() as conn:
        conn.executemany("""
            INSERT INTO error_logs (source_id, timestamp, type, message, severity, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
        """, records)
    return len(records)

def sev(value):
    return SEVERITY.get(str(value).lower().strip(), "Error")

def detect_type(message):
    s = str(message).lower()
    rules = {
        "Database":["database","mysql","postgres","sql","db ","query failed"],
        "Authentication":["login","authentication","unauthorized","token","password"],
        "Network":["timeout","network","dns","socket","unreachable","connection reset"],
        "File System":["file not found","no such file","directory","path","permission"],
        "Memory":["memory","heap","ram","out of memory"]
    }
    for name, words in rules.items():
        if any(w in s for w in words):
            return name
    return "Application"

def analyze(rows):
    out=[]
    for i,row in enumerate(rows,1):
        if not isinstance(row,dict): continue
        msg=row.get("message") or row.get("error") or row.get("description") or "Unknown error"
        typ=row.get("type") or row.get("category") or detect_type(msg)
        out.append({
            "id":row.get("id",i),
            "timestamp":row.get("timestamp",datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
            "type":typ,"message":str(msg),"severity":sev(row.get("severity","Error"))
        })
    tc=Counter(x["type"] for x in out)
    sc=Counter(x["severity"] for x in out)
    rank={"Critical":4,"Error":3,"Warning":2,"Info":1}
    recurring=[]
    for typ,count in tc.most_common():
        level=max((x["severity"] for x in out if x["type"]==typ),
                  key=lambda x:rank.get(x,0),default="Error")
        cause,solution=GUIDE.get(typ,GUIDE["Application"])
        recurring.append({"type":typ,"count":count,"severity":level,
                          "cause":cause,"solution":solution})
    return {"total":len(out),"unique_types":len(tc),"critical":sc["Critical"],
            "warning":sc["Warning"],"error":sc["Error"],"info":sc["Info"],
            "type_counts":dict(tc),"severity_counts":dict(sc),
            "recurring":recurring[:6],"recent":out[-10:][::-1]}

def demo_rows():
    # Support both the original root-level file and the data/ subfolder layout.
    candidates = [ROOT / "data" / "errors.json", ROOT / "errors.json"]
    for path in candidates:
        if path.exists():
            data=json.loads(path.read_text(encoding="utf-8"))
            return data["errors"] if isinstance(data,dict) else data
    return []

@app.route("/")
def index():
    return render_template("index.html")

@app.get("/api/demo")
def demo():
    return jsonify(analyze(demo_rows()))

@app.post("/api/analyze")
def api_analyze():
    if "file" not in request.files:
        return jsonify({"error":"Please select an errors.json file."}),400
    try:
        data=json.load(request.files["file"])
        rows=data.get("errors",data) if isinstance(data,dict) else data
        if not isinstance(rows,list):
            raise ValueError("JSON must contain an array of errors.")
        result=analyze(rows)
        saved=save_rows(rows, request.files["file"].filename or "upload")
        result["saved_to_database"]=saved
        return jsonify(result)
    except Exception as e:
        return jsonify({"error":str(e)}),400

@app.get("/api/history")
def api_history():
    """Return the most recently stored error records from the database."""
    try:
        limit = min(max(int(request.args.get("limit", 100)), 1), 1000)
    except ValueError:
        limit = 100
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT id, source_id, timestamp, type, message, severity, created_at "
            "FROM error_logs ORDER BY id DESC LIMIT ?", (limit,)
        ).fetchall()
    return jsonify({"total_returned": len(rows), "records": [dict(row) for row in rows]})

@app.get("/api/health")
def api_health():
    with get_connection() as conn:
        count = conn.execute("SELECT COUNT(*) FROM error_logs").fetchone()[0]
    return jsonify({"status":"ok", "database":"SQLite", "database_file":DB_PATH.name,
                    "stored_error_records":count})

init_db()

if __name__=="__main__":
    app.run(host="127.0.0.1",port=5000,debug=True)
