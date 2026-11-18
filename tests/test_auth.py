"""
Test suite covering TC-01 (Authentication & Lockout), TC-02 (RBAC Enforcement),
TC-17 (Security Headers & CSRF), and TC-19 (Scrypt Verification).
"""

from datetime import datetime, timedelta
import pytest
from flask import session
from werkzeug.security import check_password_hash, generate_password_hash
from app.db import get_db, transaction
from app.services.auth_service import AuthService


def test_tc01_successful_login_and_logout(client):
    """TC-01: Verifies successful authentication and session creation."""
    # Obtain CSRF token by visiting login page
    res_get = client.get("/login")
    assert res_get.status_code == 200

    with client.session_transaction() as sess:
        csrf = sess["_csrf_token"]

    # Submit valid owner credentials
    res_post = client.post(
        "/login",
        data={"username": "admin", "password": "NdunguAdmin2026!", "csrf_token": csrf},
        follow_redirects=False
    )
    assert res_post.status_code == 302

    with client.session_transaction() as sess:
        assert sess["user_id"] is not None
        assert sess["username"] == "admin"
        assert sess["role"] == "owner"

    # Logout
    with client.session_transaction() as sess:
        csrf_logout = sess["_csrf_token"]

    res_logout = client.post("/logout", data={"csrf_token": csrf_logout}, follow_redirects=True)
    assert res_logout.status_code == 200

    with client.session_transaction() as sess:
        assert "user_id" not in sess


def test_tc01_brute_force_lockout_after_five_attempts(client):
    """TC-01: Verifies 15-minute account lockout (HTTP 429) after 5 failed attempts."""
    client.get("/login")
    with client.session_transaction() as sess:
        csrf = sess["_csrf_token"]

    # Attempt 4 invalid logins
    for i in range(4):
        res = client.post(
            "/login",
            data={"username": "admin", "password": "WrongPassword!", "csrf_token": csrf}
        )
        assert res.status_code == 401

    # 5th attempt triggers lockout
    res_lock = client.post(
        "/login",
        data={"username": "admin", "password": "WrongPassword!", "csrf_token": csrf}
    )
    assert res_lock.status_code == 429
    assert b"locked" in res_lock.data.lower()

    # Even a correct password must now be rejected while locked
    res_correct_while_locked = client.post(
        "/login",
        data={"username": "admin", "password": "NdunguAdmin2026!", "csrf_token": csrf}
    )
    assert res_correct_while_locked.status_code == 429


def test_tc02_rbac_owner_required_decorator(app):
    """TC-02: Verifies RBAC enforcement: Attendant receives 403 on Owner-only views."""
    from app.blueprints.auth import owner_required

    @app.route("/test-owner-only", methods=["GET"])
    @owner_required
    def test_owner_route():
        return "Owner Access Granted"

    # 1. Unauthenticated -> redirects to /login
    client_anon = app.test_client()
    res_anon = client_anon.get("/test-owner-only")
    assert res_anon.status_code == 302
    assert "/login" in res_anon.headers["Location"]

    # 2. Attendant -> returns HTTP 403 Forbidden
    client_att = app.test_client()
    with app.app_context():
        user_att = AuthService.get_user_by_username("attendant1")
        user_owner = AuthService.get_user_by_username("admin")

    with client_att.session_transaction() as sess:
        sess["user_id"] = user_att.user_id
        sess["username"] = user_att.username
        sess["role"] = "attendant"
    res_att = client_att.get("/test-owner-only")
    assert res_att.status_code == 403

    # 3. Owner -> returns HTTP 200 OK
    client_owner = app.test_client()
    with client_owner.session_transaction() as sess:
        sess["user_id"] = user_owner.user_id
        sess["username"] = user_owner.username
        sess["role"] = "owner"
    res_owner = client_owner.get("/test-owner-only")
    assert res_owner.status_code == 200
    assert b"Owner Access Granted" in res_owner.data


