"""
Analytics service for ErrorInsight.
Computes real statistics, frequency distributions, recurring errors, trends, and Chart.js payloads.
"""

from collections import Counter
from datetime import datetime
from typing import Any, Dict, List, Optional

from .recommendation_service import get_recommendation_for_category

SEVERITY_ORDER = {"Critical": 4, "Error": 3, "Warning": 2, "Info": 1}

SEVERITY_PALETTE = {
    "Critical": "#ef4444",   # Crimson Red
    "Error": "#f97316",      # Vibrant Orange
    "Warning": "#f59e0b",    # Amber
    "Info": "#06b6d4",       # Cyber Cyan
}

CATEGORY_PALETTE = {
    "Database": "#8b5cf6",       # Violet
    "Authentication": "#ec4899", # Pink
    "Network": "#06b6d4",        # Cyan
    "File System": "#10b981",    # Emerald Green
    "Memory": "#f59e0b",         # Amber
    "Application": "#3b82f6",    # Blue
}


def analyze_records_in_memory(records: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Perform complete calculation over an in-memory list of normalized records.
    Used for immediate analysis returns during file upload or test evaluation.
    """
    total = len(records)
    if total == 0:
        return {
            "total_errors": 0,
            "unique_categories": 0,
            "severity_counts": {"Critical": 0, "Error": 0, "Warning": 0, "Info": 0},
            "category_counts": {},
            "recurring_errors": [],
            "recent_errors": [],
            "timeline": [],
            "recommendations": [],
            "chart_data": {
                "categories": {"labels": [], "data": [], "colors": []},
                "severities": {"labels": [], "data": [], "colors": []},
                "timeline": {"labels": [], "data": []}
            }
        }

    category_counts = Counter(r.get("category", "Application") for r in records)
    severity_counts = Counter(r.get("severity", "Error") for r in records)

    # Recurring error messages: group by (message, category)
    message_occurrences: Dict[str, Dict[str, Any]] = {}
    for r in records:
        msg = r.get("message", "Unknown error")
        cat = r.get("category", "Application")
        sev = r.get("severity", "Error")
        key = f"{cat}::: {msg}"
        if key not in message_occurrences:
            message_occurrences[key] = {
                "message": msg,
                "category": cat,
                "severity": sev,
                "count": 0,
                "last_seen": r.get("timestamp", "")
            }
        message_occurrences[key]["count"] += 1
        # Upgrade severity if a more severe instance was logged
        if SEVERITY_ORDER.get(sev, 0) > SEVERITY_ORDER.get(message_occurrences[key]["severity"], 0):
            message_occurrences[key]["severity"] = sev

    sorted_recurring = sorted(
        message_occurrences.values(),
        key=lambda x: (x["count"], SEVERITY_ORDER.get(x["severity"], 0)),
        reverse=True
    )[:10]

    # Timeline buckets: group by YYYY-MM-DD HH or YYYY-MM-DD
    time_counter = Counter()
    for r in records:
        ts = str(r.get("timestamp") or "").strip()
        if len(ts) >= 13:
            bucket = ts[:13]  # YYYY-MM-DD HH
        elif len(ts) >= 10:
            bucket = ts[:10]  # YYYY-MM-DD
        else:
            bucket = "Recent"
        time_counter[bucket] += 1

    sorted_timeline = sorted(time_counter.items(), key=lambda x: x[0])
    timeline_labels = [k for k, _ in sorted_timeline]
    timeline_values = [v for _, v in sorted_timeline]

    # Chart.js Category breakdown
    sorted_cat = sorted(category_counts.items(), key=lambda x: x[1], reverse=True)
    cat_labels = [k for k, _ in sorted_cat]
    cat_values = [v for _, v in sorted_cat]
    cat_colors = [CATEGORY_PALETTE.get(k, "#64748b") for k in cat_labels]

    # Chart.js Severity breakdown
    sev_keys = ["Critical", "Error", "Warning", "Info"]
    sev_labels = [k for k in sev_keys if severity_counts.get(k, 0) > 0]
    sev_values = [severity_counts.get(k, 0) for k in sev_labels]
    sev_colors = [SEVERITY_PALETTE.get(k, "#64748b") for k in sev_labels]

    # Category recommendations
    recommendations = []
    for cat, count in sorted_cat:
        rec = get_recommendation_for_category(cat)
        rec["error_count"] = count
        recommendations.append(rec)

    # Recent errors (last 15, newest first)
    recent = list(reversed(records))[:15]

    return {
        "total_errors": total,
        "unique_categories": len(category_counts),
        "critical_count": severity_counts.get("Critical", 0),
        "error_count": severity_counts.get("Error", 0),
        "warning_count": severity_counts.get("Warning", 0),
        "info_count": severity_counts.get("Info", 0),
        "severity_counts": dict(severity_counts),
        "category_counts": dict(category_counts),
        "recurring_errors": sorted_recurring,
        "recent_errors": recent,
        "timeline": [{"time": k, "count": v} for k, v in sorted_timeline],
        "recommendations": recommendations,
        "chart_data": {
            "categories": {
                "labels": cat_labels,
                "data": cat_values,
                "colors": cat_colors
            },
            "severities": {
                "labels": sev_labels,
                "data": sev_values,
                "colors": sev_colors
            },
            "timeline": {
                "labels": timeline_labels,
                "data": timeline_values
            }
        }
    }


def compute_database_analytics(db_analytics_raw: Dict[str, Any]) -> Dict[str, Any]:
    """
    Format raw database query results into full analytics response.
    """
    total = db_analytics_raw.get("total_records", 0)
    category_counts = db_analytics_raw.get("category_counts", {})
    severity_counts = db_analytics_raw.get("severity_counts", {})
    recurring = db_analytics_raw.get("recurring_errors", [])
    timeline = db_analytics_raw.get("timeline", [])
    recent = db_analytics_raw.get("recent_errors", [])

    # Sort categories
    sorted_cat = sorted(category_counts.items(), key=lambda x: x[1], reverse=True)
    cat_labels = [k for k, _ in sorted_cat]
    cat_values = [v for _, v in sorted_cat]
    cat_colors = [CATEGORY_PALETTE.get(k, "#64748b") for k in cat_labels]

    # Severities
    sev_keys = ["Critical", "Error", "Warning", "Info"]
    sev_labels = [k for k in sev_keys if severity_counts.get(k, 0) > 0]
    sev_values = [severity_counts.get(k, 0) for k in sev_labels]
    sev_colors = [SEVERITY_PALETTE.get(k, "#64748b") for k in sev_labels]

    # Timeline
    timeline_labels = [t["time"] for t in timeline]
    timeline_values = [t["count"] for t in timeline]

    # Recommendations
    recommendations = []
    for cat, count in sorted_cat:
        rec = get_recommendation_for_category(cat)
        rec["error_count"] = count
        recommendations.append(rec)

    return {
        "total_errors": total,
        "unique_categories": len(category_counts),
        "critical_count": severity_counts.get("Critical", 0),
        "error_count": severity_counts.get("Error", 0),
        "warning_count": severity_counts.get("Warning", 0),
        "info_count": severity_counts.get("Info", 0),
        "severity_counts": severity_counts,
        "category_counts": category_counts,
        "recurring_errors": recurring,
        "recent_errors": recent,
        "timeline": timeline,
        "recommendations": recommendations,
        "chart_data": {
            "categories": {
                "labels": cat_labels,
                "data": cat_values,
                "colors": cat_colors
            },
            "severities": {
                "labels": sev_labels,
                "data": sev_values,
                "colors": sev_colors
            },
            "timeline": {
                "labels": timeline_labels,
                "data": timeline_values
            }
        }
    }
