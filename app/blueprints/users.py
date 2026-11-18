"""
Users Blueprint for Ndungu Electronics IMS.
Renders S-10 Users & Unified Audit Trail.
Handles owner-issued 24-hour single-use invite tokens, attendant deactivation,
account lockout reset, and security audit event logs.
"""

from flask import (
    Blueprint, render_template, request, redirect, url_for,
    flash, jsonify, session
)
from app.blueprints.auth import owner_required
from app.services.auth_service import AuthService
from app.db import get_db, transaction

users_bp = Blueprint("users", __name__, url_prefix="/users")


@users_bp.route("/", methods=["GET"])
@owner_required
def index():
    """Renders S-10 Users & Audit Trail dashboard."""
    conn = get_db()
    cursor = conn.cursor()

    # Fetch users
    cursor.execute("""
        SELECT user_id, username, full_name, role, is_active,
               failed_login_attempts, locked_until, created_at, updated_at
        FROM users
        ORDER BY user_id ASC
    """)
    users = [dict(r) for r in cursor.fetchall()]

    # Fetch recent active invite tokens
    cursor.execute("""
        SELECT token_id, role, created_at, expires_at, used_at
        FROM invite_tokens
        ORDER BY token_id DESC
        LIMIT 10
    """)
    tokens = [dict(r) for r in cursor.fetchall()]

    # Fetch unified audit trail: auth_events + stock_movements
    cursor.execute("""
        SELECT event_id, event_type, username, ip_address, created_at,
               'auth' AS log_category, '' AS details
        FROM auth_events
        ORDER BY event_id DESC
        LIMIT 30
    """)
    auth_events = [dict(r) for r in cursor.fetchall()]

    cursor.execute("""
        SELECT movement_id AS event_id, movement_type AS event_type,
               username_snapshot AS username, '' AS ip_address,
               created_at, 'stock' AS log_category,
               (sku_snapshot || ' (' || CASE WHEN qty_delta > 0 THEN '+' ELSE '' END || qty_delta || ')') AS details
        FROM stock_movements
        ORDER BY movement_id DESC
        LIMIT 30
    """)
    stock_events = [dict(r) for r in cursor.fetchall()]

    # Merge and sort by created_at descending
    all_events = sorted(auth_events + stock_events, key=lambda e: e["created_at"], reverse=True)[:40]

    return render_template(
        "users.html",
        users=users,
        tokens=tokens,
        events=all_events
    )


@users_bp.route("/invite", methods=["POST"])
@owner_required
def create_invite():
    """Mints an Owner-issued 24-hour single-use invite link for new attendants."""
    role = request.form.get("role", "attendant").strip()
    if role not in ("attendant", "owner"):
        role = "attendant"

    user = AuthService.get_user_by_id(session["user_id"])
    token, err = AuthService.create_invite_token(user.user_id, role=role)

    if err:
        flash(err, "error")
    else:
        invite_url = request.host_url.rstrip("/") + url_for("auth.register", token=token)
        flash(f"Single-use invite link generated: {invite_url}", "success")

    return redirect(url_for("users.index"))


@users_bp.route("/<int:user_id>/toggle-status", methods=["POST"])
@owner_required
def toggle_user_status(user_id):
    """Enables or disables an attendant account."""
    curr_user_id = session.get("user_id")
    if user_id == curr_user_id:
        flash("You cannot deactivate your own administrative account.", "error")
        return redirect(url_for("users.index"))

    with transaction() as conn:
        conn.execute("""
            UPDATE users
            SET is_active = CASE WHEN is_active = 1 THEN 0 ELSE 1 END,
                updated_at = datetime('now', 'localtime')
            WHERE user_id = ?
        """, (user_id,))
    flash("User account active status toggled.", "success")
    return redirect(url_for("users.index"))


@users_bp.route("/<int:user_id>/unlock", methods=["POST"])
@owner_required
def unlock_user(user_id):
    """Resets brute-force failed attempts and clears lockout timestamp."""
    with transaction() as conn:
        conn.execute("""
            UPDATE users
            SET failed_login_attempts = 0,
                locked_until = NULL,
                updated_at = datetime('now', 'localtime')
            WHERE user_id = ?
        """, (user_id,))
    flash("Account lockout reset and failed attempt counter cleared.", "success")
    return redirect(url_for("users.index"))
