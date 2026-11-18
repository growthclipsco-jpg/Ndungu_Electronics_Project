"""
SQLite database connection and transaction management.
Implements environment-aware journal mode (WAL local, DELETE PythonAnywhere NFS)
and atomic BEGIN IMMEDIATE transactions.
"""

import sqlite3
import os
from contextlib import contextmanager
from pathlib import Path
from flask import g, current_app


def get_db_path():
    """Returns database file path from Flask config or default."""
    if current_app and "DATABASE_PATH" in current_app.config:
        return current_app.config["DATABASE_PATH"]
    return Path(__file__).resolve().parent.parent / "instance" / "inventory.db"


def get_db():
    """
    Retrieves or establishes database connection for current request context.
    Configures foreign keys, row factory, busy timeout, and journal mode.
    """
    if "db" not in g:
        db_path = get_db_path()
        if isinstance(db_path, Path):
            db_path.parent.mkdir(parents=True, exist_ok=True)
            db_path_str = str(db_path)
        else:
            db_path_str = str(db_path)

        timeout = current_app.config.get("DB_TIMEOUT_SEC", 30.0) if current_app else 30.0
        g.db = sqlite3.connect(
            db_path_str,
            timeout=timeout,
            detect_types=sqlite3.PARSE_DECLTYPES
        )
        g.db.row_factory = sqlite3.Row

        # Essential SQLite Pragmas
        busy_ms = current_app.config.get("DB_BUSY_TIMEOUT_MS", 10000) if current_app else 10000
        journal_mode = current_app.config.get("DB_JOURNAL_MODE", "WAL") if current_app else "WAL"

        cursor = g.db.cursor()
        cursor.execute("PRAGMA foreign_keys = ON;")
        cursor.execute(f"PRAGMA busy_timeout = {busy_ms};")
        if db_path_str != ":memory:":
            cursor.execute(f"PRAGMA journal_mode = {journal_mode};")
        cursor.close()

    return g.db


def close_db(e=None):
    """Closes database connection at the end of request."""
    db = g.pop("db", None)
    if db is not None:
        db.close()


@contextmanager
def transaction(db=None):
    """
    Context manager for atomic write operations.
    Executes BEGIN IMMEDIATE to lock writer exclusively and commits on clean exit,
    or rolls back on unhandled exceptions.
    """
    conn = db if db is not None else get_db()
    # In SQLite, BEGIN IMMEDIATE acquires a reserved lock immediately
    conn.execute("BEGIN IMMEDIATE")
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise


def init_db(app=None):
    """Executes schema.sql DDL to create normalized tables."""
    schema_path = Path(__file__).resolve().parent / "schema.sql"
    with open(schema_path, "r", encoding="utf-8") as f:
        schema_sql = f.read()

    if app:
        with app.app_context():
            db = get_db()
            db.executescript(schema_sql)
            db.commit()
    else:
        db = get_db()
        db.executescript(schema_sql)
        db.commit()
