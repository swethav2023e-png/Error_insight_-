"""
REST API routes for ErrorInsight.
Implements all required endpoints with validation, API-key authentication,
database persistence, and standardized JSON responses.
"""

from functools import wraps
import json
import logging
from typing import Any, Callable, Dict, Tuple

from flask import Blueprint, current_app, jsonify, request

from config import get_config
from database.db import DatabaseError, get_db
from services.analytics_service import analyze_records_in_memory, compute_database_analytics
from services.parser_service import ParseError, parse_json_data, parse_upload_payload
from services.recommendation_service import get_recommendation_for_error

logger = logging.getLogger(__name__)

api_bp = Blueprint("api", __name__, url_prefix="/api")


def require_api_key(f: Callable) -> Callable:
    """Decorator to protect data ingestion endpoints with API Key verification."""
    @wraps(f)
    def decorated_function(*args: Any, **kwargs: Any) -> Any:
        configured_key = current_app.config.get("API_KEY", "dev-secret-key-12345")

        # Check X-API-Key header or Authorization: Bearer <token>
        auth_header = request.headers.get("X-API-Key")
        if not auth_header:
            auth_header = request.headers.get("Authorization")
            if auth_header and auth_header.startswith("Bearer "):
                auth_header = auth_header[7:].strip()

        # Also check query param ?api_key= for simple testing
        if not auth_header:
            auth_header = request.args.get("api_key")

        if not auth_header or auth_header != configured_key:
            logger.warning("Unauthorized API access attempt from %s", request.remote_addr)
            return jsonify({
                "status": "error",
                "error": "Unauthorized. A valid 'X-API-Key' header is required.",
                "hint": "Set X-API-Key in your HTTP request headers."
            }), 401

        return f(*args, **kwargs)
    return decorated_function


@api_bp.route("/health", methods=["GET"])
def health_check() -> Tuple[Any, int]:
    """
    GET /api/health
    Return application status, database connectivity, and stored record count.
    """
    db = get_db()
    health = db.check_health()
    if not health.get("connected"):
        return jsonify({
            "status": "error",
            "service": "ErrorInsight API",
            "database": "disconnected",
            "details": health.get("error", "Database unavailable")
        }), 503

    return jsonify({
        "status": "healthy",
        "service": "ErrorInsight – Intelligent Error Analyzer",
        "database": health.get("engine", "SQLite"),
        "database_file": health.get("database_file"),
        "stored_record_count": health.get("record_count", 0),
        "version": "1.0.0"
    }), 200


@api_bp.route("/logs", methods=["POST"])
@require_api_key
def ingest_logs() -> Tuple[Any, int]:
    """
    POST /api/logs
    Shared endpoint for Log Parser integration.
    Accepts JSON records directly from external Log Parser projects.
    Validates, normalizes, detects duplicates, and persists records.
    """
    if not request.is_json:
        return jsonify({
            "status": "error",
            "error": "Invalid Content-Type. Expected 'application/json'."
        }), 400

    try:
        payload = request.get_json(silent=True)
        if payload is None:
            return jsonify({
                "status": "error",
                "error": "Malformed JSON payload in request body."
            }), 400

        source_name = request.headers.get("X-Source-Project", "log_parser_client")
        records = parse_json_data(payload, default_source=source_name)

        if not records:
            return jsonify({
                "status": "error",
                "error": "No valid error records found in JSON payload.",
                "accepted": 0,
                "rejected": 0,
                "duplicates": 0
            }), 400

        db = get_db()
        persist_result = db.insert_records(records)

        status_code = 201 if persist_result["accepted"] > 0 else 200

        return jsonify({
            "status": "success",
            "message": f"Processed {len(records)} records: {persist_result['accepted']} accepted, {persist_result['duplicates']} duplicate(s), {persist_result['rejected']} rejected.",
            "accepted": persist_result["accepted"],
            "duplicates": persist_result["duplicates"],
            "rejected": persist_result["rejected"],
            "errors": persist_result["errors"],
            "total_submitted": len(records)
        }), status_code

    except ParseError as pe:
        return jsonify({"status": "error", "error": str(pe)}), 400
    except DatabaseError as de:
        logger.exception("Database error in /api/logs")
        return jsonify({"status": "error", "error": f"Database failure: {de}"}), 500
    except Exception as exc:
        logger.exception("Unexpected error in /api/logs")
        return jsonify({"status": "error", "error": f"Internal server error: {exc}"}), 500


