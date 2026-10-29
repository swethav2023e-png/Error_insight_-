"""
Classifier service for LogHealth.
Performs rule-based component categorization and severity normalization.
"""

import re
from typing import Optional

CANONICAL_CATEGORIES = {
    "database": "Database",
    "db": "Database",
    "authentication": "Authentication",
    "auth": "Authentication",
    "security": "Authentication",
    "network": "Network",
    "net": "Network",
    "file system": "File System",
    "filesystem": "File System",
    "fs": "File System",
    "memory": "Memory",
    "mem": "Memory",
    "api": "API & Backend",
    "api & backend": "API & Backend",
    "backend": "API & Backend",
    "background jobs": "Background Jobs",
    "worker": "Background Jobs",
    "queue": "Background Jobs",
    "infrastructure": "Infrastructure",
    "infra": "Infrastructure",
    "application": "Application",
    "app": "Application",
}

SEVERITY_MAPPING = {
    "critical": "Critical",
    "fatal": "Critical",
    "emergency": "Critical",
    "alert": "Critical",
    "panic": "Critical",
    "error": "Error",
    "exception": "Error",
    "fail": "Error",
    "failed": "Error",
    "err": "Error",
    "severe": "Error",
    "warning": "Warning",
    "warn": "Warning",
    "info": "Info",
    "information": "Info",
    "notice": "Info",
    "debug": "Info",
    "trace": "Info",
}

# Ordered rules for pattern matching
CATEGORY_RULES = [
    (
        "Database",
        [
            r"\bdatabase\b", r"\bmysql\b", r"\bpostgres(?:ql)?\b", r"\bsqlite\b",
            r"\boracle\b", r"\bsql\b", r"\bquery\b", r"\bdeadlock\b", r"\btransaction\b",
            r"\bconnection pool\b", r"\bforeign key\b", r"\btable\b", r"\bcolumn\b",
            r"\bprisma\b", r"\bhibernate\b", r"\bsqlalchemy\b", r"\bmongodb?\b",
            r"\bquery failed\b", r"\bconnection refused on port (?:3306|5432|1433|27017)\b"
        ]
    ),
    (
        "Authentication",
        [
            r"\bauthentication\b", r"\bunauthorized\b", r"\bforbidden\b", r"\blogin\b",
            r"\bcredential(?:s)?\b", r"\bpassword\b", r"\btoken\b", r"\bjwt\b",
            r"\boauth\b", r"\b401\b", r"\b403\b", r"\baccess denied\b",
            r"\bsession (?:expired|invalid)\b", r"\bcsrf\b", r"\bpermission denied\b"
        ]
    ),
    (
        "Network",
        [
            r"\bnetwork\b", r"\bdns\b", r"\bsocket\b", r"\btimeout\b", r"\bconnection reset\b",
            r"\beconnrefused\b", r"\bunreachable\b", r"\b502\b", r"\b503\b", r"\b504\b",
            r"\bgateway\b", r"\bhandshake\b", r"\bssl\b", r"\btls\b", r"\bconnection refused\b",
            r"\bpacket\b", r"\bbroken pipe\b", r"\bhttp request (?:failed|timed out)\b"
        ]
    ),
    (
        "File System",
        [
            r"\bfile not found\b", r"\bno such file\b", r"\bdirectory\b", r"\bpath\b",
            r"\bdisk\b", r"\bio error\b", r"\benoent\b", r"\benospc\b", r"\bdisk full\b",
            r"\bread-only file system\b", r"\bfile locked\b", r"\bcorrupt file\b",
            r"\bmissing directory\b"
        ]
    ),
    (
        "Memory",
        [
            r"\bout of memory\b", r"\bheap\b", r"\bram\b", r"\bmemory leak\b",
            r"\boom\b", r"\bsegmentation fault\b", r"\bbuffer overflow\b",
            r"\bstack overflow\b", r"\bgarbage collector\b", r"\bmalloc\b",
            r"\bcannot allocate memory\b"
        ]
    ),
    (
        "Background Jobs",
        [
            r"\bcelery\b", r"\brq\b", r"\bsidekiq\b", r"\bcron(?:job)?\b",
            r"\bqueue\b", r"\bworker (?:died|timeout|failed)\b", r"\btask failed\b"
        ]
    ),
    (
        "Infrastructure",
        [
            r"\bdocker\b", r"\bk8s\b", r"\bkubernetes\b", r"\bcontainer\b",
            r"\bec2\b", r"\bnginx\b", r"\bapache\b", r"\bload balancer\b"
        ]
    ),
    (
        "API & Backend",
        [
            r"\brest api\b", r"\bgraphql\b", r"\bendpoint\b", r"\bcontroller\b",
            r"\bhandler\b", r"\broute not found\b", r"\bmethod not allowed\b"
        ]
    )
]


def normalize_severity(raw_severity: Optional[str]) -> str:
    """Normalize arbitrary severity strings to Critical, Error, Warning, or Info."""
    if not raw_severity:
        return "Error"
    cleaned = str(raw_severity).strip().lower()
    return SEVERITY_MAPPING.get(cleaned, "Error")


def classify_category(message: str, explicit_type: Optional[str] = None) -> str:
    """
    Determine category:
    1. If explicit_type is a recognized valid category, preserve it.
    2. If explicit_type is present and non-empty, preserve as custom category.
    3. Otherwise, use rule-based matching against the error message.
    4. Fallback to 'Application'.
    """
    if explicit_type:
        cleaned_type = str(explicit_type).strip().lower()
        if cleaned_type in CANONICAL_CATEGORIES:
            return CANONICAL_CATEGORIES[cleaned_type]
        # Preserve user-supplied explicit category name if clean
        clean_raw = str(explicit_type).strip()
        if clean_raw and len(clean_raw) <= 50:
            return clean_raw.title()

    msg_lower = str(message or "").lower()

    for category_name, patterns in CATEGORY_RULES:
        for pat in patterns:
            if re.search(pat, msg_lower):
                return category_name

    return "Application"

