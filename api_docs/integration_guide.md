# LogHealth Integration Contract for External Log Collectors & Parsers

This document specifies the technical contract and integration protocol for connecting external log collectors, parsers, and monitoring agents to the **LogHealth – Log Analytics and System Health Intelligence** platform.

---

## 1. Architecture Overview

```
┌─────────────────────────────────┐                 ┌──────────────────────────────────────┐
│ External Log Collector / Parser │                 │ LogHealth Backend (Flask Serverless) │
│ (Any Language, Host, or Agent)  │                 │ - Classification & Validation Engine │
└────────────────┬────────────────┘                 │ - Deduplication & Health Scoring     │
                 │                                  │ - Anomaly & Component Risk Engine    │
                 │  POST /api/logs (JSON)           └───────────────────┬──────────────────┘
                 │  Header: X-API-Key: <key>                            │
                 ▼                                                      ▼ Parameterized Queries
┌──────────────────────────────────────────────────────────────────────────────────────────┐
│                           Database (SQLite / PostgreSQL)                                 │
│                                (table: `error_logs`)                                     │
└──────────────────────────────────────────────────────────────────────────────────────────┘
```

External collectors interface with the LogHealth REST API over HTTP, pushing structured records that are analyzed in real time.

---

## 2. Base URL Configuration

- **Local Development:**
  `http://127.0.0.1:5000`
- **Local Network (LAN / Multi-machine):**
  `http://<SERVER_IP_ADDRESS>:5000` (e.g. `http://192.168.1.105:5000`)
- **Vercel / Cloud Production Deployment:**
  `https://error-insight-ruddy.vercel.app` (or custom configured domain)

---

## 3. Authentication

All requests to `POST /api/logs` must include the shared API Key.

| Header Name | Format | Required | Example |
| :--- | :--- | :--- | :--- |
| `X-API-Key` | Plain String | **Yes** | `dev-secret-key-12345` |
| `Content-Type` | MIME type | **Yes** | `application/json` |
| `X-Source-Project` | String identifier | *Optional* | `Production_Log_Collector_v2` |

Alternatively, you may pass the token via standard Bearer authorization:
`Authorization: Bearer <API_KEY>`

---

## 4. Ingestion Endpoint Specification

### `POST /api/logs`

Submits parsed log records in bulk or individually.

#### Supported Request Payload Formats

##### Format A (Object with `errors` array - Recommended):
```json
{
  "errors": [
    {
      "id": "PARSER-LOG-001",
      "timestamp": "2026-10-29 08:30:00",
      "type": "Database",
      "message": "Database connection pool exhausted: timeout waiting for connection",
      "severity": "Critical"
    },
    {
      "id": "PARSER-LOG-002",
      "timestamp": "2026-10-29 08:35:12",
      "type": "Network",
      "message": "DNS resolution timeout for api.payments.com",
      "severity": "Warning"
    }
  ]
}
```

##### Format B (Raw Array of Objects):
```json
[
  {
    "timestamp": "2026-10-29 08:40:00",
    "message": "Authentication token expired for user 42",
    "severity": "Warning"
  }
]
```

#### Field Specifications

| Field | Type | Required | Description | Allowed Values |
| :--- | :--- | :--- | :--- | :--- |
| `message` | string | **Yes** | The raw or normalized log message. | Non-empty text. |
| `timestamp` | string | *Optional* | Occurrence timestamp. (Defaults to server receive time). | `YYYY-MM-DD HH:MM:SS` or ISO-8601. |
| `severity` | string | *Optional* | Impact level. (Defaults to `Error`). | `Critical`, `Error`, `Warning`, `Info` *(Aliases like FATAL, WARN, EXCEPTION auto-normalized)* |
| `type` / `category` | string | *Optional* | System component. If omitted, LogHealth auto-classifies. | `Database`, `Authentication`, `Network`, `API & Backend`, `Background Jobs`, `Infrastructure`, `File System`, `Memory`, `Application` |
| `id` / `source_id` | string/int | *Optional* | External identifier from source collector. | Any unique string or integer. |

---

## 5. Duplicate Prevention & Idempotency

To prevent duplicate database records during network retries or re-scanned log files:
1. LogHealth computes an **Idempotency Hash** from:
   `hash = SHA256(source_name + "|" + source_id + "|" + timestamp + "|" + message)`
2. If the identical log event is transmitted again, LogHealth safely ignores the duplicate and increments the `duplicates` counter in the response.
3. Legitimate repeated errors (e.g., multiple connection timeouts at different seconds) have different timestamps and are **always preserved**.

---

## 6. Sample Response

### Success (HTTP 201 Created or 200 OK)
```json
{
  "status": "success",
  "message": "Processed 2 records: 2 accepted, 0 duplicate(s), 0 rejected.",
  "accepted": 2,
  "duplicates": 0,
  "rejected": 0,
  "errors": [],
  "total_submitted": 2
}
```

### Partial or Duplicate Submission (HTTP 200 OK)
```json
{
  "status": "success",
  "message": "Processed 2 records: 0 accepted, 2 duplicate(s), 0 rejected.",
  "accepted": 0,
  "duplicates": 2,
  "rejected": 0,
  "errors": [],
  "total_submitted": 2
}
```

### Unauthorized (HTTP 401 Unauthorized)
```json
{
  "status": "error",
  "error": "Unauthorized. A valid 'X-API-Key' header is required.",
  "hint": "Set X-API-Key in your HTTP request headers."
}
```

---

## 7. Report Export Endpoint

### `GET /api/report`

Generates an executive system health report containing overall score, component breakdown, detected anomalies, and prioritized risks.

- **Query Parameters**:
  - `format`: `json` (default) or `markdown`
  - `download`: `1` (triggers file download attachment `loghealth_executive_report.md`)

#### Example JSON Response:
```json
{
  "status": "success",
  "report": {
    "title": "LogHealth Executive System Health Report",
    "generated_at": "2026-10-29 13:00:00",
    "sections": {
      "executive_summary": "System Health Status: FAIR (Health Score: 78/100)...",
      "health_assessment": { ... },
      "component_health": [ ... ],
      "anomalies": [ ... ],
      "prioritized_risks": [ ... ]
    }
  }
}
```

---

## 8. Python Client Example

A complete, runnable Python client (`sample_parser_client.py`) is provided in the repository root. Run:
```bash
python sample_parser_client.py
```
This tests server connectivity, transmits sample log events, and validates idempotency protection.
