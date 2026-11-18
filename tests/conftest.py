"""
Pytest fixtures for Ndungu Electronics IMS test suite.
Configures in-memory database and authenticated test client helpers.
"""

import pytest
from app import create_app
from app.config import TestingConfig
from app.db import init_db
from app.seed import seed_database
from app.services.auth_service import AuthService


@pytest.fixture
def app():
    """Creates isolated Flask app configured for testing."""
    test_app = create_app(TestingConfig)
    with test_app.app_context():
        init_db(test_app)
        seed_database(reset=True)
    yield test_app


@pytest.fixture
def client(app):
    """Provides unauthenticated test client."""
    return app.test_client()


@pytest.fixture
def owner_client(app, client):
    """Provides authenticated Owner test client."""
    with app.app_context():
        user = AuthService.get_user_by_username("admin")
        user_id = user.user_id
        username = user.username
        full_name = user.full_name
    with client.session_transaction() as sess:
        sess["user_id"] = user_id
        sess["username"] = username
        sess["full_name"] = full_name
        sess["role"] = "owner"
        sess["_csrf_token"] = "test-csrf-token-xyz"
    return client


@pytest.fixture
def attendant_client(app, client):
    """Provides authenticated Attendant test client."""
    with app.app_context():
        user = AuthService.get_user_by_username("attendant1")
        user_id = user.user_id
        username = user.username
        full_name = user.full_name
    with client.session_transaction() as sess:
        sess["user_id"] = user_id
        sess["username"] = username
        sess["full_name"] = full_name
        sess["role"] = "attendant"
        sess["_csrf_token"] = "test-csrf-token-xyz"
    return client
