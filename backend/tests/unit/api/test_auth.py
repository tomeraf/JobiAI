"""
Unit tests for auth API routes.
"""
import pytest
from unittest.mock import patch, AsyncMock, MagicMock
from httpx import AsyncClient

from app.main import app


class TestAuthStatusEndpoint:
    """Tests for GET /api/auth/status endpoint."""

    @pytest.mark.asyncio
    async def test_status_logged_in(self, client: AsyncClient):
        """Test status when logged in."""
        mock_auth = MagicMock()
        mock_auth.check_session = AsyncMock(return_value=True)
        mock_auth.get_profile_info = AsyncMock(return_value={"name": "Test User"})
        mock_auth.close = AsyncMock()

        with patch("app.api.auth.LinkedInAuth", return_value=mock_auth):
            response = await client.get("/api/auth/status")

        assert response.status_code == 200
        data = response.json()
        assert data["logged_in"] is True
        assert data["name"] == "Test User"
        assert "active" in data["message"].lower()

    @pytest.mark.asyncio
    async def test_status_not_logged_in(self, client: AsyncClient):
        """Test status when not logged in."""
        mock_auth = MagicMock()
        mock_auth.check_session = AsyncMock(return_value=False)
        mock_auth.close = AsyncMock()

        with patch("app.api.auth.LinkedInAuth", return_value=mock_auth):
            response = await client.get("/api/auth/status")

        assert response.status_code == 200
        data = response.json()
        assert data["logged_in"] is False
        assert "not logged in" in data["message"].lower()

    @pytest.mark.asyncio
    async def test_status_error_handling(self, client: AsyncClient):
        """Test status when error occurs."""
        mock_auth = MagicMock()
        mock_auth.check_session = AsyncMock(side_effect=Exception("Connection failed"))
        mock_auth.close = AsyncMock()

        with patch("app.api.auth.LinkedInAuth", return_value=mock_auth):
            response = await client.get("/api/auth/status")

        assert response.status_code == 200
        data = response.json()
        assert data["logged_in"] is False
        assert "error" in data["message"].lower()

    @pytest.mark.asyncio
    async def test_status_closes_auth(self, client: AsyncClient):
        """Test that auth is closed after status check."""
        mock_auth = MagicMock()
        mock_auth.check_session = AsyncMock(return_value=False)
        mock_auth.close = AsyncMock()

        with patch("app.api.auth.LinkedInAuth", return_value=mock_auth):
            await client.get("/api/auth/status")

        mock_auth.close.assert_called_once()


class TestLoginEndpoint:
    """Tests for POST /api/auth/login endpoint."""

    @pytest.mark.asyncio
    async def test_login_success(self, client: AsyncClient):
        """Test successful login."""
        mock_auth = MagicMock()
        mock_auth.login = AsyncMock(return_value=True)
        mock_auth.get_profile_info = AsyncMock(return_value={"name": "Test User"})
        mock_auth.close = AsyncMock()

        with patch("app.api.auth.LinkedInAuth", return_value=mock_auth):
            response = await client.post(
                "/api/auth/login",
                json={"wait_for_login": True}
            )

        assert response.status_code == 200
        data = response.json()
        assert data["logged_in"] is True
        assert data["name"] == "Test User"
        assert "success" in data["message"].lower()

    @pytest.mark.asyncio
    async def test_login_failure(self, client: AsyncClient):
        """Test failed login."""
        mock_auth = MagicMock()
        mock_auth.login = AsyncMock(return_value=False)
        mock_auth.close = AsyncMock()

        with patch("app.api.auth.LinkedInAuth", return_value=mock_auth):
            response = await client.post(
                "/api/auth/login",
                json={"wait_for_login": True}
            )

        assert response.status_code == 200
        data = response.json()
        assert data["logged_in"] is False
        assert "not completed" in data["message"].lower()

    @pytest.mark.asyncio
    async def test_login_error_raises_500(self, client: AsyncClient):
        """Test login error raises HTTPException."""
        mock_auth = MagicMock()
        mock_auth.login = AsyncMock(side_effect=Exception("Browser crashed"))
        mock_auth.close = AsyncMock()

        with patch("app.api.auth.LinkedInAuth", return_value=mock_auth):
            response = await client.post(
                "/api/auth/login",
                json={"wait_for_login": True}
            )

        assert response.status_code == 500
        assert "Browser crashed" in response.json()["detail"]

    @pytest.mark.asyncio
    async def test_login_default_wait(self, client: AsyncClient):
        """Test login with default wait_for_login value."""
        mock_auth = MagicMock()
        mock_auth.login = AsyncMock(return_value=True)
        mock_auth.get_profile_info = AsyncMock(return_value={"name": "Test User"})
        mock_auth.close = AsyncMock()

        with patch("app.api.auth.LinkedInAuth", return_value=mock_auth):
            response = await client.post("/api/auth/login", json={})

        assert response.status_code == 200
        mock_auth.login.assert_called_once_with(wait_for_manual_login=True)

    @pytest.mark.asyncio
    async def test_login_no_wait(self, client: AsyncClient):
        """Test login without waiting."""
        mock_auth = MagicMock()
        mock_auth.login = AsyncMock(return_value=True)
        mock_auth.get_profile_info = AsyncMock(return_value={"name": "Test User"})
        mock_auth.close = AsyncMock()

        with patch("app.api.auth.LinkedInAuth", return_value=mock_auth):
            response = await client.post(
                "/api/auth/login",
                json={"wait_for_login": False}
            )

        assert response.status_code == 200
        mock_auth.login.assert_called_once_with(wait_for_manual_login=False)

    @pytest.mark.asyncio
    async def test_login_closes_auth(self, client: AsyncClient):
        """Test that auth is closed after login attempt."""
        mock_auth = MagicMock()
        mock_auth.login = AsyncMock(return_value=True)
        mock_auth.get_profile_info = AsyncMock(return_value={"name": "Test User"})
        mock_auth.close = AsyncMock()

        with patch("app.api.auth.LinkedInAuth", return_value=mock_auth):
            await client.post("/api/auth/login", json={})

        mock_auth.close.assert_called_once()

    @pytest.mark.asyncio
    async def test_login_closes_auth_on_error(self, client: AsyncClient):
        """Test that auth is closed even when login fails."""
        mock_auth = MagicMock()
        mock_auth.login = AsyncMock(side_effect=Exception("Error"))
        mock_auth.close = AsyncMock()

        with patch("app.api.auth.LinkedInAuth", return_value=mock_auth):
            await client.post("/api/auth/login", json={})

        mock_auth.close.assert_called_once()


