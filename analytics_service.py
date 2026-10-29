"""
Analytics service for LogHealth – Log Analytics and System Health Intelligence.
Computes explainable system health scores, component risk ranking, anomaly detection,
historical baselines, and structured health reports from real log data.
"""

from collections import Counter
from datetime import datetime
import math
from typing import Any, Dict, List, Optional, Tuple

from .recommendation_service import get_recommendation_for_category

SEVERITY_ORDER = {"Critical": 4, "Error": 3, "Warning": 2, "Info": 1}

SEVERITY_PALETTE = {
    "Critical": "#ef4444",   # Crimson Red
    "Error": "#f97316",      # Vibrant Orange
    "Warning": "#f59e0b",    # Amber
    "Info": "#06b6d4",       # Cyber Cyan
}

CATEGORY_PALETTE = {
    "Database": "#8b5cf6",         # Violet
    "Authentication": "#ec4899",   # Pink
    "Network": "#06b6d4",          # Cyan
    "File System": "#10b981",      # Emerald Green
    "Memory": "#f59e0b",           # Amber
    "API & Backend": "#6366f1",    # Indigo
    "Background Jobs": "#14b8a6",  # Teal
    "Infrastructure": "#64748b",   # Slate
    "Application": "#3b82f6",      # Blue
}


def calculate_health_score(
    total_events: int,
    severity_counts: Dict[str, int],
    component_counts: Dict[str, int],
    anomalies_count: int = 0
) -> Dict[str, Any]:
    """
    Compute an explainable, evidence-based system health score (0-100).
    When no log events exist, returns an explicit Insufficient Data state.
    """
    if total_events <= 0:
        return {
            "score": None,
            "status": "Insufficient Data",
            "has_sufficient_data": False,
            "formula": "Score = 100 - (Critical*12 + Error*4 + Warning*1.5) * DensityFactor - AnomalyPenalty",
            "formula_description": "Health score requires at least one ingested log event. Currently no data is present.",
            "deductions": {
                "base": 100,
                "critical_deduction": 0.0,
                "error_deduction": 0.0,
                "warning_deduction": 0.0,
                "anomaly_deduction": 0.0,
                "concentration_deduction": 0.0,
                "density_factor": 0.0,
                "final_score": None
            },
            "plain_english_summary": "No logs have been ingested yet. System health cannot be determined."
        }

    critical = severity_counts.get("Critical", 0)
    errors = severity_counts.get("Error", 0)
    warnings = severity_counts.get("Warning", 0)

    # Failure ratio calculation
    failure_events = critical + errors
    failure_ratio = failure_events / max(1, total_events)

    # Dynamic density weight scales appropriately to prevent skew in very small or very large datasets
    density_weight = min(1.5, max(0.4, 0.4 + (failure_ratio * 1.1)))

    crit_deduction = round(critical * 12.0 * density_weight, 1)
    err_deduction = round(errors * 4.0 * density_weight, 1)
    warn_deduction = round(warnings * 1.5 * density_weight, 1)
    anomaly_deduction = round(min(20.0, anomalies_count * 4.0), 1)

    # Component concentration penalty: checks if failures are concentrated heavily in a single component
    concentration_deduction = 0.0
    if failure_events >= 3 and component_counts:
        top_cat_count = max(component_counts.values())
        if (top_cat_count / max(1, failure_events)) >= 0.65:
            concentration_deduction = 5.0

    total_deductions = crit_deduction + err_deduction + warn_deduction + anomaly_deduction + concentration_deduction
    raw_score = max(0, min(100, round(100.0 - total_deductions)))

    if raw_score >= 90:
        status = "Healthy"
        summary = f"System operational health is optimal ({raw_score}/100) with minimal non-critical anomalies."
    elif raw_score >= 75:
        status = "Degraded"
        summary = f"System health is degraded ({raw_score}/100) due to elevated warnings or moderate errors."
    elif raw_score >= 50:
        status = "Warning"
        summary = f"System health requires attention ({raw_score}/100) due to significant error concentrations."
    else:
        status = "Critical"
        summary = f"System health is in critical condition ({raw_score}/100) with severe or cascading failures."

    return {
        "score": raw_score,
        "status": status,
        "has_sufficient_data": True,
        "formula": "Score = max(0, min(100, 100 - (Critical*12 + Error*4 + Warning*1.5) * DensityFactor - AnomalyPenalty - ConcentrationPenalty))",
        "formula_description": (
            "Evidence-based score starting at 100 base points. Deducts points weighted by severity "
            "(Critical: -12, Error: -4, Warning: -1.5), adjusted by failure density factor, "
            "anomaly bursts (-4 each, max -20), and single-component failure concentration (-5)."
        ),
        "deductions": {
            "base": 100,
            "critical_deduction": crit_deduction,
            "error_deduction": err_deduction,
            "warning_deduction": warn_deduction,
            "anomaly_deduction": anomaly_deduction,
            "concentration_deduction": concentration_deduction,
            "density_factor": round(density_weight, 2),
            "final_score": raw_score
        },
        "plain_english_summary": summary
    }


