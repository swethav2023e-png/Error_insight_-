"""
Sample Log Ingestion Client for LogHealth.
Demonstrates how an external log collector or parser integrates with LogHealth
using Python and the `requests` library.

Run locally:
    python sample_parser_client.py
"""

import os
import sys
import time
from datetime import datetime
import requests

# Base configuration (backward-compatible with ERRORINSIGHT_URL)
BASE_URL = os.environ.get("LOGHEALTH_URL", os.environ.get("ERRORINSIGHT_URL", "http://127.0.0.1:5000"))
API_KEY = os.environ.get("API_KEY", "dev-secret-key-12345")


def check_backend_health() -> bool:
    """Verify LogHealth backend availability before dispatching logs."""
    health_url = f"{BASE_URL}/api/health"
    print(f"\n[1/3] Checking LogHealth backend health at {health_url}...")
    try:
        response = requests.get(health_url, timeout=5)
        if response.status_code == 200:
            data = response.json()
            print(f"  --> Connected successfully! Status: {data.get('status')}")
            print(f"  --> Platform: {data.get('app', 'LogHealth')} v{data.get('version', '2.0.0')}")
            print(f"  --> Stored records currently in database: {data.get('stored_record_count')}")
            return True
        else:
            print(f"  [!] Health check returned HTTP {response.status_code}: {response.text}")
            return False
    except requests.exceptions.RequestException as exc:
        print(f"  [!] Connection failed: {exc}")
        print("  Ensure LogHealth is running locally (`python app.py`) on http://127.0.0.1:5000")
        return False


def send_parsed_logs(records, source_name="External_LogCollector_v2.0", retries=3):
    """
    Transmit parsed log records to LogHealth's POST /api/logs endpoint.
    Handles authentication, payload wrapping, and exponential backoff.
    """
    endpoint = f"{BASE_URL}/api/logs"
    headers = {
        "X-API-Key": API_KEY,
        "Content-Type": "application/json",
        "X-Source-Project": source_name
    }

    payload = {"errors": records}

    print(f"\n[2/3] Sending {len(records)} parsed records to {endpoint}...")
    for attempt in range(1, retries + 1):
        try:
            response = requests.post(endpoint, json=payload, headers=headers, timeout=10)
            print(f"  --> HTTP Status: {response.status_code}")
            data = response.json()

            if response.status_code in (200, 201):
                print(f"  --> Success: {data.get('message')}")
                print(f"      Accepted:   {data.get('accepted')}")
                print(f"      Duplicates: {data.get('duplicates')}")
                print(f"      Rejected:   {data.get('rejected')}")
                return data
            elif response.status_code == 401:
                print(f"  [!] Authentication Failed (401): {data.get('error')}")
                print(f"      Check that your API_KEY ('{API_KEY}') matches the server configuration.")
                return None
            else:
                print(f"  [!] Request Error ({response.status_code}): {data}")
                return None

        except requests.exceptions.ConnectionError:
            print(f"  [!] Connection attempt {attempt}/{retries} failed. Server may be starting...")
            if attempt < retries:
                time.sleep(2 ** attempt)
        except Exception as exc:
            print(f"  [!] Unexpected error: {exc}")
            break

    return None


def main():
    print("=" * 70)
    print("  LogHealth – Sample Log Ingestion & System Health Client")
    print("=" * 70)

    # 1. Verify health
    healthy = check_backend_health()
    if not healthy:
        print("\nAborting transmission: LogHealth backend is not reachable.")
        sys.exit(1)

    # 2. Prepare sample parsed log records extracted by collector
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    sample_records = [
        {
            "id": "PARSER-EVT-9001",
            "timestamp": now,
            "type": "Database",
            "message": "PostgreSQL database connection pool saturated: timeout waiting for connection",
            "severity": "Critical"
        },
        {
            "id": "PARSER-EVT-9002",
            "timestamp": now,
            "type": "Authentication",
            "message": "Failed JWT signature verification from unauthorized client 192.168.1.50",
            "severity": "Error"
        },
        {
            "id": "PARSER-EVT-9003",
            "timestamp": now,
            "type": "Network",
            "message": "Gateway timeout (HTTP 504) received from upstream payment microservice",
            "severity": "Warning"
        },
        {
            "id": "PARSER-EVT-9004",
            "timestamp": now,
            "type": "Memory",
            "message": "JVM Garbage collection pause exceeded 4500ms: high memory pressure",
            "severity": "Warning"
        }
    ]

    # 3. Transmit batch
    result1 = send_parsed_logs(sample_records)

    # 4. Test Idempotency / Duplicate Detection:
    # Re-transmitting the exact same records should be safely flagged as duplicates
    print("\n[3/3] Re-sending the identical batch to verify idempotency / duplicate protection...")
    result2 = send_parsed_logs(sample_records)

    print("\n" + "=" * 70)
    print("LogHealth integration client test finished.")
    print(f"View the live system intelligence dashboard at: {BASE_URL}")
    print("=" * 70 + "\n")


if __name__ == "__main__":
    main()
