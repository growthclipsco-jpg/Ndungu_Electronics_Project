"""
Health check blueprint for PythonAnywhere monitoring and test suites.
"""

from flask import Blueprint, jsonify
from app.db import get_db

health_bp = Blueprint("health", __name__)


@health_bp.route("/healthz", methods=["GET"])
def health_check():
    """
    Returns 200 OK with database connectivity status.
    Used by PythonAnywhere reload verification and TC-21.
    """
    db_status = "ok"
    try:
        db = get_db()
        cursor = db.cursor()
        cursor.execute("SELECT 1")
        cursor.fetchone()
    except Exception as exc:
        db_status = f"error: {str(exc)}"

    code = 200 if db_status == "ok" else 500
    return jsonify({
        "status": "ok" if code == 200 else "degraded",
        "db": db_status
    }), code
