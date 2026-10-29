# LogHealth — Log Analytics and System Health Intelligence

> **LogHealth is a log analytics and system health intelligence platform that transforms application logs into actionable insights about reliability, operational health, anomalies, and system behavior.**

[![Python](https://img.shields.io/badge/Python-3.9%20%7C%203.10%20%7C%203.11%20%7C%203.12-blue.svg)](https://www.python.org/)
[![Framework](https://img.shields.io/badge/Framework-Flask%203.1-black.svg)](https://palletsprojects.com/p/flask/)
[![Frontend](https://img.shields.io/badge/Frontend-Vanilla%20HTML%2FCSS%2FJS-orange.svg)](https://developer.mozilla.org/)
[![Visualizations](https://img.shields.io/badge/Charts-Chart.js%204.4-yellow.svg)](https://www.chartjs.org/)
[![Deployment](https://img.shields.io/badge/Deploy-Vercel%20Serverless-lightgrey.svg)](https://vercel.com/)
[![Tests](https://img.shields.io/badge/Tests-20%20Passing-brightgreen.svg)](tests/)

---

## 1. Overview & Core Mission

LogHealth evolves traditional log parsing into a comprehensive **System Health Intelligence** platform. Rather than acting as a code-level patch generator, LogHealth monitors the operational reliability, risk posture, and behavior of production services through their event logs.

### Key Capabilities
- **Explainable System Health Score (0–100)**: Transparent calculation incorporating weighted event severity, failure density, detected anomalies, and component failure concentrations. Displays an explicit *Insufficient Data* provisional state when 0 logs are present.
- **Component & Subsystem Health**: Classifies logs across components (`API & Backend`, `Database`, `Authentication`, `Network`, `Background Jobs`, `Infrastructure`, `File System`, `Memory`, `Application`), calculating failure rates, event volumes, and relative risk scores.
- **Statistical Anomaly Detection**: Identifies volume spikes using dynamic standard deviations ($z > 1.5$), critical error bursts, and dangerous concentrations in single components.
- **Prioritized Risk Assessment**: Ranks architectural and operational risks by severity, frequency, and impact evidence, pairing each with monitoring and mitigation guidance.
- **Historical Baseline Comparison**: Compares current log batches with persisted historical baselines, reporting volume change ($\Delta\%$), newly emerged error signatures, and resolved issues.
- **Executive Health Reports**: Generates structured 10-section health reports exportable as JSON or formatted Markdown (`GET /api/report`).
- **Professional Command-Center UI**: Modern responsive interface with 10 dedicated views, glassmorphic styling, and Chart.js visualizations.
- **Robust Ingestion**: Accepts structured JSON (Format A with `errors` object, Format B flat array), Syslog, Apache/Nginx web logs, and raw stack traces with SHA256 idempotency deduplication.

---

## 2. Quick Start & Execution

### Prerequisites
- Python 3.9+ (Python 3.11 or 3.12 recommended)
- `pip` package manager

### Local Installation & Launch

1. **Navigate to the project root directory**:
   ```bash
   cd Error_Insight--main
   ```

2. **(Optional) Create and activate a virtual environment**:
   ```bash
   # Windows PowerShell:
   python -m venv venv
   .\venv\Scripts\Activate.ps1

   # macOS / Linux:
   python3 -m venv venv
   source venv/bin/activate
   ```

3. **Install dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

4. **Start the LogHealth platform**:
   ```bash
   python app.py
   ```

5. **Open the Dashboard**:
   Navigate to **[http://127.0.0.1:5000](http://127.0.0.1:5000)** in your browser.

---

## 3. Explainable Health Scoring Formula

LogHealth does not generate arbitrary numbers or claim measured uptime without telemetry. The health score is evidence-based and calculated as:

$$\text{Raw Penalty} = \left(12 \times N_{\text{critical}} + 4 \times N_{\text{error}} + 1.5 \times N_{\text{warning}}\right) \times \text{DensityWeight}$$

$$\text{Total Penalty} = \text{Raw Penalty} + \text{AnomalyPenalty} + \text{ConcentrationPenalty}$$

$$\text{Health Score} = \max\left(0, \min\left(100, \text{round}(100 - \text{Total Penalty})\right)\right)$$

### Contributing Factors
1. **Severity Weights**: Critical (12 pts), Error (4 pts), Warning (1.5 pts), Info (0 pts).
2. **Density Weight**: Ratio of non-informational events to total events ($\frac{N_{\text{issues}}}{N_{\text{total}}}$).
3. **Anomaly Penalty**: Adds 5 to 10 penalty points for detected statistical volume spikes or critical error bursts.
4. **Concentration Penalty**: Adds 5 penalty points if over 65% of failures are concentrated in a single subsystem.

### Health Status Bands
| Health Score | Status | Description |
| :--- | :--- | :--- |
| **90 – 100** | **EXCELLENT** | System operating within healthy parameters; minimal warnings. |
| **75 – 89** | **GOOD** | Normal operational load; minor errors handled gracefully. |
| **50 – 74** | **FAIR** | Elevated warning/error rates; targeted investigation recommended. |
| **25 – 49** | **DEGRADED** | High failure density or recurring critical events; service stability at risk. |
| **0 – 24** | **CRITICAL** | Severe cascading failures or systemic failure concentration. Immediate action required. |
| **N/A** | **NO DATA** | Explicit provisional state when 0 events exist in the dataset. |

---

## 4. Architecture & Technology Stack

| Layer | Technology | Description |
| :--- | :--- | :--- |
| **Frontend** | HTML5, CSS3, Vanilla JS | Dark command-center theme, responsive layout, glassmorphic cards, zero heavyweight JS frameworks. |
| **Visualizations** | Chart.js 4.4 | Reactive timeline charts, severity doughnuts, and component distribution bars. |
| **Backend** | Python 3 + Flask 3.1 | Modular Application Factory with Service Layer architecture and Blueprint routing. |
| **Database** | SQLite3 (`sqlite3`) | Parameterized queries, WAL mode, composite indexes on `timestamp`, `category`, and `severity`. |
| **Persistence Layer**| `DatabaseManager` | Extensible repository pattern allowing transparent switching between SQLite and external databases. |
| **Deduplication** | SHA256 Idempotency Hash | Prevents duplicate event insertion during network retries or batch re-processing. |
| **Security** | API Key (`X-API-Key`) | Header-based authentication protecting automated ingestion endpoints. |

---

## 5. Directory Structure

```
LogHealth/
├── app.py                      # Flask Application Factory & WSGI Server Entry Point
├── config.py                   # Environment Configuration & DB Path Resolver
├── requirements.txt            # Python Dependencies
├── vercel.json                 # Vercel Serverless Deployment Configuration
├── sample_parser_client.py     # Standalone Python client simulating log collector
├── database/
│   ├── __init__.py
│   ├── db.py                   # DatabaseManager Abstraction Layer & SQLiteManager
│   └── schema.sql              # SQL Schema with indexes & idempotency constraints
├── services/
│   ├── __init__.py
│   ├── classifier_service.py   # Subsystem classification & severity normalizer
│   ├── parser_service.py       # JSON (Format A/B), Syslog, and raw log parser
│   ├── analytics_service.py    # Health scoring, anomaly detection, component risk, & reports
│   └── recommendation_service.py # Operational mitigations & monitoring suggestions
├── routes/
│   ├── __init__.py
│   ├── api_routes.py           # REST endpoints (/health, /logs, /analyze, /report, etc.)
│   └── web_routes.py           # Dashboard single-page template router
├── templates/
│   └── index.html              # Responsive command-center dashboard (10 views)
├── static/
│   ├── css/
│   │   └── dashboard.css       # Command-center styling, glassmorphism, responsive grid
│   └── js/
│       └── dashboard.js        # Reactive Chart.js charts, tab router, modal, & report viewer
├── sample_data/
│   ├── format_a_errors.json    # Format A structured JSON sample
│   ├── format_b_errors.json    # Format B array JSON sample
│   ├── sample_system.log       # Plain-text multi-line log sample
│   └── malformed_sample.txt    # Malformed file for validation testing
├── api_docs/
│   └── integration_guide.md    # Integration contract for external log collectors
└── tests/
    ├── __init__.py
    └── test_app.py             # 20 automated unit tests with isolated test SQLite DB
```

---

## 6. REST API Reference

| Method | Endpoint | Description | Auth Required |
| :--- | :--- | :--- | :--- |
| `GET` | `/api/health` | Health check, DB connectivity, stored record count | No |
| `POST` | `/api/logs` | External log collector ingestion endpoint | **Yes** (`X-API-Key`) |
| `POST` | `/api/analyze` | Upload JSON or `.log` file for analysis & saving | No |
| `GET` | `/api/history` | Stored records with pagination & search filtering | No |
| `GET` | `/api/analytics` | Aggregated metrics, health score, anomalies, component risks | No |
| `GET` | `/api/report` | Executive health report (`?format=markdown&download=1`) | No |
| `GET` | `/api/errors/{id}` | Detailed error inspection & operational recommendations | No |
| `GET` | `/api/docs` | OpenAPI-style JSON specification | No |
| `POST` | `/api/seed` | Seed realistic demo dataset (12 records) | No |
| `POST` | `/api/clear` | Clear all records from database | No |

### Submitting Logs (`POST /api/logs`)
```bash
curl -X POST http://127.0.0.1:5000/api/logs \
  -H "Content-Type: application/json" \
  -H "X-API-Key: dev-secret-key-12345" \
  -d '{
    "errors": [
      {
        "id": "LOG-101",
        "timestamp": "2026-10-29 08:30:00",
        "type": "Database",
        "message": "Connection pool exhausted on port 5432",
        "severity": "Critical"
      }
    ]
  }'
```

### Exporting Executive Report (`GET /api/report`)
```bash
# JSON Format:
curl http://127.0.0.1:5000/api/report

# Download Markdown Report:
curl -OJ "http://127.0.0.1:5000/api/report?format=markdown&download=1"
```

---

## 7. Cloud Deployment & Vercel Serverless Architecture

LogHealth is fully configured for deployment on [Vercel](https://vercel.com/) via the existing [vercel.json](file:///c:/Users/sweth/Downloads/Error_Insight_Database/Error_Insight_Database_Ready/Error_Insight--main/vercel.json) configuration:

### Ephemeral Storage Handling
- In Vercel Serverless environments, the filesystem is **read-only** with the exception of the `/tmp` directory.
- `config.py` automatically detects Vercel environments (`VERCEL=1`) and routes SQLite databases to `tempfile.gettempdir()` (`/tmp/loghealth.db`), ensuring error-free execution and zero crashes during serverless invocations.

### Durable Multi-Invocation Persistence
- Because serverless `/tmp` directories are ephemeral across cold starts and container recycles, durable long-term storage can be connected seamlessly.
- Thanks to the `DatabaseManager` abstraction, you can connect an external hosted database (such as PostgreSQL via Supabase, Neon, or Railway) by setting the environment variable in your Vercel Project Settings:
  ```env
  DATABASE_PATH=postgresql://user:pass@ep-hostname.neon.tech/loghealth?sslmode=require
  ```
- No changes to application code are required.

---

## 8. Automated Testing

LogHealth includes an automated test suite containing **20 unit tests**:
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
15. Explainable health score computation (bounds, formula, penalties)
16. Component health ranking and failure rate calculation
17. Statistical anomaly detection (volume spike and burst detection)
18. Prioritized risk assessment generation
19. Historical baseline comparison logic
20. Executive health report generation (`GET /api/report`)

### Run Tests:
```bash
python -m unittest discover -s tests -v
```

*Note: All tests execute against an isolated temporary SQLite database that is automatically destroyed upon test completion.*

---

## 9. Live Resources
- **GitHub Repository**: [https://github.com/swethav2023e-png/Error_insight_-](https://github.com/swethav2023e-png/Error_insight_-)
- **Vercel Live Deployment**: [https://error-insight-ruddy.vercel.app/](https://error-insight-ruddy.vercel.app/)
