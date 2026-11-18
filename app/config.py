"""
Application configuration for local dev, pytest, and PythonAnywhere.
Anchored strictly via BASE_DIR to prevent CWD mismatches.
"""

import os
from pathlib import Path
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent

# Load .env if present
load_dotenv(BASE_DIR / ".env")


class Config:
    """Base configuration."""
    SECRET_KEY = os.environ.get("SECRET_KEY", "ndungu-ims-insecure-dev-key-change-in-prod-64chars-min-length-xyz")
    DATABASE_PATH = BASE_DIR / "instance" / "inventory.db"
    DB_JOURNAL_MODE = os.environ.get("DB_JOURNAL_MODE", "WAL")
    DB_BUSY_TIMEOUT_MS = int(os.environ.get("DB_BUSY_TIMEOUT_MS", "10000"))
    DB_TIMEOUT_SEC = float(os.environ.get("DB_TIMEOUT_SEC", "30.0"))
    TESTING = False
    DEBUG = False
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"
    SESSION_COOKIE_SECURE = False  # Set True in production HTTPS
    PERMANENT_SESSION_LIFETIME_HOURS = 12


class DevelopmentConfig(Config):
    """Local development configuration."""
    DEBUG = True
    DB_JOURNAL_MODE = "WAL"


class TestingConfig(Config):
    """Test environment configuration (dedicated isolated test SQLite)."""
    TESTING = True
    DEBUG = False
    DATABASE_PATH = BASE_DIR / "instance" / "test_inventory.db"
    DB_JOURNAL_MODE = "WAL"
    SECRET_KEY = "test-secret-key-not-for-production-use"


class PythonAnywhereConfig(Config):
    """
    Production configuration for PythonAnywhere free beginner tier.
    Enforces DELETE journal mode (never WAL on NFS filesystem).
    """
    DEBUG = False
    DB_JOURNAL_MODE = "DELETE"
    SESSION_COOKIE_SECURE = True


CONFIG_MAP = {
    "development": DevelopmentConfig,
    "testing": TestingConfig,
    "production": PythonAnywhereConfig,
    "pythonanywhere": PythonAnywhereConfig,
}


def get_config(env_name: str = None) -> type[Config]:
    """Resolves configuration class based on environment variable."""
    if not env_name:
        env_name = os.environ.get("FLASK_ENV", "development").lower()
    return CONFIG_MAP.get(env_name, DevelopmentConfig)