@api_bp.route("/analyze", methods=["POST"])
def analyze_logs() -> Tuple[Any, int]:
    """
    POST /api/analyze
    Accepts JSON (body or file upload) or plain-text log files.
    Analyzes data, calculates metrics, and persists valid records to the database.
    """
    records = []
    source_name = "upload"

    try:
        # Check if file was uploaded via multipart/form-data
        if "file" in request.files:
            file_storage = request.files["file"]
            if not file_storage.filename:
                return jsonify({"status": "error", "error": "No file selected."}), 400

            source_name = file_storage.filename
            raw_bytes = file_storage.read()
            records, detected_format = parse_upload_payload(raw_bytes, filename=source_name)

        # Check if JSON was submitted in the request body
        elif request.is_json:
            payload = request.get_json(silent=True)
            if payload is None:
                return jsonify({"status": "error", "error": "Malformed JSON payload."}), 400
            source_name = request.headers.get("X-Source-Project", "direct_json")
            records = parse_json_data(payload, default_source=source_name)

        # Check if raw text was posted
        elif request.data:
            records, detected_format = parse_upload_payload(request.data, filename="raw_text.log")

        else:
            return jsonify({
                "status": "error",
                "error": "No log data provided. Please upload a file or submit JSON."
            }), 400

        if not records:
            return jsonify({
                "status": "error",
                "error": "No valid error records could be parsed from input."
            }), 400

        # Calculate metrics immediately for the parsed records
        analysis_result = analyze_records_in_memory(records)

        # Persist to database
        db = get_db()
        save_stats = {"accepted": 0, "duplicates": 0, "rejected": 0, "errors": []}
        db_warning = None

        try:
            save_stats = db.insert_records(records)
        except (DatabaseError, Exception) as db_exc:
            logger.exception("Database saving failed during /api/analyze")
            db_warning = f"Analysis succeeded, but database saving failed: {db_exc}"

        return jsonify({
            "status": "success",
            "source_name": source_name,
            "saved_to_database": save_stats["accepted"],
            "duplicates": save_stats["duplicates"],
            "rejected": save_stats["rejected"],
            "database_warning": db_warning,
            "analysis": analysis_result
        }), 200

    except ParseError as pe:
        return jsonify({"status": "error", "error": str(pe)}), 400
    except Exception as exc:
        logger.exception("Unexpected error in /api/analyze")
        return jsonify({"status": "error", "error": f"Analysis failed: {exc}"}), 500


@api_bp.route("/history", methods=["GET"])
def get_history() -> Tuple[Any, int]:
    """
    GET /api/history
    Retrieve saved records with pagination, filtering, and search.
    Query parameters:
    - page (int, default 1)
    - limit (int, default 50)
    - severity (str: Critical, Error, Warning, Info)
    - category (str: Database, Authentication, Network, File System, Memory, Application)
    - source (str: filter by source_name)
    - search or q (str: text search in message or source_id)
    - sort_by (str: timestamp, category, severity, created_at)
    - sort_dir (str: asc, desc)
    """
    try:
        page = int(request.args.get("page", 1))
        limit = int(request.args.get("limit", 50))
    except (ValueError, TypeError):
        page = 1
        limit = 50

    severity = request.args.get("severity")
    category = request.args.get("category")
    source = request.args.get("source")
    search = request.args.get("search") or request.args.get("q")
    sort_by = request.args.get("sort_by", "timestamp")
    sort_dir = request.args.get("sort_dir", "desc")

    db = get_db()
    try:
        result = db.get_records(
            page=page,
            limit=limit,
            severity=severity,
            category=category,
            source=source,
            search=search,
            sort_by=sort_by,
            sort_dir=sort_dir
        )
        return jsonify({
            "status": "success",
            "pagination": result["pagination"],
            "records": result["records"]
        }), 200
    except DatabaseError as de:
        logger.exception("Database error in /api/history")
        return jsonify({
            "status": "error",
            "error": "History is temporarily unavailable.",
            "records": [],
            "pagination": {"page": page, "limit": limit, "total_records": 0, "total_pages": 0}
        }), 503


@api_bp.route("/analytics", methods=["GET"])
def get_analytics() -> Tuple[Any, int]:
    """
    GET /api/analytics
    Return summary statistics, frequency distributions, and Chart.js datasets
    computed directly from persistent database records.
    """
    db = get_db()
    try:
        raw_data = db.get_analytics_data()
        formatted_analytics = compute_database_analytics(raw_data)
        return jsonify({
            "status": "success",
            "analytics": formatted_analytics
        }), 200
    except DatabaseError as de:
        logger.exception("Database error in /api/analytics")
        return jsonify({
            "status": "error",
            "error": f"Failed to compute analytics: {de}"
        }), 503


@api_bp.route("/errors/<int:error_id>", methods=["GET"])
def get_error_detail(error_id: int) -> Tuple[Any, int]:
    """
    GET /api/errors/{id}
    Return full details of a specific stored error record, including tailored recommendations.
    """
    db = get_db()
    try:
        record = db.get_record_by_id(error_id)
        if not record:
            return jsonify({
                "status": "error",
                "error": f"Error record with ID {error_id} not found."
            }), 404

        recommendation = get_recommendation_for_error(
            record["category"],
            record["message"]
        )

        return jsonify({
            "status": "success",
            "record": record,
            "recommendation": recommendation
        }), 200
    except DatabaseError as de:
        logger.exception("Database error in /api/errors/%s", error_id)
        return jsonify({"status": "error", "error": f"Database query failed: {de}"}), 500