class TestLogoutEndpoint:
    """Tests for POST /api/auth/logout endpoint."""

    @pytest.mark.asyncio
    async def test_logout_success(self, client: AsyncClient):
        """Test successful logout."""
        mock_auth = MagicMock()
        mock_auth.clear_session = AsyncMock()
        mock_auth.close = AsyncMock()

        with patch("app.api.auth.LinkedInAuth", return_value=mock_auth):
            response = await client.post("/api/auth/logout")

        assert response.status_code == 200
        assert "cleared" in response.json()["message"].lower()
        mock_auth.clear_session.assert_called_once()

    @pytest.mark.asyncio
    async def test_logout_error_raises_500(self, client: AsyncClient):
        """Test logout error raises HTTPException."""
        mock_auth = MagicMock()
        mock_auth.clear_session = AsyncMock(side_effect=Exception("File locked"))
        mock_auth.close = AsyncMock()

        with patch("app.api.auth.LinkedInAuth", return_value=mock_auth):
            response = await client.post("/api/auth/logout")

        assert response.status_code == 500
        assert "File locked" in response.json()["detail"]

    @pytest.mark.asyncio
    async def test_logout_closes_auth(self, client: AsyncClient):
        """Test that auth is closed after logout."""
        mock_auth = MagicMock()
        mock_auth.clear_session = AsyncMock()
        mock_auth.close = AsyncMock()

        with patch("app.api.auth.LinkedInAuth", return_value=mock_auth):
            await client.post("/api/auth/logout")

        mock_auth.close.assert_called_once()

    @pytest.mark.asyncio
    async def test_logout_closes_auth_on_error(self, client: AsyncClient):
        """Test that auth is closed even when logout fails."""
        mock_auth = MagicMock()
        mock_auth.clear_session = AsyncMock(side_effect=Exception("Error"))
        mock_auth.close = AsyncMock()

        with patch("app.api.auth.LinkedInAuth", return_value=mock_auth):
            await client.post("/api/auth/logout")

        mock_auth.close.assert_called_once()


class TestAuthModels:
    """Tests for auth Pydantic models."""

    def test_auth_status_model(self):
        """Test AuthStatus model."""
        from app.api.auth import AuthStatus

        status = AuthStatus(
            logged_in=True,
            email="test@example.com",
            name="Test User",
            message="Active session"
        )
        assert status.logged_in is True
        assert status.email == "test@example.com"
        assert status.name == "Test User"
        assert status.message == "Active session"

    def test_auth_status_optional_fields(self):
        """Test AuthStatus with optional fields."""
        from app.api.auth import AuthStatus

        status = AuthStatus(
            logged_in=False,
            message="Not logged in"
        )
        assert status.logged_in is False
        assert status.email is None
        assert status.name is None

    def test_login_request_model(self):
        """Test LoginRequest model."""
        from app.api.auth import LoginRequest

        request = LoginRequest(wait_for_login=False)
        assert request.wait_for_login is False

    def test_login_request_default(self):
        """Test LoginRequest default value."""
        from app.api.auth import LoginRequest

        request = LoginRequest()
        assert request.wait_for_login is True
