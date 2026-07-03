import pytest
import json
from unittest.mock import patch, MagicMock
from app import create_app
from app.extensions import db as _db
from app.models.user import User

@pytest.fixture(scope="session")
def app():
    """Create app in testing mode (in-memory SQLite) with configured client ID."""
    flask_app = create_app(env="testing")
    flask_app.config["GOOGLE_CLIENT_ID"] = "test-client-id.apps.googleusercontent.com"
    flask_app.debug = True  # Enable debug mode to receive otp_dev_only in tests
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
    """Clean the DB before and after each test."""
    with app.app_context():
        yield
        _db.session.rollback()
        for table in reversed(_db.metadata.sorted_tables):
            _db.session.execute(table.delete())
        _db.session.commit()


class TestGoogleAuth:
    @patch("app.routes.google_routes.http_requests.get")
    def test_google_login_success(self, mock_get, client):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "sub": "google-user-id-123",
            "email": "google-user@example.com",
            "name": "Google User",
            "aud": "test-client-id.apps.googleusercontent.com"
        }
        mock_get.return_value = mock_response

        res = client.post(
            "/api/auth/google",
            data=json.dumps({"credential": "valid-token"}),
            content_type="application/json"
        )
        assert res.status_code == 200
        body = res.get_json()
        assert body["success"] is True
        assert "access_token" in body["data"]
        assert body["data"]["user"]["email"] == "google-user@example.com"
        assert body["data"]["user"]["auth_provider"] == "google"

    @patch("app.routes.google_routes.http_requests.get")
    def test_google_login_audience_mismatch(self, mock_get, client):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "sub": "google-user-id-123",
            "email": "google-user@example.com",
            "name": "Google User",
            "aud": "wrong-client-id.apps.googleusercontent.com"
        }
        mock_get.return_value = mock_response

        res = client.post(
            "/api/auth/google",
            data=json.dumps({"credential": "valid-token"}),
            content_type="application/json"
        )
        assert res.status_code == 401
        body = res.get_json()
        assert body["success"] is False
        assert "audience mismatch" in body["error"].lower()

    def test_google_login_missing_credential(self, client):
        res = client.post(
            "/api/auth/google",
            data=json.dumps({}),
            content_type="application/json"
        )
        assert res.status_code == 400


class TestPhoneAuth:
    def test_phone_send_otp_and_verify_success(self, client):
        res = client.post(
            "/api/auth/phone/send-otp",
            data=json.dumps({"phone": "+919876543210"}),
            content_type="application/json"
        )
        assert res.status_code == 200
        body = res.get_json()
        assert body["success"] is True
        otp = body["data"].get("otp_dev_only")
        assert otp is not None

        res_verify = client.post(
            "/api/auth/phone/verify-otp",
            data=json.dumps({
                "phone": "+919876543210",
                "otp": otp,
                "name": "Phone User"
            }),
            content_type="application/json"
        )
        assert res_verify.status_code == 200
        body_verify = res_verify.get_json()
        assert body_verify["success"] is True
        assert "access_token" in body_verify["data"]
        assert body_verify["data"]["user"]["name"] == "Phone User"

    def test_phone_verify_wrong_otp(self, client):
        client.post(
            "/api/auth/phone/send-otp",
            data=json.dumps({"phone": "+919876543210"}),
            content_type="application/json"
        )

        res_verify = client.post(
            "/api/auth/phone/verify-otp",
            data=json.dumps({
                "phone": "+919876543210",
                "otp": "000000"
            }),
            content_type="application/json"
        )
        assert res_verify.status_code == 401
        body_verify = res_verify.get_json()
        assert body_verify["success"] is False
