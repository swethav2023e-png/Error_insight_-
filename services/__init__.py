"""Services package for ErrorInsight."""
from .classifier_service import classify_category, normalize_severity
from .parser_service import parse_json_data, parse_plaintext_log, parse_upload_payload, ParseError
from .recommendation_service import get_recommendation_for_category, get_recommendation_for_error
from .analytics_service import analyze_records_in_memory, compute_database_analytics

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
    "compute_database_analytics"
]
