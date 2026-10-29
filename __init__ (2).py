"""Services package for LogHealth – Log Analytics and System Health Intelligence."""
from .classifier_service import classify_category, normalize_severity
from .parser_service import parse_json_data, parse_plaintext_log, parse_upload_payload, ParseError
from .recommendation_service import get_recommendation_for_category, get_recommendation_for_error
from .analytics_service import (
    analyze_records_in_memory,
    compute_database_analytics,
    calculate_health_score,
    calculate_component_health,
    detect_anomalies,
    generate_health_report,
    compare_with_history
)

__all__ = [
    "classify_category",
    "normalize_severity",
    "parse_json_data",
    "parse_plaintext_log",
    "parse_upload_payload",
    "ParseError",
    "get_recommendation_for_category",
    "get_recommendation_for_error",
    "analyze_records_in_memory",
    "compute_database_analytics",
    "calculate_health_score",
    "calculate_component_health",
    "detect_anomalies",
    "generate_health_report",
    "compare_with_history"
]