def calculate_component_health(
    records: List[Dict[str, Any]],
    recurring_messages: List[Dict[str, Any]]
) -> List[Dict[str, Any]]:
    """
    Calculate component-level metrics and evidence-based risk ranking.
    """
    if not records:
        return []

    comp_groups: Dict[str, List[Dict[str, Any]]] = {}
    for r in records:
        comp = r.get("category", "Application")
        if comp not in comp_groups:
            comp_groups[comp] = []
        comp_groups[comp].append(r)

    component_health_list = []

    for comp_name, items in comp_groups.items():
        total_comp = len(items)
        crit = sum(1 for x in items if x.get("severity") == "Critical")
        err = sum(1 for x in items if x.get("severity") == "Error")
        warn = sum(1 for x in items if x.get("severity") == "Warning")
        info = sum(1 for x in items if x.get("severity") == "Info")

        failure_count = crit + err
        failure_rate = round((failure_count / max(1, total_comp)) * 100.0, 1)

        # Check recurring messages belonging to this component
        comp_recurring = [rm for rm in recurring_messages if rm.get("category") == comp_name]
        recurring_count = sum(rm.get("count", 0) for rm in comp_recurring)

        # Evidence-based risk score (0 to 100)
        risk_score = min(100, int((crit * 25) + (err * 8) + (warn * 2) + (recurring_count * 3)))
        if risk_score >= 70 or crit >= 2:
            risk_level = "Critical"
        elif risk_score >= 40 or crit == 1 or err >= 5:
            risk_level = "High"
        elif risk_score >= 15 or err >= 2 or warn >= 4:
            risk_level = "Medium"
        else:
            risk_level = "Low"

        # Concrete evidence strings
        evidence = []
        if crit > 0:
            evidence.append(f"{crit} critical severity failure(s) recorded.")
        if err > 0:
            evidence.append(f"{err} application error(s) logged (failure rate: {failure_rate}%).")
        if recurring_count > 0:
            evidence.append(f"{len(comp_recurring)} recurring pattern(s) across {recurring_count} total occurrences.")
        if warn > 0:
            evidence.append(f"{warn} warning event(s) observed.")
        if not evidence:
            evidence.append("Operational telemetry normal with informational logs.")

        rec_info = get_recommendation_for_category(comp_name)

        component_health_list.append({
            "component": comp_name,
            "total_events": total_comp,
            "critical_count": crit,
            "error_count": err,
            "warning_count": warn,
            "info_count": info,
            "failure_rate": failure_rate,
            "risk_score": risk_score,
            "risk_level": risk_level,
            "evidence": evidence,
            "recommended_actions": rec_info.get("recommended_solutions", [])[:3]
        })

    # Rank components by evidence-based risk descending
    risk_order = {"Critical": 4, "High": 3, "Medium": 2, "Low": 1}
    component_health_list.sort(
        key=lambda x: (risk_order.get(x["risk_level"], 0), x["risk_score"], x["total_events"]),
        reverse=True
    )

    return component_health_list


