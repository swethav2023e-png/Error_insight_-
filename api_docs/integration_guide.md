# ErrorInsight Integration Contract for External Log Parsers

This document specifies the technical contract and integration protocol for connecting external Log Parsers to the **ErrorInsight – Intelligent Error Analyzer** backend.

---

## 1. Architecture Overview

```
┌────────────────────────┐                   ┌───────────────────────────────┐
│ External Log Parser    │                   │ ErrorInsight Backend (Flask)  │
│ (Any Language / Host)  │                   │ - Categorization & Validation │
└───────────┬────────────┘                   │ - Persistence & Deduplication │
            │                                └──────────────┬────────────────┘
            │  POST /api/logs (JSON)                        │
            │  Header: X-API-Key: <key>                     │  Parameterized SQL
            ▼                                               ▼
┌────────────────────────────────────────────────────────────────────────────┐
│                    Shared SQLite / PostgreSQL Database                     │
│                        (table: `error_logs`)                               │
└────────────────────────────────────────────────────────────────────────────┘
```

Both projects interface with the same persistent backend service and write into the same central database.

---

## 2. Base URL Configuration

- **Local Development (Same Computer):**
  `http://127.0.0.1:5000`
- **Local Network (Different Computers on same Wi-Fi/LAN):**
  `http://<SERVER_IP_ADDRESS>:5000` (e.g. `http://192.168.1.105:5000`)
  *Note: Start Flask with `python app.py` listening on `0.0.0.0` or allow firewall incoming traffic on port 5000.*
- **Production / Deployed URL:**
  `https://your-errorinsight-domain.com`

---

## 3. Authentication

All requests to `POST /api/logs` must include the shared API Key.

| Header Name | Format | Required | Example |
| :--- | :--- | :--- | :--- |
| `X-API-Key` | Plain String | **Yes** | `dev-secret-key-12345` |
| `Content-Type` | MIME type | **Yes** | `application/json` |
| `X-Source-Project` | String identifier | *Optional* | `Production_Log_Parser_v2` |

Alternatively, you may pass the token via standard Bearer authorization:
`Authorization: Bearer <API_KEY>`

---

## 4. Ingestion Endpoint Specification

### `POST /api/logs`

Submits parsed error records in bulk or individually.

#### Supported Request Payload Formats

##### Format A (Object with `errors` array - Recommended):
```json
{
  "errors": [
    {
      "id": "PARSER-LOG-001",
      "timestamp": "2026-10-29 08:30:00",
      "type": "Database",
      "message": "Database connection refused on port 5432",
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
| `message` | string | **Yes** | The raw or normalized error description. | Non-empty text. |
| `timestamp` | string | *Optional* | Occurrence timestamp. (Defaults to server receive time). | `YYYY-MM-DD HH:MM:SS` or ISO-8601. |
| `severity` | string | *Optional* | Impact level. (Defaults to `Error`). | `Critical`, `Error`, `Warning`, `Info` *(Aliases like FATAL, WARN, EXCEPTION auto-normalized)* |
| `type` / `category` | string | *Optional* | System category. If omitted or invalid, ErrorInsight auto-classifies. | `Database`, `Authentication`, `Network`, `File System`, `Memory`, `Application` |
| `id` / `source_id` | string/int | *Optional* | External identifier from the source parser. | Any unique string or integer. |

---

## 5. Duplicate Prevention & Idempotency

To prevent duplicate database records during network retries or re-scanned log files:
1. ErrorInsight calculates an **Idempotency Hash** from:
   `hash = SHA256(source_name + "|" + source_id + "|" + timestamp + "|" + message)`
2. If the identical error event is transmitted again, ErrorInsight safely ignores the duplicate and increments the `duplicates` counter in the response.
3. Legitimate repeated errors (e.g. multiple connection timeouts at different seconds) have different timestamps and are **always preserved**.

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

## 7. Recommended Retry and Failure Handling Strategy

When integrating the Log Parser client:
1. **Transient Network Errors (502, 503, 504, Connection Reset):**
   - Implement exponential backoff with jitter (e.g., retry after 1s, 2s, 4s, up to 3 attempts).
2. **Client Validation Errors (400 Bad Request):**
   - Log the rejection details returned in the `errors` array. Do not retry without modifying the payload.
3. **Authentication Errors (401 Unauthorized):**
   - Verify that your client's API Key matches the `API_KEY` setting in ErrorInsight's `.env`.

---

## 8. Python Client Example

A complete, runnable Python client (`sample_parser_client.py`) is provided in the repository root. See the next section or run `python sample_parser_client.py` for a live demonstration.
