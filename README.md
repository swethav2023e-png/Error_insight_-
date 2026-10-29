# ErrorInsight – Intelligent Error Analyzer

**ErrorInsight** is a cybersecurity and system-monitoring web application designed to analyze log files and structured error payloads produced by external Log Parsers. It classifies errors across 6 subsystems, computes real frequency and severity statistics, detects recurring anomalies, provides rule-based remediation suggestions, and exposes a reusable, documented REST API for cross-project integration.

---

## 1. Quick Start & Execution

### Prerequisites
- Python 3.9+ (Python 3.12+ recommended)
- `pip` package manager

### Installation & Launch

1. **Clone or extract** the repository and open the project directory in VS Code or your terminal:
   ```bash
   cd Error_Insight--main
   ```

2. **(Optional) Create and activate a virtual environment**:
   ```bash
   python -m venv venv
   # On Windows (PowerShell):
   .\venv\Scripts\Activate.ps1
   # On macOS/Linux:
   source venv/bin/activate
   ```

3. **Install dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

4. **Configure environment variables (Optional)**:
   A template is provided in `.env.example`. By default, ErrorInsight uses:
   - `DATABASE_PATH=error_insight.db` (auto-created on startup)
   - `API_KEY=dev-secret-key-12345`
   - `PORT=5000`

5. **Start the Flask server**:
   ```bash
   python app.py
   ```