def detect_anomalies(
    records: List[Dict[str, Any]],
    timeline: List[Dict[str, Any]],
    component_counts: Dict[str, int]
) -> List[Dict[str, Any]]:
    """
    Detect statistical volume spikes, critical failure bursts, and subsystem failure concentrations.
    Clearly distinguishes between observed facts and suspected causes.
    """
    anomalies: List[Dict[str, Any]] = []
    if not records:
        return anomalies

    # 1. Timeline Volume Spikes
    if len(timeline) >= 2:
        counts = [t["count"] for t in timeline]
        mean_vol = sum(counts) / len(counts)
        variance = sum((c - mean_vol) ** 2 for c in counts) / len(counts)
        std_dev = math.sqrt(variance)

        threshold = mean_vol + max(2.0, 1.5 * std_dev)

        for bucket in timeline:
            if bucket["count"] > threshold and bucket["count"] >= 3:
                anomalies.append({
                    "id": f"anom-vol-{bucket['time']}",
                    "type": "Volume Spike",
                    "severity": "Warning" if bucket["count"] < (mean_vol * 3) else "Critical",
                    "time_bucket": bucket["time"],
                    "event_count": bucket["count"],
                    "observed_fact": (
                        f"Time bucket '{bucket['time']}' recorded {bucket['count']} events, "
                        f"exceeding the average baseline of {mean_vol:.1f} events/interval "
                        f"(threshold: {threshold:.1f})."
                    ),
                    "suspected_cause": (
                        "Sudden workload surge, retry loop cascade, or repeated exception logging."
                    ),
                    "recommendation": "Inspect detailed timestamps and query logs in this window for runaway processes."
                })

    # 2. Critical Failure Bursts
    crit_records = [r for r in records if r.get("severity") == "Critical"]
    if len(crit_records) >= 2:
        # Check if multiple critical records occur in the same hour or close together
        crit_times = Counter(str(r.get("timestamp", ""))[:13] for r in crit_records if r.get("timestamp"))
        for bucket, count in crit_times.items():
            if count >= 2:
                anomalies.append({
                    "id": f"anom-crit-{bucket}",
                    "type": "Critical Error Burst",
                    "severity": "Critical",
                    "time_bucket": bucket,
                    "event_count": count,
                    "observed_fact": f"{count} critical severity events clustered within interval '{bucket}'.",
                    "suspected_cause": "Major subsystem interruption, authentication boundary failure, or unhandled crash.",
                    "recommendation": "Check application service availability and inspect critical event stack traces immediately."
                })

    # 3. Single Subsystem Failure Concentration
    failure_records = [r for r in records if r.get("severity") in ("Critical", "Error")]
    if len(failure_records) >= 4 and component_counts:
        top_comp, top_count = max(component_counts.items(), key=lambda x: x[1])
        fail_ratio = top_count / len(failure_records)
        if fail_ratio >= 0.70:
            anomalies.append({
                "id": f"anom-concentrate-{top_comp}",
                "type": "Subsystem Failure Concentration",
                "severity": "High",
                "time_bucket": "Cumulative Session",
                "event_count": top_count,
                "observed_fact": (
                    f"{round(fail_ratio * 100, 1)}% of all system errors ({top_count}/{len(failure_records)}) "
                    f"are isolated within the '{top_comp}' subsystem."
                ),
                "suspected_cause": f"Localized failure or upstream dependency outage specifically targeting {top_comp}.",
                "recommendation": f"Focus triage and telemetry specifically on {top_comp} configuration and dependencies."
            })

    return anomalies


