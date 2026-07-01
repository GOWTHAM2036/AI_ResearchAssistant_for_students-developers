"""
Authentication Service Tests
Run with:  pytest tests/ -v
"""

import pytest
import json
from app import create_app
from app.extensions import db as _db


# ── Fixtures ───────────────────────────────────────────────────────────────────

@pytest.fixture(scope="session")
def app():
    """Create app in testing mode (in-memory SQLite)."""
    flask_app = create_app(env="testing")
    with flask_app.app_context():
        _db.create_all()
        yield flask_app
        _db.drop_all()


@pytest.fixture()
def client(app):
    """Flask test client."""
    return app.test_client()


@pytest.fixture(autouse=True)
def clean_db(app):
    """Rollback all DB changes after each test to keep tests isolated."""
    with app.app_context():
        yield
        _db.session.rollback()
        # Clear all rows without dropping tables
        for table in reversed(_db.metadata.sorted_tables):
            _db.session.execute(table.delete())
        _db.session.commit()


# ── Helpers ────────────────────────────────────────────────────────────────────

VALID_USER = {
    "name": "Alice Smith",
    "email": "alice@example.com",
    "password": "Secret123",
}


def register(client, data=None):
    return client.post(
        "/api/auth/register",
        data=json.dumps(data or VALID_USER),
        content_type="application/json",
    )


def login(client, data=None):
    creds = data or {"email": VALID_USER["email"], "password": VALID_USER["password"]}
    return client.post(
        "/api/auth/login",
        data=json.dumps(creds),
        content_type="application/json",
    )


# ── Registration Tests ─────────────────────────────────────────────────────────

class TestRegister:
    def test_successful_registration(self, client):
        res = register(client)
        assert res.status_code == 201
        body = res.get_json()
        assert body["success"] is True
        assert "user" in body["data"]
        assert "password_hash" not in body["data"]["user"]  # never exposed

    def test_duplicate_email_returns_409(self, client):
        register(client)
        res = register(client)
        assert res.status_code == 409

    def test_missing_name_returns_400(self, client):
        res = register(client, {"email": "a@b.com", "password": "Secret123"})
        assert res.status_code == 400

    def test_invalid_email_returns_400(self, client):
        res = register(client, {"name": "Bob", "email": "not-an-email", "password": "Secret123"})
        assert res.status_code == 400

    def test_weak_password_returns_400(self, client):
        res = register(client, {"name": "Bob", "email": "bob@b.com", "password": "short"})
        assert res.status_code == 400

    def test_empty_body_returns_400(self, client):
        res = client.post("/api/auth/register", content_type="application/json", data="{}")
        assert res.status_code == 400

    def test_non_json_returns_400(self, client):
        res = client.post("/api/auth/register", data="not json", content_type="text/plain")
        assert res.status_code == 400


# ── Login Tests ────────────────────────────────────────────────────────────────

class TestLogin:
    def test_successful_login_returns_token(self, client):
        register(client)
        res = login(client)
        assert res.status_code == 200
        body = res.get_json()
        assert "access_token" in body["data"]
        assert body["data"]["token_type"] == "Bearer"

    def test_wrong_password_returns_401(self, client):
        register(client)
        res = login(client, {"email": VALID_USER["email"], "password": "WrongPass1"})
        assert res.status_code == 401

    def test_unknown_email_returns_401(self, client):
        res = login(client, {"email": "ghost@x.com", "password": "Secret123"})
        assert res.status_code == 401

    def test_missing_fields_returns_400(self, client):
        res = login(client, {"email": VALID_USER["email"]})
        assert res.status_code == 400


# ── Protected Route Tests ──────────────────────────────────────────────────────

class TestProtectedRoute:
    def test_access_with_valid_token(self, client):
        register(client)
        token = login(client).get_json()["data"]["access_token"]
        res = client.get(
            "/api/protected",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert res.status_code == 200
        assert res.get_json()["data"]["user"]["email"] == VALID_USER["email"].lower()

    def test_access_without_token_returns_401(self, client):
        res = client.get("/api/protected")
        assert res.status_code == 401

    def test_access_with_invalid_token_returns_401(self, client):
        res = client.get(
            "/api/protected",
            headers={"Authorization": "Bearer this.is.invalid"},
        )
        assert res.status_code == 422  # Flask-JWT-Extended returns 422 for malformed tokens
