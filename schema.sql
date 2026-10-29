-- Schema for ErrorInsight
-- Compatible with SQLite and adaptable to PostgreSQL

CREATE TABLE IF NOT EXISTS error_logs (
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

-- Indexes for fast query filtering and sorting
CREATE INDEX IF NOT EXISTS idx_error_logs_timestamp ON error_logs(timestamp);
CREATE INDEX IF NOT EXISTS idx_error_logs_category ON error_logs(category);
CREATE INDEX IF NOT EXISTS idx_error_logs_severity ON error_logs(severity);
CREATE INDEX IF NOT EXISTS idx_error_logs_source ON error_logs(source_name);
CREATE INDEX IF NOT EXISTS idx_error_logs_hash ON error_logs(idempotency_hash);