def calculate_prioritized_risks(
    component_health: List[Dict[str, Any]],
    anomalies: List[Dict[str, Any]],
    recurring_errors: List[Dict[str, Any]]
) -> List[Dict[str, Any]]:
    """
    Generate transparent, evidence-based operational risks ranked by severity and frequency.
    """
    risks = []

    # Component risks
    for ch in component_health:
        if ch["risk_level"] in ("Critical", "High", "Medium"):
            risks.append({
                "title": f"Elevated Risk in {ch['component']} Subsystem",
                "risk_level": ch["risk_level"],
                "component": ch["component"],
                "event_count": ch["total_events"],
                "why_it_matters": (
                    f"High failure rate ({ch['failure_rate']}%) with {ch['critical_count']} critical "
                    f"and {ch['error_count']} standard errors threatens subsystem stability."
                ),
                "evidence": "; ".join(ch["evidence"]),
                "recommended_actions": ch["recommended_actions"]
            })

    # Recurring pattern risks
    for re_item in recurring_errors[:3]:
        if re_item.get("count", 0) >= 3:
            risks.append({
                "title": f"Chronic Recurring Signature in {re_item.get('category', 'Application')}",
                "risk_level": "High" if re_item.get("severity") in ("Critical", "Error") else "Medium",
                "component": re_item.get("category", "Application"),
                "event_count": re_item.get("count", 0),
                "why_it_matters": (
                    f"The error '{re_item.get('message', '')[:60]}...' has reoccurred {re_item.get('count')} times, "
                    "signifying an unmitigated systematic defect."
                ),
                "evidence": f"Logged {re_item.get('count')} times. Last observed at {re_item.get('last_seen', 'recent')}.",
                "recommended_actions": [
                    "Isolate root cause of repeated failure signature.",
                    "Verify automated retry limits to avoid log exhaustion."
                ]
            })

    # Sort risks by severity level
    risk_order = {"Critical": 4, "High": 3, "Medium": 2, "Low": 1}
    risks.sort(key=lambda x: (risk_order.get(x["risk_level"], 0), x["event_count"]), reverse=True)
    return risks


def compare_with_history(
    current_records: List[Dict[str, Any]],
    historical_records: Optional[List[Dict[str, Any]]] = None
) -> Dict[str, Any]:
    """
    Compare current session against persistent historical baseline.
    Explicitly labels when historical data is insufficient.
    """
    if not historical_records or len(historical_records) <= len(current_records):
        return {
            "has_baseline": False,
            "message": "Single session or initial ingestion. Additional historical data required for trend comparison.",
            "delta_volume_percent": 0.0,
            "historical_total": len(historical_records) if historical_records else 0,
            "new_signatures": [],
            "resolved_signatures": []
        }

    # Partition historical records (excluding current batch if current is subset of history)
    current_hashes = {r.get("idempotency_hash") or r.get("message") for r in current_records}
    prior_records = [r for r in historical_records if (r.get("idempotency_hash") or r.get("message")) not in current_hashes]

    if not prior_records:
        return {
            "has_baseline": False,
            "message": "Historical records match current dataset exactly; baseline comparison unavailable.",
            "delta_volume_percent": 0.0,
            "historical_total": len(historical_records),
            "new_signatures": [],
            "resolved_signatures": []
        }

    current_sigs = {r.get("message", "").strip() for r in current_records if r.get("message")}
    prior_sigs = {r.get("message", "").strip() for r in prior_records if r.get("message")}

    new_sigs = list(current_sigs - prior_sigs)[:5]
    resolved_sigs = list(prior_sigs - current_sigs)[:5]

    vol_diff = len(current_records) - len(prior_records)
    delta_vol = round((vol_diff / max(1, len(prior_records))) * 100.0, 1)

    return {
        "has_baseline": True,
        "message": f"Compared with {len(prior_records)} prior historical log records.",
        "delta_volume_percent": delta_vol,
        "historical_total": len(prior_records),
        "new_signatures_count": len(new_sigs),
        "new_signatures": new_sigs,
        "resolved_signatures_count": len(resolved_sigs),
        "resolved_signatures": resolved_sigs
    }


