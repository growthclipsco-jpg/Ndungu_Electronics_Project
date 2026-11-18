"""
Authentication blueprint handling login, logout, first-run bootstrap,
and 24-hour single-use invite token sign-up.
"""

from functools import wraps
from flask import (
    Blueprint, render_template, request, redirect, url_for, session,
    flash, jsonify, current_app, abort
)
from app.services.auth_service import AuthService

auth_bp = Blueprint("auth", __name__)


def login_required(view):
    """Decorator requiring authenticated session."""
    @wraps(view)
    def wrapped_view(**kwargs):
        if "user_id" not in session:
            return redirect(url_for("auth.login", next=request.path))
        return view(**kwargs)
    return wrapped_view


def owner_required(view):
    """Decorator requiring Owner role (returns HTTP 403 for attendants)."""
    @wraps(view)
    def wrapped_view(**kwargs):
        if "user_id" not in session:
            return redirect(url_for("auth.login", next=request.path))
        if session.get("role") != "owner":
            abort(403)
        return view(**kwargs)
    return wrapped_view


@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    """Terminal login view enforcing 15-minute brute-force lockout."""
    # If already logged in, redirect to inventory or pos
    if "user_id" in session:
        return redirect(url_for("inventory.index") if "inventory" in current_app.blueprints else "/")

    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        ip_addr = request.remote_addr or ""

        user, err = AuthService.authenticate(username, password, ip_addr)
        if err:
            status_code = 429 if "locked" in err.lower() else 401
            # If AJAX / JSON request
            if request.is_json or request.headers.get("X-Requested-With") == "XMLHttpRequest":
                return jsonify({"success": False, "error": err}), status_code
            flash(err, "error")
            return render_template("login.html", username=username), status_code

        # Login successful - preserve CSRF token
        csrf_tok = session.get("_csrf_token")
        session.clear()
        if csrf_tok:
            session["_csrf_token"] = csrf_tok
        session["user_id"] = user.user_id
        session["username"] = user.username
        session["full_name"] = user.full_name
        session["role"] = user.role

        next_url = request.args.get("next")
        if not next_url or not next_url.startswith("/"):
            next_url = url_for("inventory.index") if "inventory" in current_app.blueprints else "/"

        if request.is_json or request.headers.get("X-Requested-With") == "XMLHttpRequest":
            return jsonify({"success": True, "redirect": next_url}), 200

        return redirect(next_url)

    return render_template("login.html")


@auth_bp.route("/logout", methods=["GET", "POST"])
def logout():
    """Logs out user and destroys session."""
    user_id = session.get("user_id")
    username = session.get("username")
    if user_id and username:
        AuthService.log_logout(user_id, username, request.remote_addr or "")
    session.clear()
    flash("You have been signed out.", "info")
    return redirect(url_for("auth.login"))


@auth_bp.route("/register", methods=["GET", "POST"])
def register():
    """
    Registration router:
    - If users == 0: First-Run Shop Owner Setup.
    - If ?token=... present: Attendant registration via single-use 24-hr invite.
    - If uninvited and users > 0: Redirects to /login.
    """
    user_count = AuthService.get_user_count()
    token = request.args.get("token", "").strip()

    if user_count > 0 and not token and request.method == "GET":
        flash("Public registration is disabled. You must have an owner invite link to sign up.", "warning")
        return redirect(url_for("auth.login"))

    is_first_run = (user_count == 0)

    if request.method == "POST":
        token_post = request.form.get("token", "").strip() or token
        username = request.form.get("username", "").strip()
        full_name = request.form.get("full_name", "").strip()
        password = request.form.get("password", "")
        confirm_password = request.form.get("confirm_password", "")
        ip_addr = request.remote_addr or ""

        if password != confirm_password:
            flash("Passwords do not match.", "error")
            return render_template("register.html", is_first_run=is_first_run, token=token_post, username=username, full_name=full_name), 400

        if is_first_run:
            user, err = AuthService.register_first_owner(username, password, full_name, ip_addr)
        else:
            user, err = AuthService.register_via_invite_token(token_post, username, password, full_name, ip_addr)

        if err:
            flash(err, "error")
            return render_template("register.html", is_first_run=is_first_run, token=token_post, username=username, full_name=full_name), 400

        flash("Account created successfully! Please sign in with your credentials.", "success")
        return redirect(url_for("auth.login"))

    return render_template("register.html", is_first_run=is_first_run, token=token)
