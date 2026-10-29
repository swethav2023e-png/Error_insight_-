"""Database package for ErrorInsight."""
from .db import DatabaseManager, SQLiteManager, DatabaseError, get_db, set_db

__all__ = ["DatabaseManager", "SQLiteManager", "DatabaseError", "get_db", "set_db"]