def generate_health_report(analytics: Dict[str, Any]) -> Dict[str, Any]:
    """
    Generate structured, professional System Health Report with 10 required sections.
    """
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S UTC")
    health_score = analytics.get("health_score", {})
    score_val = health_score.get("score")
    score_display = f"{score_val}/100 ({health_score.get('status', 'Unknown')})" if score_val is not None else "N/A (Insufficient Data)"

    total = analytics.get("total_errors", 0)
    crit = analytics.get("critical_count", 0)
    err = analytics.get("error_count", 0)
    warn = analytics.get("warning_count", 0)
    info = analytics.get("info_count", 0)

    component_health = analytics.get("component_health", [])
    anomalies = analytics.get("anomalies", [])
    risks = analytics.get("prioritized_risks", [])
    recurring = analytics.get("recurring_errors", [])
    historical = analytics.get("historical_comparison", {})

    # Markdown document compilation
    md_lines = [
        "# LogHealth – System Health & Reliability Report",
        f"**Generated:** {now_str}  ",
        f"**System Health Status:** {health_score.get('status', 'N/A')}  ",
        f"**Overall Health Score:** {score_display}  ",
        "",
        "---",
        "",
        "## 1. Executive Summary",
        analytics.get("plain_english_summary", "Operational log analysis completed."),
        "",
        "## 2. Overall Health Assessment",
        f"- **Health Score:** {score_display}",
        f"- **Scoring Formula:** `{health_score.get('formula', '')}`",
        f"- **Formula Explanation:** {health_score.get('formula_description', '')}",
        "",
        "## 3. Key Telemetry Statistics",
        f"- **Total Events Processed:** {total}",
        f"- **Critical Failures:** {crit}",
        f"- **Application Errors:** {err}",
        f"- **System Warnings:** {warn}",
        f"- **Informational Events:** {info}",
        f"- **Unique Subsystems Monitored:** {analytics.get('unique_categories', 0)}",
        "",
        "## 4. Severity Distribution",
        "| Severity | Event Count | Percentage |",
        "| :--- | :--- | :--- |",
        f"| Critical | {crit} | {round((crit / max(1, total)) * 100, 1)}% |",
        f"| Error | {err} | {round((err / max(1, total)) * 100, 1)}% |",
        f"| Warning | {warn} | {round((warn / max(1, total)) * 100, 1)}% |",
        f"| Info | {info} | {round((info / max(1, total)) * 100, 1)}% |",
        "",
        "## 5. Component & Subsystem Health Matrix",
        "| Component | Total Events | Failure Rate | Risk Level | Primary Evidence |",
        "| :--- | :--- | :--- | :--- | :--- |"
    ]

    for ch in component_health:
        ev_summary = ch["evidence"][0] if ch["evidence"] else "Normal"
        md_lines.append(f"| {ch['component']} | {ch['total_events']} | {ch['failure_rate']}% | {ch['risk_level']} | {ev_summary} |")

    if not component_health:
        md_lines.append("| None | 0 | 0.0% | Low | No log events observed |")

    md_lines.extend([
        "",
        "## 6. Trends and Recurring Patterns",
        f"Observed **{len(recurring)}** prominent recurring failure signatures.",
        ""
    ])
    for r in recurring[:5]:
        md_lines.append(f"- **[{r.get('severity', 'Error')}] {r.get('category', 'App')}** ({r.get('count')} occurrences): `{r.get('message', '')}`")

    md_lines.extend([
        "",
        "## 7. Detected Anomalies",
    ])
    if anomalies:
        for a in anomalies:
            md_lines.append(f"- **[{a.get('severity', 'Warning')}] {a.get('type')}:** {a.get('observed_fact')}")
    else:
        md_lines.append("No statistical volume spikes or critical error bursts detected in this log window.")

    md_lines.extend([
        "",
        "## 8. Prioritized Operational Risks",
    ])
    if risks:
        for rk in risks:
            md_lines.append(f"### {rk['title']} ({rk['risk_level']} Risk)")
            md_lines.append(f"- **Affected Component:** {rk.get('component', 'System')}")
            md_lines.append(f"- **Impact Assessment:** {rk['why_it_matters']}")
            md_lines.append(f"- **Evidence:** {rk['evidence']}")
            if rk.get("recommended_actions"):
                md_lines.append(f"- **Action:** {rk['recommended_actions'][0]}")
    else:
        md_lines.append("No critical or high-priority operational risks identified.")

    md_lines.extend([
        "",
        "## 9. Recommended Next Steps",
        "1. Prioritize resolution of subsystems tagged with Critical or High risk.",
        "2. Review identified recurring error patterns and apply targeted patches or connection pool increases.",
        "3. Configure proactive alerts on time intervals exhibiting volume surges.",
        "4. Ingest subsequent log sessions to establish a robust continuous historical baseline.",
        "",
        "## 10. Data Limitations & Confidence Caveats",
        "- **Log Boundary Limitation:** Health insights reflect exclusively the provided log stream; hardware metrics (e.g. CPU temperature, external ping) are not directly measured.",
        "- **Statistical Baseline:** Anomaly detection confidence increases with larger multi-day sample sets.",
        "- **Provisional Scoring:** When sample sizes are small (< 5 events), metrics reflect immediate sample properties rather than longitudinal system availability."
    ])

    markdown_text = "\n".join(md_lines)

    return {
        "title": "LogHealth System Health & Reliability Report",
        "generated_at": now_str,
        "executive_summary": analytics.get("plain_english_summary", ""),
        "overall_health_score": score_val,
        "status": health_score.get("status", "N/A"),
        "key_statistics": {
            "total_events": total,
            "critical_count": crit,
            "error_count": err,
            "warning_count": warn,
            "info_count": info,
            "components_count": analytics.get("unique_categories", 0)
        },
        "component_health": component_health,
        "anomalies": anomalies,
        "prioritized_risks": risks,
        "historical_comparison": historical,
        "markdown": markdown_text
    }


