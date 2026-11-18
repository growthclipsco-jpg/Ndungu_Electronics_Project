"""
Application factory for Ndungu Electronics Inventory Management System.
Configures security headers, CSRF protection, error handling, and database teardown.
"""

import hmac
import os
import secrets
from pathlib import Path
from flask import Flask, request, session, abort, render_template, jsonify, g
from app.config import get_config
from app.db import close_db, init_db
from app.domain.money import format_kes, to_kes
from app.services.auth_service import AuthService


def generate_csrf_token():
    """Generates or retrieves CSRF token bound to current session."""
    if "_csrf_token" not in session:
        session["_csrf_token"] = secrets.token_hex(32)
    return session["_csrf_token"]


def validate_csrf():
    """Validates CSRF token on mutating request methods."""
    if request.method in ("POST", "PUT", "PATCH", "DELETE"):
        # Allow disabling CSRF in testing if configured
        if getattr(g, "_testing_disable_csrf", False):
            return

        expected = session.get("_csrf_token")
        sent = request.form.get("csrf_token") or request.headers.get("X-CSRFToken") or request.headers.get("X-CSRF-Token")

        if not expected or not sent or not hmac.compare_digest(expected, sent):
            abort(400, description="Invalid or expired CSRF security token. Please refresh the form.")


def create_app(config_class=None):
    """Factory function initializing Flask application."""
    app = Flask(__name__, instance_relative_config=True)

    if config_class is None:
        config_class = get_config()
    app.config.from_object(config_class)

    # Ensure instance directory exists
    instance_dir = Path(app.instance_path)
    instance_dir.mkdir(parents=True, exist_ok=True)

    # Register DB teardown
    app.teardown_appcontext(close_db)

    # CSRF protection hook
    @app.before_request
    def check_csrf():
        validate_csrf()

    # Security Headers hook
    @app.after_request
    def set_security_headers(response):
        # Strict Content Security Policy
        csp = (
            "default-src 'self'; "
            "script-src 'self' 'unsafe-inline' https://cdn.tailwindcss.com; "
            "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; "
            "font-src 'self' https://fonts.gstatic.com; "
            "img-src 'self' data:; "
            "connect-src 'self';"
        )
        response.headers["Content-Security-Policy"] = csp
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        
        # Disable caching on authenticated / operational routes
        if "user_id" in session:
            response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
            response.headers["Pragma"] = "no-cache"
            response.headers["Expires"] = "0"
            
        return response

    # Global Template Context Processor
    @app.context_processor
    def inject_helpers():
        user = None
        if "user_id" in session:
            user = AuthService.get_user_by_id(session["user_id"])
        return {
            "csrf_token": generate_csrf_token,
            "format_kes": format_kes,
            "to_kes": to_kes,
            "current_user": user
        }

    # Custom Error Handlers
    @app.errorhandler(400)
    def handle_bad_request(err):
        msg = getattr(err, "description", "Bad Request")
        if request.is_json or request.headers.get("X-Requested-With") == "XMLHttpRequest":
            return jsonify({"error": msg, "code": 400}), 400
        return render_template("error.html", code=400, title="Invalid Request", message=msg), 400

    @app.errorhandler(403)
    def handle_forbidden(err):
        msg = "You do not have administrative permission to access this resource."
        if request.is_json or request.headers.get("X-Requested-With") == "XMLHttpRequest":
            return jsonify({"error": msg, "code": 403}), 403
        return render_template("error.html", code=403, title="Access Forbidden", message=msg), 403

    @app.errorhandler(404)
    def handle_not_found(err):
        msg = "The requested page or resource could not be found."
        if request.is_json or request.headers.get("X-Requested-With") == "XMLHttpRequest":
            return jsonify({"error": msg, "code": 404}), 404
        return render_template("error.html", code=404, title="Page Not Found", message=msg), 404

    @app.errorhandler(405)
    def handle_method_not_allowed(err):
        msg = "HTTP method not allowed on this endpoint."
        if request.is_json or request.headers.get("X-Requested-With") == "XMLHttpRequest":
            return jsonify({"error": msg, "code": 405}), 405
        return render_template("error.html", code=405, title="Method Not Allowed", message=msg), 405

    @app.errorhandler(429)
    def handle_too_many_requests(err):
        msg = getattr(err, "description", "Too many requests. Account temporarily locked.")
        if request.is_json or request.headers.get("X-Requested-With") == "XMLHttpRequest":
            return jsonify({"error": msg, "code": 429}), 429
        return render_template("error.html", code=429, title="Terminal Locked", message=msg), 429

    @app.errorhandler(500)
    def handle_internal_error(err):
        msg = "An unexpected server error occurred. Transaction was rolled back safely."
        if request.is_json or request.headers.get("X-Requested-With") == "XMLHttpRequest":
            return jsonify({"error": msg, "code": 500}), 500
        return render_template("error.html", code=500, title="Server Error", message=msg), 500

    # Register Blueprints
    from app.blueprints.health import health_bp
    from app.blueprints.auth import auth_bp
    from app.blueprints.inventory import inventory_bp
    from app.blueprints.pos import pos_bp
    from app.blueprints.sales import sales_bp
    from app.blueprints.promotions import promotions_bp
    from app.blueprints.reports import reports_bp
    from app.blueprints.users import users_bp

    app.register_blueprint(health_bp)
    app.register_blueprint(auth_bp)
    app.register_blueprint(inventory_bp)
    app.register_blueprint(pos_bp)
    app.register_blueprint(sales_bp)
    app.register_blueprint(promotions_bp)
    app.register_blueprint(reports_bp)
    app.register_blueprint(users_bp)

    # Root redirect
    @app.route("/")
    def index():
        if "user_id" in session:
            from flask import redirect, url_for
            return redirect(url_for("inventory.index"))
        from flask import redirect, url_for
        return redirect(url_for("auth.login"))

    # Register CLI Commands
    @app.cli.command("init-db")
    def init_db_cmd():
        """Initializes database schema from schema.sql."""
        init_db(app)
        print("Database schema successfully initialized.")

    @app.cli.command("seed-demo")
    def seed_demo_cmd():
        """Seeds initial categories, products, serials, and relative-date sales."""
        from app.seed import seed_database
        init_db(app)
        seed_database(reset=False)
        print("Demo database records successfully seeded with relative dates.")

    @app.cli.command("reset-db")
    def reset_db_cmd():
        """Completely resets database and reseeds demo data."""
        from app.seed import seed_database
        init_db(app)
        seed_database(reset=True)
        print("Database completely reset and reseeded.")

    return app
