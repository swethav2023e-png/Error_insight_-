"""
Parser service for LogHealth.
Parses JSON (Format A and Format B) and plain-text log files into normalized record dictionaries.
"""


from datetime import datetime
import json
import re
from typing import Any, Dict, List, Optional, Tuple, Union

from .classifier_service import classify_category, normalize_severity


class ParseError(Exception):
    """Exception raised when an uploaded log or JSON cannot be parsed."""
    pass


# Regular expressions for common plain-text log formats
LOG_LINE_PATTERNS = [
    # Pattern 1: ISO/Standard Date + Level + Message
    # e.g.: 2026-10-29 08:00:00 [ERROR] Database connection failed
    # e.g.: 2026-10-29T08:00:00Z CRITICAL auth failed
    # e.g.: 2026-10-29 08:00:00,456 - ERROR - connection timed out
    re.compile(
        r"^(?:\[?(?P<timestamp>\d{4}[-/]\d{2}[-/]\d{2}[T ]\d{2}:\d{2}:\d{2}(?:[.,]\d+)?(?:Z|[+-]\d{2}:?\d{2})?)\]?)"
        r"\s*(?:[-–:]\s*)?"
        r"(?:\[?(?P<severity>[A-Za-z]+)\]?)"
        r"\s*(?:[-–:]\s*)?"
        r"(?:\[(?P<component>[^\]]+)\]\s*)?"
        r"(?:[-–:]\s*)?"
        r"(?P<message>.+)$"
    ),

    # Pattern 2: Bracketed Timestamp then Bracketed Severity
    # e.g.: [2026-10-29 08:00:00] [CRITICAL] [service] message
    re.compile(
        r"^\[(?P<timestamp>[^\]]+)\]\s*\[(?P<severity>[A-Za-z]+)\]\s*(?:\[(?P<component>[^\]]+)\]\s*)?(?P<message>.+)$"
    ),

    # Pattern 3: Syslog format (e.g., Oct 29 08:00:00 host app[1234]: ERROR message)
    re.compile(
        r"^(?P<timestamp>[A-Z][a-z]{2}\s+\d{1,2}\s+\d{2}:\d{2}:\d{2})\s+"
        r"(?P<host>[^\s]+)\s+"
        r"(?P<process>[^:\[]+)(?:\[(?P<pid>\d+)\])?:\s*"
        r"(?:\[?(?P<severity>FATAL|CRITICAL|ERROR|WARN|WARNING|INFO|DEBUG|NOTICE)\]?[:\s]*)?"
        r"(?P<message>.+)$",
        re.IGNORECASE
    )
]


def parse_json_data(data: Union[Dict, List], default_source: str = "upload") -> List[Dict[str, Any]]:
    """
    Parse and normalize JSON records in Format A or Format B.
    Format A: { "errors": [ { "id": 1, "timestamp": "...", "type": "Database", "message": "...", "severity": "Critical" } ] }
    Format B: [ { "timestamp": "...", "message": "...", "severity": "Warning" } ]
    """
    if isinstance(data, dict):
        raw_items = data.get("errors") or data.get("records") or data.get("data")
        if raw_items is None:
            # Check if it's a single error object
            if "message" in data or "error" in data or "description" in data:
                raw_items = [data]
            else:
                raise ParseError("JSON object must contain an 'errors' array or represent an error record.")
    elif isinstance(data, list):
        raw_items = data
    else:
        raise ParseError(f"Unsupported JSON root type: {type(data).__name__}. Expected an Array or Object.")

    if not isinstance(raw_items, list):
        raise ParseError("JSON 'errors' key must be a list of records.")

    normalized_records = []
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    for idx, item in enumerate(raw_items):
        if not isinstance(item, dict):
            continue

        message = (
            item.get("message")
            or item.get("error")
            or item.get("description")
            or item.get("msg")
            or ""
        )
        if not message:
            # Skip completely empty messages or record if id exists
            continue

        timestamp = str(item.get("timestamp") or item.get("time") or item.get("date") or now_str).strip()
        raw_type = item.get("type") or item.get("category")
        category = classify_category(message, raw_type)
        severity = normalize_severity(item.get("severity") or item.get("level"))
        source_id = str(item.get("id") or item.get("source_id") or "") if item.get("id") or item.get("source_id") else None
        source_name = str(item.get("source") or item.get("source_name") or default_source).strip()

        normalized_records.append({
            "source_id": source_id,
            "source_name": source_name,
            "timestamp": timestamp,
            "category": category,
            "message": str(message).strip(),
            "severity": severity
        })

    return normalized_records


def parse_plaintext_log(text_content: str, source_name: str = "system.log") -> List[Dict[str, Any]]:
    """
    Parse plain-text log files line by line using common pattern extractors.
    Unrecognized non-empty lines are preserved as raw application log entries.
    """
    if not text_content or not text_content.strip():
        raise ParseError("Log file is empty.")

    lines = text_content.strip().splitlines()
    records = []
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    for line_num, line in enumerate(lines, start=1):
        line = line.strip()
        if not line:
            continue

        matched = False
        for pattern in LOG_LINE_PATTERNS:
            m = pattern.match(line)
            if m:
                groups = m.groupdict()
                timestamp = groups.get("timestamp") or now_str
                # For syslog, format year if missing
                if len(timestamp.split()) == 3 and not re.search(r"\d{4}", timestamp):
                    timestamp = f"{datetime.now().year} {timestamp}"

                raw_sev = groups.get("severity") or "Error"
                message = groups.get("message") or line
                source_id = groups.get("pid") or str(line_num)
                category = classify_category(message)
                severity = normalize_severity(raw_sev)

                records.append({
                    "source_id": source_id,
                    "source_name": source_name,
                    "timestamp": timestamp,
                    "category": category,
                    "message": message.strip(),
                    "severity": severity
                })
                matched = True
                break

        if not matched:
            # Preserved raw log line
            category = classify_category(line)
            records.append({
                "source_id": str(line_num),
                "source_name": source_name,
                "timestamp": now_str,
                "category": category,
                "message": line,
                "severity": "Info" if "info" in line.lower() else "Error"
            })

    if not records:
        raise ParseError("No valid log lines could be extracted from the file.")

    return records


def parse_upload_payload(
    raw_content: bytes,
    filename: Optional[str] = None
) -> Tuple[List[Dict[str, Any]], str]:
    """
    Inspect file extension and content to parse either JSON or plain text.
    Returns (records, detected_format).
    """
    if not raw_content or not raw_content.strip():
        raise ParseError("Uploaded file is empty.")

    source_name = filename or "upload"

    # Decode bytes to text
    try:
        text = raw_content.decode("utf-8")
    except UnicodeDecodeError:
        try:
            text = raw_content.decode("latin-1")
        except Exception as exc:
            raise ParseError(f"Unsupported binary file encoding: {exc}")

    # Check if filename or content indicates JSON
    is_json = False
    if filename and filename.lower().endswith(".json"):
        is_json = True
    elif text.strip().startswith("{") or text.strip().startswith("["):
        is_json = True

    if is_json:
        try:
            data = json.loads(text)
        except json.JSONDecodeError as exc:
            raise ParseError(f"Invalid JSON syntax: {exc}")
        records = parse_json_data(data, default_source=source_name)
        return records, "JSON"
    else:
        records = parse_plaintext_log(text, source_name=source_name)
        return records, "Plain Text"