def analyze_records_in_memory(
    records: List[Dict[str, Any]],
    historical_records: Optional[List[Dict[str, Any]]] = None
) -> Dict[str, Any]:
    """
    Perform complete calculation over an in-memory list of normalized records.
    Returns full LogHealth intelligence payload while preserving all legacy keys.
    """
    total = len(records)
    if total == 0:
        health_score = calculate_health_score(0, {}, {})
        empty_res = {
            "total_errors": 0,
            "total_events": 0,
            "unique_categories": 0,
            "critical_count": 0,
            "error_count": 0,
            "warning_count": 0,
            "info_count": 0,
            "severity_counts": {"Critical": 0, "Error": 0, "Warning": 0, "Info": 0},
            "category_counts": {},
            "recurring_errors": [],
            "recent_errors": [],
            "timeline": [],
            "recommendations": [],
            "health_score": health_score,
            "component_health": [],
            "anomalies": [],
            "prioritized_risks": [],
            "historical_comparison": {"has_baseline": False, "message": "No data present."},
            "plain_english_summary": health_score["plain_english_summary"],
            "chart_data": {
                "categories": {"labels": [], "data": [], "colors": []},
                "severities": {"labels": [], "data": [], "colors": []},
                "timeline": {"labels": [], "data": []}
            }
        }
        empty_res["report"] = generate_health_report(empty_res)
        return empty_res

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
        if SEVERITY_ORDER.get(sev, 0) > SEVERITY_ORDER.get(message_occurrences[key]["severity"], 0):
            message_occurrences[key]["severity"] = sev

    sorted_recurring = sorted(
        message_occurrences.values(),
        key=lambda x: (x["count"], SEVERITY_ORDER.get(x["severity"], 0)),
        reverse=True
    )[:15]

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
    timeline_list = [{"time": k, "count": v} for k, v in sorted_timeline]

    # Component health & risk ranking
    component_health = calculate_component_health(records, sorted_recurring)

    # Anomaly detection
    anomalies = detect_anomalies(records, timeline_list, dict(category_counts))

    # Health score calculation
    health_score = calculate_health_score(
        total_events=total,
        severity_counts=dict(severity_counts),
        component_counts=dict(category_counts),
        anomalies_count=len(anomalies)
    )

    # Prioritized risks
    prioritized_risks = calculate_prioritized_risks(component_health, anomalies, sorted_recurring)

    # Historical comparison
    historical_comp = compare_with_history(records, historical_records)

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

    result = {
        "total_errors": total,
        "total_events": total,
        "unique_categories": len(category_counts),
        "critical_count": severity_counts.get("Critical", 0),
        "error_count": severity_counts.get("Error", 0),
        "warning_count": severity_counts.get("Warning", 0),
        "info_count": severity_counts.get("Info", 0),
        "severity_counts": dict(severity_counts),
        "category_counts": dict(category_counts),
        "recurring_errors": sorted_recurring,
        "recent_errors": recent,
        "timeline": timeline_list,
        "health_score": health_score,
        "component_health": component_health,
        "anomalies": anomalies,
        "prioritized_risks": prioritized_risks,
        "historical_comparison": historical_comp,
        "plain_english_summary": health_score["plain_english_summary"],
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

    result["report"] = generate_health_report(result)
    return result


def compute_database_analytics(db_analytics_raw: Dict[str, Any]) -> Dict[str, Any]:
    """
    Format raw database query results into full analytics response.
    Leverages all stored records if available to guarantee exact mathematical parity.
    """
    all_records = db_analytics_raw.get("all_records")
    if all_records is not None and len(all_records) > 0:
        return analyze_records_in_memory(all_records)

    total = db_analytics_raw.get("total_records", 0)
    category_counts = db_analytics_raw.get("category_counts", {})
    severity_counts = db_analytics_raw.get("severity_counts", {})
    recurring = db_analytics_raw.get("recurring_errors", [])
    timeline = db_analytics_raw.get("timeline", [])
    recent = db_analytics_raw.get("recent_errors", [])

    if total == 0:
        return analyze_records_in_memory([])

    # Compute health score
    health_score = calculate_health_score(total, severity_counts, category_counts, anomalies_count=0)

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

    # Basic component health from raw counts
    component_health = []
    cat_sev_map = db_analytics_raw.get("category_severity_breakdown", {})
    for cat_name, cnt in sorted_cat:
        sevs = cat_sev_map.get(cat_name, {})
        crit = sevs.get("Critical", 0)
        err = sevs.get("Error", 0)
        warn = sevs.get("Warning", 0)
        info = sevs.get("Info", 0)
        fail_rate = round(((crit + err) / max(1, cnt)) * 100.0, 1)
        risk_score = min(100, int((crit * 25) + (err * 8) + (warn * 2)))
        risk_level = "Critical" if risk_score >= 70 or crit >= 2 else ("High" if risk_score >= 40 else ("Medium" if risk_score >= 15 else "Low"))
        component_health.append({
            "component": cat_name,
            "total_events": cnt,
            "critical_count": crit,
            "error_count": err,
            "warning_count": warn,
            "info_count": info,
            "failure_rate": fail_rate,
            "risk_score": risk_score,
            "risk_level": risk_level,
            "evidence": [f"{cnt} events logged", f"Failure rate: {fail_rate}%"],
            "recommended_actions": get_recommendation_for_category(cat_name).get("recommended_solutions", [])[:3]
        })

    anomalies = detect_anomalies([], timeline, category_counts)
    prioritized_risks = calculate_prioritized_risks(component_health, anomalies, recurring)

    res = {
        "total_errors": total,
        "total_events": total,
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
        "health_score": health_score,
        "component_health": component_health,
        "anomalies": anomalies,
        "prioritized_risks": prioritized_risks,
        "historical_comparison": {
            "has_baseline": total > 0,
            "message": f"Based on {total} persistent records currently stored in database.",
            "historical_total": total,
            "delta_volume_percent": 0.0,
            "new_signatures": [],
            "resolved_signatures": []
        },
        "plain_english_summary": health_score["plain_english_summary"],
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

    res["report"] = generate_health_report(res)
    return res
