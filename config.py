"""
Application configuration for ErrorInsight.
Handles environment variables, default settings, and test configurations.
"""

import os
from pathlib import Path
from dotenv import load_dotenv

import tempfile

BASE_DIR = Path(__file__).resolve().parent

# Load .env file if it exists
load_dotenv(BASE_DIR / ".env")

# On Vercel serverless, the filesystem is read-only except /tmp
IS_VERCEL = bool(os.environ.get("VERCEL"))
DEFAULT_DB = str(Path(tempfile.gettempdir()) / "error_insight.db") if IS_VERCEL else str(BASE_DIR / "error_insight.db")


class Config:
    """Base application configuration."""

    SECRET_KEY = os.environ.get("SECRET_KEY", "errorinsight-default-dev-secret-key-2026")
    API_KEY = os.environ.get("API_KEY", "dev-secret-key-12345")
    DATABASE_PATH = os.environ.get("DATABASE_PATH", DEFAULT_DB)
    MAX_CONTENT_LENGTH = int(os.environ.get("MAX_CONTENT_LENGTH", 16 * 1024 * 1024))  # 16 MB
    JSON_SORT_KEYS = False
    TESTING = False
    DEBUG = os.environ.get("FLASK_DEBUG", "0").lower() in ("1", "true", "yes")


class TestingConfig(Config):
    """Configuration for automated test suite."""

    TESTING = True
    DEBUG = False
    DATABASE_PATH = str(BASE_DIR / "test_error_insight.db")
    API_KEY = "test-api-key-9999"


def get_config():
    """Retrieve active configuration based on environment."""
    env = os.environ.get("FLASK_ENV", "development").lower()
    if env == "testing":
        return TestingConfig
    return Config