6. **Open the Dashboard in your browser**:
   Navigate to: **[http://127.0.0.1:5000](http://127.0.0.1:5000)**

---

## 2. Key Architecture & Technology Stack

| Layer | Technology | Description |
| :--- | :--- | :--- |
| **Frontend** | HTML5, CSS3, Vanilla JS | Cyber command-center theme, responsive layout, glassmorphic panels. |
| **Visualizations** | Chart.js 4.4 | Bar chart for category breakdown, doughnut for severity impact, line/area for error trends over time. |
| **Backend** | Python 3 + Flask 3.1 | Modular architecture with Application Factory, Blueprints, and Services. |
| **Database** | SQLite3 (`sqlite3`) | Parameterized queries, WAL mode, indexes on `timestamp`, `category`, `severity`. |
| **Abstraction** | `DatabaseManager` | Extensible repository pattern allowing seamless migration to PostgreSQL without modifying application logic. |
| **Security** | API Key (`X-API-Key`) | Header-based authentication protecting data-ingestion endpoints. |

---

## 3. Project Directory Structure

```
ErrorInsight/
├── app.py                      # Flask Application Factory & Server Entry Point
├── config.py                   # App Configuration (Base & Testing)
├── requirements.txt            # Python Dependencies
├── .env.example                # Environment Variable Template
├── .gitignore                  # Git Ignore rules for DB, env, caches
├── README.md                   # Complete Documentation & Execution Guide
├── sample_parser_client.py     # Standalone Python client simulating friend's Log Parser
├── database/
│   ├── __init__.py
│   ├── db.py                   # DatabaseManager Abstraction Layer & SQLiteManager
│   └── schema.sql              # SQL Schema with indexes & idempotency constraints
├── services/
│   ├── __init__.py
│   ├── classifier_service.py   # Rule-based categorization & severity normalizer
│   ├── parser_service.py       # JSON (Format A/B) & plain-text log parsing engine
│   ├── analytics_service.py    # Frequency, severity, timeline, and Chart.js metrics
│   └── recommendation_service.py # Rule-based preliminary causes & solutions
├── routes/
│   ├── __init__.py
│   ├── api_routes.py           # REST endpoints (/health, /logs, /analyze, /history, etc.)
│   └── web_routes.py           # Dashboard single-page template router
├── templates/
│   └── index.html              # Cyber-themed responsive dashboard UI
├── static/
│   ├── css/
│   │   └── dashboard.css       # Command-center styling, glassmorphism, responsive
│   └── js/
│       └── dashboard.js        # Reactive Chart.js charts, filters, modal, and API console
├── sample_data/
│   ├── format_a_errors.json    # Format A structured JSON sample
│   ├── format_b_errors.json    # Format B array JSON sample
│   ├── sample_system.log       # Plain-text multi-line log sample
│   └── malformed_sample.txt    # Malformed file for validation testing
├── api_docs/
│   └── integration_guide.md    # Full integration contract for the friend's Log Parser
└── tests/
    ├── __init__.py
    └── test_app.py             # 14 automated unit tests using isolated test SQLite DB
```

---

## 4. Integration with the Friend's Log Parser

The Log Parser is a separate project that extracts errors from application logs and pushes structured records into ErrorInsight. Both systems interact over HTTP and store data into the same persistent database.

### 1. Ingestion Endpoint
- **URL**: `POST http://127.0.0.1:5000/api/logs`
- **Required Header**: `X-API-Key: dev-secret-key-12345`
- **Content-Type**: `application/json`

### 2. Supported JSON Formats

#### Format A (Recommended):
```json
{
  "errors": [
    {
      "id": "PARSER-LOG-101",
      "timestamp": "2026-10-29 08:30:00",
      "type": "Database",
      "message": "Database connection refused on port 5432",
      "severity": "Critical"
    }
  ]
}
```

#### Format B (Direct Array):
```json
[
  {
    "timestamp": "2026-10-29 08:35:10",
    "message": "Connection timeout connecting to upstream microservice",
    "severity": "Warning"
  }
]
```

### 3. Idempotency & Duplicate Prevention
ErrorInsight automatically calculates an idempotency hash for each event:
`SHA256(source_name + "|" + source_id + "|" + timestamp + "|" + message)`
- If the exact same record is submitted again, ErrorInsight safely ignores it and increments the `duplicates` counter.
- Repeated error messages occurring at different timestamps are **never discarded**.

### 4. Run the Simulated Log Parser Client
To test the integration end-to-end:
```bash
python sample_parser_client.py
```
This script checks backend health, sends a batch of 4 parsed records, tests duplicate detection, and reports HTTP response details.

---

## 5. Automated Testing

ErrorInsight includes an automated test suite verifying all 14 project requirements:
1. Application startup and database initialization
2. Health endpoint (`GET /api/health`)
3. Valid JSON upload (Format A and Format B)
4. Valid plain-text log upload
5. Invalid JSON and unsupported formats
6. Missing required fields validation
7. Error categorization and severity normalization
8. Database persistence across application restarts
9. History retrieval, search, and filtering
10. Analytics calculations and recurring error grouping
11. API-key authentication (`X-API-Key`)
12. Duplicate submission handling and idempotency
13. Simulated Log Parser client integration
14. Database failures and error response codes

### Run Tests:
```bash
python -m unittest discover tests
```
*Note: All tests run against a temporary isolated database (`test_*.db`) that is automatically cleaned up, ensuring real application data is never modified.*

---

## 6. REST API Endpoints Reference

| Method | Endpoint | Description | Auth Required |
| :--- | :--- | :--- | :--- |
| `GET` | `/api/health` | Health check, DB connectivity, stored record count | No |
| `POST` | `/api/logs` | External Log Parser ingestion endpoint | **Yes** (`X-API-Key`) |
| `POST` | `/api/analyze` | Upload JSON or `.log` file for analysis & saving | No |
| `GET` | `/api/history` | Stored records with pagination & search filtering | No |
| `GET` | `/api/analytics` | Aggregated metrics, frequency counts, Chart.js datasets | No |
| `GET` | `/api/errors/{id}` | Detailed error inspection & rule-based recommendations | No |
| `GET` | `/api/docs` | OpenAPI-style JSON specification | No |
| `POST` | `/api/seed` | Seed realistic demo dataset (12 records) | No |
| `POST` | `/api/clear` | Clear all records from database | No |

---

## 7. Troubleshooting & FAQ

- **Database is locked**: Ensure you do not have external SQLite browser locks open. ErrorInsight uses a 15-second busy timeout and WAL mode.
- **Unauthorized (401) error**: Check that your request header includes `X-API-Key: dev-secret-key-12345` (or the key specified in your `.env` file).
- **Connecting from another computer on the same network**:
  1. Find your computer's local IP address (`ipconfig` on Windows, `ifconfig` on Linux/macOS).
  2. Start Flask listening on all network interfaces:
     ```bash
     python app.py
     ```
     *(In `app.py`, change host to `0.0.0.0` or run `flask run --host=0.0.0.0 --port=5000`)*.
  3. On the other computer, point the Log Parser to `http://<YOUR_IP>:5000/api/logs`.
- **Production Deployment Note**: For production hosting, configure a PostgreSQL database URL and set environment variable `DATABASE_PATH` to your connection string via the extensible `DatabaseManager` interface.
