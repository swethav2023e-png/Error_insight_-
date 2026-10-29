"""
Database abstraction layer and SQLite implementation for LogHealth.
Enables pluggable backend architecture (SQLite for local dev, PostgreSQL for production).
"""

from abc import ABC, abstractmethod
from datetime import datetime
from pathlib import Path
import hashlib
import logging
import sqlite3
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


class DatabaseError(Exception):
    """Custom exception for database-related operational errors."""
    pass


class DatabaseManager(ABC):
    """Abstract interface defining the persistence contract."""

    @abstractmethod
    def init_db(self) -> None:
        """Initialize database schema, tables, and indexes."""
        pass

    @abstractmethod
    def insert_records(self, records: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Insert multiple normalized records with idempotency and duplicate checking.
        Returns summary: { 'accepted': int, 'rejected': int, 'duplicates': int, 'errors': list }
        """
        pass

    @abstractmethod
    def get_records(
        self,
        page: int = 1,
        limit: int = 50,
        severity: Optional[str] = None,
        category: Optional[str] = None,
        source: Optional[str] = None,
        search: Optional[str] = None,
        sort_by: str = "timestamp",
        sort_dir: str = "desc"
    ) -> Dict[str, Any]:
        """Query stored records with filtering, searching, sorting, and pagination."""
        pass

    @abstractmethod
    def get_record_by_id(self, record_id: int) -> Optional[Dict[str, Any]]:
        """Retrieve a single error record by primary key."""
        pass

    @abstractmethod
    def get_total_count(self) -> int:
        """Get the total count of stored error records."""
        pass

    @abstractmethod
    def get_all_records(self, limit: int = 5000) -> List[Dict[str, Any]]:
        """Retrieve stored records up to limit for deep analytical processing."""
        pass

    @abstractmethod
    def get_analytics_data(self) -> Dict[str, Any]:
        """Fetch raw aggregated counts for category, severity, and recurring errors."""
        pass

    @abstractmethod
    def check_health(self) -> Dict[str, Any]:
        """Verify database connectivity and health."""
        pass

    @abstractmethod
    def clear_all(self) -> int:
        """Clear all records from error_logs (useful for testing and reset)."""
        pass



class SQLiteManager(DatabaseManager):
    """SQLite implementation of the DatabaseManager interface."""

    def __init__(self, db_path: str):
        self.db_path = Path(db_path).resolve()
        # Ensure parent directory exists
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

    def _get_connection(self) -> sqlite3.Connection:
        """Return a SQLite connection with row_factory enabled and busy timeout."""
        try:
            conn = sqlite3.connect(str(self.db_path), timeout=15)
            conn.row_factory = sqlite3.Row
            # Enable foreign keys and WAL mode for better concurrency
            conn.execute("PRAGMA foreign_keys = ON;")
            return conn
        except sqlite3.Error as exc:
            logger.error("Failed to connect to SQLite at %s: %s", self.db_path, exc)
            raise DatabaseError(f"Database connection error: {exc}") from exc

    def init_db(self) -> None:
        """Initialize database tables, performing seamless migrations if old columns exist."""
        schema_file = Path(__file__).resolve().parent / "schema.sql"
        try:
            with self._get_connection() as conn:
                # Check if table already exists
                table_check = conn.execute(
                    "SELECT name FROM sqlite_master WHERE type='table' AND name='error_logs';"
                ).fetchone()

                if table_check:
                    # Table exists; verify columns
                    cols = [row["name"] for row in conn.execute("PRAGMA table_info(error_logs)").fetchall()]
                    if "type" in cols:
                        # Migrate legacy table schema cleanly removing old type column
                        conn.execute("""
                            CREATE TABLE error_logs_v2 (
                                id INTEGER PRIMARY KEY AUTOINCREMENT,
                                source_id TEXT,
                                source_name TEXT DEFAULT 'upload',
                                timestamp TEXT NOT NULL,
                                category TEXT NOT NULL,
                                message TEXT NOT NULL,
                                severity TEXT NOT NULL,
                                created_at TEXT NOT NULL,
                                idempotency_hash TEXT UNIQUE
                            );
                        """)
                        cat_expr = "COALESCE(category, type, 'Application')" if "category" in cols else "COALESCE(type, 'Application')"
                        src_expr = "COALESCE(source_name, 'upload')" if "source_name" in cols else "'upload'"
                        hash_expr = "idempotency_hash" if "idempotency_hash" in cols else "NULL"
                        conn.execute(f"""
                            INSERT INTO error_logs_v2 (id, source_id, source_name, timestamp, category, message, severity, created_at, idempotency_hash)
                            SELECT id, source_id, {src_expr}, timestamp, {cat_expr}, message, severity, created_at, {hash_expr}
                            FROM error_logs;
                        """)
                        conn.execute("DROP TABLE error_logs;")
                        conn.execute("ALTER TABLE error_logs_v2 RENAME TO error_logs;")
                    else:
                        if "category" not in cols:
                            conn.execute("ALTER TABLE error_logs ADD COLUMN category TEXT DEFAULT 'Application';")
                        if "source_name" not in cols:
                            conn.execute("ALTER TABLE error_logs ADD COLUMN source_name TEXT DEFAULT 'upload';")
                        if "idempotency_hash" not in cols:
                            conn.execute("ALTER TABLE error_logs ADD COLUMN idempotency_hash TEXT;")

                # Execute schema.sql for table creation and indexes
                with open(schema_file, "r", encoding="utf-8") as f:
                    schema_sql = f.read()
                conn.executescript(schema_sql)

            logger.info("Database initialized successfully at %s", self.db_path)
        except (sqlite3.Error, OSError) as exc:
            logger.error("Failed to initialize SQLite database: %s", exc)
            raise DatabaseError(f"Database initialization failed: {exc}") from exc

    @staticmethod
    def compute_idempotency_hash(source_name: str, source_id: Optional[str], timestamp: str, message: str) -> str:
        """
        Generate a unique idempotency hash per occurrence.
        If source_id is present, it binds to (source_name, source_id, timestamp, message).
        If source_id is absent, it uses (source_name, timestamp, message).
        This preserves legitimate duplicate messages that occur at distinct timestamps,
        while safely discarding accidental replay of the exact same event.
        """
        raw = f"{source_name or ''}|{source_id or ''}|{timestamp or ''}|{message or ''}"
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()

    def insert_records(self, records: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Insert records with idempotency checking and transaction isolation."""
        if not records:
            return {"accepted": 0, "rejected": 0, "duplicates": 0, "errors": []}

        accepted = 0
        duplicates = 0
        rejected = 0
        error_details = []
        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        conn = self._get_connection()
        try:
            with conn:
                cursor = conn.cursor()
                for idx, item in enumerate(records):
                    try:
                        timestamp = str(item.get("timestamp") or now_str).strip()
                        category = str(item.get("category") or "Application").strip()
                        message = str(item.get("message") or "").strip()
                        severity = str(item.get("severity") or "Error").strip()
                        source_id = str(item.get("source_id") or "") if item.get("source_id") is not None else None
                        source_name = str(item.get("source_name") or "upload").strip()

                        if not message:
                            rejected += 1
                            error_details.append(f"Record #{idx + 1}: Missing error message.")
                            continue

                        # Check or calculate idempotency hash
                        idempotency_hash = item.get("idempotency_hash")
                        if not idempotency_hash:
                            idempotency_hash = self.compute_idempotency_hash(
                                source_name, source_id, timestamp, message
                            )

                        cursor.execute("""
                            INSERT INTO error_logs (
                                source_id, source_name, timestamp, category,
                                message, severity, created_at, idempotency_hash
                            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                        """, (
                            source_id, source_name, timestamp, category,
                            message, severity, now_str, idempotency_hash
                        ))
                        accepted += 1
                    except sqlite3.IntegrityError as ie:
                        if "UNIQUE" in str(ie):
                            # Unique constraint on idempotency_hash triggered - duplicate import
                            duplicates += 1
                        else:
                            rejected += 1
                            error_details.append(f"Record #{idx + 1}: Integrity error: {ie}")
                    except Exception as err:
                        rejected += 1
                        error_details.append(f"Record #{idx + 1}: {str(err)}")
        except sqlite3.Error as exc:
            logger.error("Transaction failed during record insert: %s", exc)
            raise DatabaseError(f"Database write failure: {exc}") from exc
        finally:
            conn.close()

        return {
            "accepted": accepted,
            "rejected": rejected,
            "duplicates": duplicates,
            "errors": error_details,
            "total_processed": len(records)
        }

    def get_records(
        self,
        page: int = 1,
        limit: int = 50,
        severity: Optional[str] = None,
        category: Optional[str] = None,
        source: Optional[str] = None,
        search: Optional[str] = None,
        sort_by: str = "timestamp",
        sort_dir: str = "desc"
    ) -> Dict[str, Any]:
        """Fetch records with parameterized filters and pagination."""
        page = max(1, page)
        limit = min(max(1, limit), 500)
        offset = (page - 1) * limit

        allowed_sort_cols = {
            "id": "id",
            "timestamp": "timestamp",
            "category": "category",
            "severity": "severity",
            "source_name": "source_name",
            "created_at": "created_at"
        }
        order_col = allowed_sort_cols.get(sort_by.lower(), "timestamp")
        order_direction = "ASC" if sort_dir.lower() == "asc" else "DESC"

        where_clauses = []
        params: List[Any] = []

        if severity:
            where_clauses.append("LOWER(severity) = LOWER(?)")
            params.append(severity.strip())

        if category:
            where_clauses.append("LOWER(category) = LOWER(?)")
            params.append(category.strip())

        if source:
            where_clauses.append("LOWER(source_name) LIKE LOWER(?)")
            params.append(f"%{source.strip()}%")

        if search:
            where_clauses.append("(LOWER(message) LIKE LOWER(?) OR LOWER(source_id) LIKE LOWER(?))")
            term = f"%{search.strip()}%"
            params.extend([term, term])

        where_sql = ("WHERE " + " AND ".join(where_clauses)) if where_clauses else ""

        count_query = f"SELECT COUNT(*) FROM error_logs {where_sql}"
        data_query = f"""
            SELECT id, source_id, source_name, timestamp, category, message, severity, created_at
            FROM error_logs
            {where_sql}
            ORDER BY {order_col} {order_direction}, id {order_direction}
            LIMIT ? OFFSET ?
        """

        try:
            with self._get_connection() as conn:
                total_filtered = conn.execute(count_query, params).fetchone()[0]
                data_params = params + [limit, offset]
                rows = conn.execute(data_query, data_params).fetchall()
                records = [dict(r) for r in rows]

            total_pages = (total_filtered + limit - 1) // limit if total_filtered > 0 else 1

            return {
                "records": records,
                "pagination": {
                    "page": page,
                    "limit": limit,
                    "total_records": total_filtered,
                    "total_pages": total_pages,
                    "has_next": page < total_pages,
                    "has_prev": page > 1
                }
            }
        except sqlite3.Error as exc:
            logger.error("Failed to query history records: %s", exc)
            raise DatabaseError(f"Database query failure: {exc}") from exc

    def get_record_by_id(self, record_id: int) -> Optional[Dict[str, Any]]:
        """Retrieve single error by ID."""
        try:
            with self._get_connection() as conn:
                row = conn.execute(
                    "SELECT id, source_id, source_name, timestamp, category, message, severity, created_at FROM error_logs WHERE id = ?",
                    (record_id,)
                ).fetchone()
                return dict(row) if row else None
        except sqlite3.Error as exc:
            logger.error("Failed to fetch record id %s: %s", record_id, exc)
            raise DatabaseError(f"Database query failure: {exc}") from exc

    def get_total_count(self) -> int:
        """Return total row count."""
        try:
            with self._get_connection() as conn:
                return conn.execute("SELECT COUNT(*) FROM error_logs").fetchone()[0]
        except sqlite3.Error as exc:
            logger.error("Failed to count error_logs: %s", exc)
            raise DatabaseError(f"Database count failure: {exc}") from exc

    def get_all_records(self, limit: int = 5000) -> List[Dict[str, Any]]:
        """Retrieve stored records up to limit for deep analytical processing."""
        try:
            with self._get_connection() as conn:
                rows = conn.execute(
                    "SELECT id, source_id, source_name, timestamp, category, message, severity, created_at "
                    "FROM error_logs ORDER BY timestamp ASC, id ASC LIMIT ?",
                    (limit,)
                ).fetchall()
                return [dict(r) for r in rows]
        except sqlite3.Error as exc:
            logger.error("Failed to fetch all records: %s", exc)
            raise DatabaseError(f"Database query failure: {exc}") from exc

    def get_analytics_data(self) -> Dict[str, Any]:
        """Aggregate stored records for analytics dashboard."""
        try:
            with self._get_connection() as conn:
                # Severity distribution
                sev_rows = conn.execute(
                    "SELECT severity, COUNT(*) as count FROM error_logs GROUP BY severity ORDER BY count DESC"
                ).fetchall()
                severity_counts = {r["severity"]: r["count"] for r in sev_rows}

                # Category distribution
                cat_rows = conn.execute(
                    "SELECT category, COUNT(*) as count FROM error_logs GROUP BY category ORDER BY count DESC"
                ).fetchall()
                category_counts = {r["category"]: r["count"] for r in cat_rows}

                # Category and severity breakdown for component risk ranking
                cat_sev_rows = conn.execute(
                    "SELECT category, severity, COUNT(*) as count FROM error_logs GROUP BY category, severity"
                ).fetchall()
                category_severity_breakdown = {}
                for r in cat_sev_rows:
                    cat = r["category"]
                    if cat not in category_severity_breakdown:
                        category_severity_breakdown[cat] = {}
                    category_severity_breakdown[cat][r["severity"]] = r["count"]

                # Recurring error messages (grouping by exact message)
                recur_rows = conn.execute("""
                    SELECT message, category, severity, COUNT(*) as count, MAX(timestamp) as last_seen
                    FROM error_logs
                    GROUP BY message, category
                    ORDER BY count DESC, last_seen DESC
                    LIMIT 15
                """).fetchall()
                recurring_messages = [dict(r) for r in recur_rows]

                # Timestamp series (hourly/daily trend)
                trend_rows = conn.execute("""
                    SELECT SUBSTR(timestamp, 1, 13) as time_bucket, COUNT(*) as count
                    FROM error_logs
                    WHERE timestamp IS NOT NULL AND LENGTH(timestamp) >= 10
                    GROUP BY time_bucket
                    ORDER BY time_bucket ASC
                    LIMIT 50
                """).fetchall()
                timeline = [{"time": r["time_bucket"], "count": r["count"]} for r in trend_rows]

                # Recent errors
                recent_rows = conn.execute("""
                    SELECT id, source_id, source_name, timestamp, category, message, severity
                    FROM error_logs
                    ORDER BY id DESC
                    LIMIT 15
                """).fetchall()
                recent_records = [dict(r) for r in recent_rows]

                # Full records list for consistent analytical processing
                all_rows = conn.execute(
                    "SELECT id, source_id, source_name, timestamp, category, message, severity, created_at "
                    "FROM error_logs ORDER BY timestamp ASC, id ASC LIMIT 5000"
                ).fetchall()
                all_records = [dict(r) for r in all_rows]

                total_count = conn.execute("SELECT COUNT(*) FROM error_logs").fetchone()[0]

            return {
                "total_records": total_count,
                "unique_categories": len(category_counts),
                "severity_counts": severity_counts,
                "category_counts": category_counts,
                "category_severity_breakdown": category_severity_breakdown,
                "recurring_errors": recurring_messages,
                "timeline": timeline,
                "recent_errors": recent_records,
                "all_records": all_records
            }
        except sqlite3.Error as exc:
            logger.error("Failed to compute analytics: %s", exc)
            raise DatabaseError(f"Database analytics query failure: {exc}") from exc


    def check_health(self) -> Dict[str, Any]:
        """Check SQLite connection and file size."""
        try:
            with self._get_connection() as conn:
                count = conn.execute("SELECT COUNT(*) FROM error_logs").fetchone()[0]
            size_bytes = self.db_path.stat().st_size if self.db_path.exists() else 0
            return {
                "connected": True,
                "engine": "SQLite",
                "database_file": self.db_path.name,
                "file_size_bytes": size_bytes,
                "record_count": count
            }
        except Exception as exc:
            return {
                "connected": False,
                "engine": "SQLite",
                "error": str(exc),
                "record_count": 0
            }

    def clear_all(self) -> int:
        """Clear all records from error_logs."""
        try:
            with self._get_connection() as conn:
                deleted = conn.execute("DELETE FROM error_logs").rowcount
            return deleted
        except sqlite3.Error as exc:
            logger.error("Failed to clear error_logs: %s", exc)
            raise DatabaseError(f"Database clear failure: {exc}") from exc


_db_instance: Optional[DatabaseManager] = None


def get_db(db_path: Optional[str] = None) -> DatabaseManager:
    """Singleton-style or on-demand factory for DatabaseManager."""
    global _db_instance
    if db_path is not None:
        return SQLiteManager(db_path)

    # Check if inside Flask request/app context with configured DATABASE_PATH
    try:
        from flask import current_app
        if current_app and "DATABASE_PATH" in current_app.config:
            return SQLiteManager(current_app.config["DATABASE_PATH"])
    except Exception:
        pass

    if _db_instance is None:
        from config import get_config
        cfg = get_config()
        _db_instance = SQLiteManager(cfg.DATABASE_PATH)
    return _db_instance


def set_db(manager: DatabaseManager) -> None:
    """Set the active database manager (used in testing)."""
    global _db_instance
    _db_instance = manager