@api_bp.route("/docs", methods=["GET"])
def get_api_docs() -> Tuple[Any, int]:
    """
    GET /api/docs
    Return OpenAPI-style documentation specification in JSON.
    """
    cfg = get_config()
    return jsonify({
        "title": "ErrorInsight REST API Documentation",
        "version": "1.0.0",
        "description": "Integration API for Log Parsers and System Monitoring clients.",
        "authentication": {
            "type": "API Key",
            "header": "X-API-Key",
            "query_parameter": "api_key",
            "configured_key": cfg.API_KEY,
            "note": "Required for POST /api/logs"
        },
        "endpoints": [
            {
                "path": "/api/health",
                "method": "GET",
                "description": "Check application health, database connectivity, and total stored records.",
                "auth_required": False,
                "response_codes": [200, 503]
            },
            {
                "path": "/api/logs",
                "method": "POST",
                "description": "Primary integration endpoint for friend's Log Parser. Ingests normalized error records.",
                "auth_required": True,
                "headers": {"X-API-Key": "<key>", "Content-Type": "application/json"},
                "accepted_formats": ["Format A (Object with 'errors' array)", "Format B (Array of error objects)"],
                "response_codes": [201, 200, 400, 401, 500]
            },
            {
                "path": "/api/analyze",
                "method": "POST",
                "description": "Upload a JSON file or plain-text log file for immediate analysis and persistence.",
                "auth_required": False,
                "supported_formats": [".json", ".log", ".txt", "raw text"],
                "response_codes": [200, 400, 500]
            },
            {
                "path": "/api/history",
                "method": "GET",
                "description": "Retrieve stored error history with pagination, category/severity filtering, and search.",
                "query_params": ["page", "limit", "severity", "category", "source", "search", "sort_by", "sort_dir"],
                "auth_required": False,
                "response_codes": [200, 503]
            },
            {
                "path": "/api/analytics",
                "method": "GET",
                "description": "Fetch aggregated analytics metrics, recurring error frequencies, and Chart.js datasets.",
                "auth_required": False,
                "response_codes": [200, 503]
            },
            {
                "path": "/api/errors/{id}",
                "method": "GET",
                "description": "Retrieve a single stored error by ID with rule-based diagnostic suggestions.",
                "auth_required": False,
                "response_codes": [200, 404, 500]
            }
        ]
    }), 200


@api_bp.route("/demo", methods=["GET"])
def get_demo_data() -> Tuple[Any, int]:
    """
    GET /api/demo
    Load sample records for instant dashboard demonstration.
    """
    from pathlib import Path
    root = Path(__file__).resolve().parent.parent
    sample_paths = [
        root / "sample_data" / "format_a_errors.json",
        root / "errors.json"
    ]
    for p in sample_paths:
        if p.is_file():
            try:
                with open(p, "r", encoding="utf-8") as f:
                    data = json.load(f)
                records = parse_json_data(data, default_source="demo_dataset")
                analysis = analyze_records_in_memory(records)
                return jsonify({
                    "status": "success",
                    "source": p.name,
                    "analysis": analysis
                }), 200
            except Exception as exc:
                logger.error("Failed to load demo file %s: %s", p, exc)

    return jsonify({"status": "error", "error": "Demo data file not found."}), 404


@api_bp.route("/seed", methods=["POST"])
def seed_demo_to_db() -> Tuple[Any, int]:
    """
    POST /api/seed
    Seed sample errors into the database so charts and history have rich data to display.
    """
    from pathlib import Path
    root = Path(__file__).resolve().parent.parent
    sample_file = root / "sample_data" / "format_a_errors.json"
    if not sample_file.is_file():
        sample_file = root / "errors.json"

    if not sample_file.is_file():
        return jsonify({"status": "error", "error": "Seed file not found."}), 404

    try:
        with open(sample_file, "r", encoding="utf-8") as f:
            data = json.load(f)
        records = parse_json_data(data, default_source="sample_dataset")
        db = get_db()
        result = db.insert_records(records)
        return jsonify({
            "status": "success",
            "message": f"Seeded database: {result['accepted']} new record(s), {result['duplicates']} duplicate(s).",
            "result": result
        }), 200
    except Exception as exc:
        logger.exception("Failed to seed database")
        return jsonify({"status": "error", "error": str(exc)}), 500


@api_bp.route("/clear", methods=["POST"])
def clear_db() -> Tuple[Any, int]:
    """
    POST /api/clear
    Clear all records from error_logs.
    """
    db = get_db()
    try:
        deleted = db.clear_all()
        return jsonify({
            "status": "success",
            "message": f"Cleared {deleted} record(s) from database.",
            "deleted_count": deleted
        }), 200
    except DatabaseError as de:
        return jsonify({"status": "error", "error": str(de)}), 500