def test_tc17_security_headers_and_csrf_protection(client):
    """TC-17: Verifies HTTP security headers and CSRF token enforcement."""
    res = client.get("/login")
    assert res.status_code == 200

    # Verify Security Headers
    assert "Content-Security-Policy" in res.headers
    assert res.headers["X-Content-Type-Options"] == "nosniff"
    assert res.headers["X-Frame-Options"] == "DENY"
    assert res.headers["Referrer-Policy"] == "strict-origin-when-cross-origin"

    # Missing CSRF on mutating POST must be rejected with HTTP 400
    res_no_csrf = client.post("/login", data={"username": "admin", "password": "any"})
    assert res_no_csrf.status_code == 400
    assert b"CSRF" in res_no_csrf.data or b"Invalid" in res_no_csrf.data


def test_tc19_scrypt_password_verification(app):
    """TC-19: Verifies passwords use Werkzeug scrypt hashing algorithm."""
    with app.app_context():
        user = AuthService.get_user_by_username("admin")
        assert user is not None
        assert user.password_hash.startswith("scrypt:")
        assert check_password_hash(user.password_hash, "NdunguAdmin2026!")


def test_tc14b_invite_token_signup_and_expiration(client, app):
    """TC-14b: Verifies single-use 24-hour invite token lifecycle, signup, and expiration rejection."""
    with app.app_context():
        owner = AuthService.get_user_by_username("admin")
        assert owner is not None
        token, err = AuthService.create_invite_token(owner.user_id, role="attendant")
        assert err == ""
        assert token and len(token) > 20

    # 1. Fetch register page with token
    res_get = client.get(f"/register?token={token}")
    assert res_get.status_code == 200
    assert b"Attendant Invitation Sign-Up" in res_get.data or b"Create Account" in res_get.data

    with client.session_transaction() as sess:
        csrf = sess["_csrf_token"]

    # 2. Register successfully with valid token
    res_post = client.post(
        "/register",
        data={
            "token": token,
            "username": "attendant_new",
            "full_name": "Test Attendant",
            "password": "ValidPassword2026!",
            "confirm_password": "ValidPassword2026!",
            "csrf_token": csrf,
        },
        follow_redirects=True,
    )
    assert res_post.status_code == 200
    assert b"Account created successfully" in res_post.data

    # Verify user exists in database with attendant role
    with app.app_context():
        new_user = AuthService.get_user_by_username("attendant_new")
        assert new_user is not None
        assert new_user.role == "attendant"

    # 3. Attempting to re-use the same token must be rejected
    with client.session_transaction() as sess:
        csrf2 = sess["_csrf_token"]

    res_reuse = client.post(
        "/register",
        data={
            "token": token,
            "username": "attendant_duplicate",
            "full_name": "Duplicate User",
            "password": "ValidPassword2026!",
            "confirm_password": "ValidPassword2026!",
            "csrf_token": csrf2,
        },
        follow_redirects=True,
    )
    assert res_reuse.status_code == 400
    assert b"already been used" in res_reuse.data

    # 4. Expired token rejection
    with app.app_context():
        exp_token, _ = AuthService.create_invite_token(owner.user_id, role="attendant")
        # Manually backdate the expiration to 2 hours ago
        from app.services.auth_service import hash_token
        from app.db import transaction
        past_time = (datetime.now() - timedelta(hours=2)).isoformat()
        with transaction() as conn:
            conn.execute(
                "UPDATE invite_tokens SET expires_at = ? WHERE token_hash = ?",
                (past_time, hash_token(exp_token)),
            )

    res_exp = client.post(
        "/register",
        data={
            "token": exp_token,
            "username": "attendant_expired",
            "full_name": "Expired User",
            "password": "ValidPassword2026!",
            "confirm_password": "ValidPassword2026!",
            "csrf_token": csrf2,
        },
        follow_redirects=True,
    )
    assert res_exp.status_code == 400
    assert b"expired" in res_exp.data

