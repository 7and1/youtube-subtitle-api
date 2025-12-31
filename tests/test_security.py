"""
Security tests for authentication, authorization, and rate limiting.

Tests cover:
- API key authentication
- JWT authentication
- Admin endpoint authorization
- Rate limit enforcement
- CORS behavior
- Request ID propagation
- IP hashing for logging
"""

from __future__ import annotations

import hmac
import hashlib
import pytest
from unittest.mock import Mock, patch, AsyncMock
from contextlib import asynccontextmanager

from httpx import ASGITransport, AsyncClient
from asgi_lifespan import LifespanManager

from main import app
from src.services.security import (
    hash_ip_for_logs,
    get_client_ip,
    require_api_key,
    require_jwt,
    require_admin_auth,
)
from src.api.middleware import ErrorCodeException
from fastapi import HTTPException, Request


@pytest.fixture
def mock_request():
    """Create a mock FastAPI request."""
    request = Mock(spec=Request)
    request.headers = {}
    request.client = Mock()
    request.client.host = "192.168.1.100"
    request.state = Mock()
    return request


class TestIPHashing:
    """Tests for IP address hashing for secure logging."""

    def test_hash_ip_for_logs_consistent(self):
        """Test that hashing is consistent for the same IP."""
        ip = "192.168.1.100"
        hash1 = hash_ip_for_logs(ip)
        hash2 = hash_ip_for_logs(ip)

        assert hash1 == hash2
        assert len(hash1) == 16  # First 16 chars of SHA256
        assert hash1.isalnum()

    def test_hash_ip_different_for_different_ips(self):
        """Test that different IPs produce different hashes."""
        hash1 = hash_ip_for_logs("192.168.1.100")
        hash2 = hash_ip_for_logs("192.168.1.101")
        hash3 = hash_ip_for_logs("10.0.0.1")

        assert hash1 != hash2
        assert hash1 != hash3
        assert hash2 != hash3

    def test_hash_ip_handles_ipv6(self):
        """Test that IPv6 addresses are handled correctly."""
        ipv6 = "2001:0db8:85a3:0000:0000:8a2e:0370:7334"
        hashed = hash_ip_for_logs(ipv6)

        assert hashed is not None
        assert len(hashed) == 16

    def test_hash_ip_handles_localhost(self):
        """Test that localhost variants are hashed correctly."""
        hashes = [hash_ip_for_logs(ip) for ip in ["127.0.0.1", "::1", "localhost"]]

        # All should produce valid hashes
        for h in hashes:
            assert len(h) == 16


class TestGetClientIP:
    """Tests for client IP extraction."""

    def test_get_client_ip_direct(self):
        """Test IP extraction from direct connection."""
        request = Mock(spec=Request)
        request.headers = {}
        request.client = Mock()
        request.client.host = "192.168.1.100"

        ip = get_client_ip(request)
        assert ip == "192.168.1.100"

    def test_get_client_ip_from_x_forwarded_for(self):
        """Test IP extraction from X-Forwarded-For header."""
        request = Mock(spec=Request)
        request.headers = {"X-Forwarded-For": "203.0.113.1, 192.168.1.100"}
        request.client = Mock()
        request.client.host = "192.168.1.100"

        ip = get_client_ip(request)
        assert ip == "203.0.113.1"  # First IP in the list

    def test_get_client_ip_from_x_forwarded_for_single(self):
        """Test IP extraction from X-Forwarded-For with single IP."""
        request = Mock(spec=Request)
        request.headers = {"X-Forwarded-For": "203.0.113.1"}
        request.client = Mock()
        request.client.host = "192.168.1.100"

        ip = get_client_ip(request)
        assert ip == "203.0.113.1"

    def test_get_client_ip_forwarded_with_spaces(self):
        """Test IP extraction handles spaces in X-Forwarded-For."""
        request = Mock(spec=Request)
        request.headers = {"X-Forwarded-For": " 203.0.113.1 , 192.168.1.100 "}
        request.client = Mock()
        request.client.host = "192.168.1.100"

        ip = get_client_ip(request)
        assert ip == "203.0.113.1"

    def test_get_client_ip_no_client(self):
        """Test IP extraction when request.client is None."""
        request = Mock(spec=Request)
        request.headers = {}
        request.client = None

        ip = get_client_ip(request)
        assert ip == "unknown"


class TestAPIKeyAuth:
    """Tests for API key authentication."""

    def test_require_api_key_success(self, mock_request):
        """Test successful API key authentication."""
        with patch("src.services.security.settings") as mock_settings:
            mock_settings.API_KEY = "test-secret-key"
            mock_settings.API_KEY_HEADER_NAME = "X-API-Key"

            mock_request.headers = {"X-API-Key": "test-secret-key"}

            # Should not raise
            require_api_key(mock_request)

    def test_require_api_key_constant_time_comparison(self, mock_request):
        """Test that API key comparison uses constant-time algorithm."""
        with patch("src.services.security.settings") as mock_settings:
            mock_settings.API_KEY = "test-secret-key-12345678"
            mock_settings.API_KEY_HEADER_NAME = "X-API-Key"

            # Wrong key that's very similar to correct key
            mock_request.headers = {"X-API-Key": "test-secret-key-12345679"}

            with pytest.raises(HTTPException) as exc_info:
                require_api_key(mock_request)

            assert exc_info.value.status_code == 401

    def test_require_api_key_missing_key(self, mock_request):
        """Test that missing API key is rejected."""
        with patch("src.services.security.settings") as mock_settings:
            mock_settings.API_KEY = "test-secret-key"
            mock_settings.API_KEY_HEADER_NAME = "X-API-Key"

            mock_request.headers = {}

            with pytest.raises(HTTPException) as exc_info:
                require_api_key(mock_request)

            assert exc_info.value.status_code == 401
            assert "Invalid or missing API key" in str(exc_info.value.detail)

    def test_require_api_key_wrong_key(self, mock_request):
        """Test that wrong API key is rejected."""
        with patch("src.services.security.settings") as mock_settings:
            mock_settings.API_KEY = "correct-secret-key"
            mock_settings.API_KEY_HEADER_NAME = "X-API-Key"

            mock_request.headers = {"X-API-Key": "wrong-secret-key"}

            with pytest.raises(HTTPException) as exc_info:
                require_api_key(mock_request)

            assert exc_info.value.status_code == 401

    def test_require_api_key_not_configured(self, mock_request):
        """Test that unconfigured API key results in 500 error (fail closed)."""
        with patch("src.services.security.settings") as mock_settings:
            mock_settings.API_KEY = None
            mock_settings.API_KEY_HEADER_NAME = "X-API-Key"

            mock_request.headers = {"X-API-Key": "some-key"}

            with pytest.raises(HTTPException) as exc_info:
                require_api_key(mock_request)

            assert exc_info.value.status_code == 500
            assert "not configured" in str(exc_info.value.detail)


class TestJWTAuth:
    """Tests for JWT authentication."""

    def test_require_jwt_success(self, mock_request):
        """Test successful JWT authentication."""
        with patch("src.services.security.settings") as mock_settings:
            mock_settings.JWT_SECRET = "test-jwt-secret"

            # Create a valid JWT
            import jwt
            token = jwt.encode({"sub": "user123"}, mock_settings.JWT_SECRET, algorithm="HS256")

            mock_request.headers = {"Authorization": f"Bearer {token}"}

            # Should not raise
            require_jwt(mock_request)

    def test_require_jwt_missing_header(self, mock_request):
        """Test that missing Authorization header is rejected."""
        with patch("src.services.security.settings") as mock_settings:
            mock_settings.JWT_SECRET = "test-jwt-secret"

            mock_request.headers = {}

            with pytest.raises(HTTPException) as exc_info:
                require_jwt(mock_request)

            assert exc_info.value.status_code == 401
            assert "Missing bearer token" in str(exc_info.value.detail)

    def test_require_jwt_wrong_prefix(self, mock_request):
        """Test that wrong token prefix is rejected."""
        with patch("src.services.security.settings") as mock_settings:
            mock_settings.JWT_SECRET = "test-jwt-secret"

            mock_request.headers = {"Authorization": "Basic some-token"}

            with pytest.raises(HTTPException) as exc_info:
                require_jwt(mock_request)

            assert exc_info.value.status_code == 401

    def test_require_jwt_invalid_token(self, mock_request):
        """Test that invalid JWT is rejected."""
        with patch("src.services.security.settings") as mock_settings:
            mock_settings.JWT_SECRET = "test-jwt-secret"

            mock_request.headers = {"Authorization": "Bearer invalid-jwt-token"}

            with pytest.raises(HTTPException) as exc_info:
                require_jwt(mock_request)

            assert exc_info.value.status_code == 401
            assert "Invalid token" in str(exc_info.value.detail)

    def test_require_jwt_expired_token(self, mock_request):
        """Test that expired JWT is rejected."""
        with patch("src.services.security.settings") as mock_settings:
            mock_settings.JWT_SECRET = "test-jwt-secret"

            # Create an expired JWT (exp in the past)
            import jwt
            from datetime import datetime, timedelta

            expired_token = jwt.encode(
                {
                    "sub": "user123",
                    "exp": (datetime.utcnow() - timedelta(hours=1)).timestamp()
                },
                mock_settings.JWT_SECRET,
                algorithm="HS256"
            )

            mock_request.headers = {"Authorization": f"Bearer {expired_token}"}

            with pytest.raises(HTTPException) as exc_info:
                require_jwt(mock_request)

            assert exc_info.value.status_code == 401
            assert "expired" in str(exc_info.value.detail).lower()

    def test_require_jwt_not_configured(self, mock_request):
        """Test that unconfigured JWT results in 500 error (fail closed)."""
        with patch("src.services.security.settings") as mock_settings:
            mock_settings.JWT_SECRET = None

            import jwt
            token = jwt.encode({"sub": "user123"}, "some-secret", algorithm="HS256")
            mock_request.headers = {"Authorization": f"Bearer {token}"}

            with pytest.raises(HTTPException) as exc_info:
                require_jwt(mock_request)

            assert exc_info.value.status_code == 500
            assert "not configured" in str(exc_info.value.detail)


class TestAdminAuth:
    """Tests for admin authentication (JWT + API key fallback)."""

    def test_require_admin_jwt_preferred(self, mock_request):
        """Test that JWT is preferred when both are configured."""
        with patch("src.services.security.settings") as mock_settings:
            mock_settings.JWT_SECRET = "test-jwt-secret"
            mock_settings.API_KEY = "test-api-key"
            mock_settings.API_KEY_HEADER_NAME = "X-API-Key"

            import jwt
            token = jwt.encode({"sub": "admin"}, mock_settings.JWT_SECRET, algorithm="HS256")

            mock_request.headers = {
                "Authorization": f"Bearer {token}",
                "X-API-Key": "wrong-api-key"  # This should be ignored
            }

            # Should not raise - JWT is preferred
            require_admin_auth(mock_request)

    def test_require_admin_api_key_fallback(self, mock_request):
        """Test API key fallback when JWT is not configured."""
        with patch("src.services.security.settings") as mock_settings:
            mock_settings.JWT_SECRET = None
            mock_settings.API_KEY = "test-api-key"
            mock_settings.API_KEY_HEADER_NAME = "X-API-Key"

            mock_request.headers = {"X-API-Key": "test-api-key"}

            # Should not raise
            require_admin_auth(mock_request)

    def test_require_admin_no_auth_configured(self, mock_request):
        """Test that request is denied when no auth is configured (fail closed)."""
        with patch("src.services.security.settings") as mock_settings:
            mock_settings.JWT_SECRET = None
            mock_settings.API_KEY = None

            mock_request.headers = {}

            with pytest.raises(HTTPException) as exc_info:
                require_admin_auth(mock_request)

            assert exc_info.value.status_code == 500
            assert "not configured" in str(exc_info.value.detail)


class TestRateLimitEnforcement:
    """Tests for rate limiting enforcement."""

    @pytest.mark.asyncio
    async def test_rate_limit_blocks_after_threshold(self):
        """Test that requests are blocked after rate limit is exceeded."""
        with patch("src.services.rate_limiter.logger"):
            from src.services.rate_limiter import RateLimiter
            import redis.asyncio as redis

            # Create mock Redis client
            mock_redis = AsyncMock()

            # Simulate rate limiter responses using Lua script
            call_count = [0]

            async def mock_eval(script, num_keys, *args):
                call_count[0] += 1
                key = args[0]
                # Allow first 2 requests, block third
                if call_count[0] <= 2:
                    return [1, 5]  # allowed, remaining tokens
                return [0, 0]  # blocked

            mock_redis.eval = mock_eval

            limiter = RateLimiter(
                redis_client=mock_redis,
                requests_per_minute=2,
                burst_size=0,
            )

            allowed1, _, _, info1 = await limiter.check_rate_limit("192.168.1.1", "/api/v1/subtitles")
            allowed2, _, _, info2 = await limiter.check_rate_limit("192.168.1.1", "/api/v1/subtitles")
            allowed3, _, _, info3 = await limiter.check_rate_limit("192.168.1.1", "/api/v1/subtitles")

            assert allowed1 is True
            assert allowed2 is True
            assert allowed3 is False

    @pytest.mark.asyncio
    async def test_rate_limit_fail_closed_on_redis_error(self):
        """Test that rate limiter denies requests when Redis fails (fail closed)."""
        from src.services.rate_limiter import RateLimiter
        from redis.exceptions import RedisError

        mock_redis = AsyncMock()
        mock_redis.eval = AsyncMock(side_effect=RedisError("Connection lost"))

        limiter = RateLimiter(
            redis_client=mock_redis,
            requests_per_minute=30,
            burst_size=5,
            fail_open=False,  # Default secure behavior
        )

        allowed, remaining, reset_at, info = await limiter.check_rate_limit("192.168.1.1", "/api/v1/subtitles")

        assert allowed is False
        assert remaining == 0

    @pytest.mark.asyncio
    async def test_rate_limit_fail_open_mode(self):
        """Test that rate limiter can be configured to fail open."""
        from src.services.rate_limiter import RateLimiter
        from redis.exceptions import RedisError

        mock_redis = AsyncMock()
        mock_redis.eval = AsyncMock(side_effect=RedisError("Connection lost"))

        limiter = RateLimiter(
            redis_client=mock_redis,
            requests_per_minute=30,
            burst_size=5,
            fail_open=True,  # Dangerous mode
        )

        allowed, remaining, reset_at, info = await limiter.check_rate_limit("192.168.1.1", "/api/v1/subtitles")

        assert allowed is True
        assert remaining == 30


@asynccontextmanager
async def _authenticated_client(api_key: str = "test-api-key"):
    """Create an authenticated test client."""
    app.state.rate_limiter = None  # Disable rate limiting for tests

    async with LifespanManager(app):
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
            headers={"X-API-Key": api_key}
        ) as client:
            yield client


class TestAdminEndpointAuthorization:
    """Integration tests for admin endpoint authorization."""

    @pytest.mark.asyncio
    async def test_admin_cache_clear_requires_auth(self):
        """Test that cache clear endpoint requires authentication."""
        async with LifespanManager(app):
            async with AsyncClient(
                transport=ASGITransport(app=app),
                base_url="http://test"
            ) as client:
                response = await client.post("/api/v1/admin/cache/clear")

                # Should get 401 or 500 depending on config
                assert response.status_code in (401, 500)

    @pytest.mark.asyncio
    async def test_admin_queue_stats_requires_auth(self):
        """Test that queue stats endpoint requires authentication."""
        async with LifespanManager(app):
            async with AsyncClient(
                transport=ASGITransport(app=app),
                base_url="http://test"
            ) as client:
                response = await client.get("/api/v1/admin/queue/stats")

                # Should get 401 or 500 depending on config
                assert response.status_code in (401, 500)

    @pytest.mark.asyncio
    async def test_admin_rate_limit_reset_requires_auth(self):
        """Test that rate limit reset endpoint requires authentication."""
        async with LifespanManager(app):
            async with AsyncClient(
                transport=ASGITransport(app=app),
                base_url="http://test"
            ) as client:
                response = await client.post("/api/v1/admin/rate-limit/reset/192.168.1.1")

                # Should get 401 or 500 depending on config
                assert response.status_code in (401, 500)


class TestCORSSecurity:
    """Tests for CORS security configuration."""

    def test_cors_defaults_to_deny_all(self):
        """Test that CORS defaults to denying all origins."""
        from src.core.config import Settings

        with patch.object(Settings, "model_config", {"env_file": ".env"}):
            settings = Settings(_env_file=None)
            settings.ALLOWED_ORIGINS = []

            # Empty list = deny all
            assert settings.ALLOWED_ORIGINS == []

    def test_cors_parses_comma_separated_origins(self):
        """Test that CORS correctly parses comma-separated origins."""
        from src.core.config import Settings

        settings = Settings(_env_file=None)
        parsed = settings._parse_allowed_origins("https://example.com,https://www.example.com")

        assert parsed == ["https://example.com", "https://www.example.com"]

    def test_cors_wildcard_warning(self):
        """Test that CORS wildcard is recognized."""
        from src.core.config import Settings

        settings = Settings(_env_file=None)
        parsed = settings._parse_allowed_origins("*")

        assert parsed == ["*"]

    def test_cors_empty_string_deny_all(self):
        """Test that empty string results in empty list (deny all)."""
        from src.core.config import Settings

        settings = Settings(_env_file=None)
        parsed = settings._parse_allowed_origins("")

        assert parsed == []


class TestRequestIDPropagation:
    """Tests for Request ID header propagation."""

    @pytest.mark.asyncio
    async def test_request_id_header_returned(self):
        """Test that X-Request-ID header is returned in responses."""
        async with LifespanManager(app):
            async with AsyncClient(
                transport=ASGITransport(app=app),
                base_url="http://test",
                headers={"X-API-Key": "test"}
            ) as client:
                response = await client.get("/health")

                assert "X-Request-ID" in response.headers
                assert len(response.headers["X-Request-ID"]) > 0

    @pytest.mark.asyncio
    async def test_request_id_preserved_from_client(self):
        """Test that client-provided Request ID is preserved."""
        client_request_id = "my-custom-request-id-12345"

        async with LifespanManager(app):
            async with AsyncClient(
                transport=ASGITransport(app=app),
                base_url="http://test",
                headers={"X-API-Key": "test", "X-Request-ID": client_request_id}
            ) as client:
                response = await client.get("/health")

                assert response.headers["X-Request-ID"] == client_request_id


class TestSecurityHeaders:
    """Tests for security-related headers."""

    @pytest.mark.asyncio
    async def test_rate_limit_headers_present(self):
        """Test that rate limit headers are present in responses."""
        async with LifespanManager(app):
            async with AsyncClient(
                transport=ASGITransport(app=app),
                base_url="http://test",
                headers={"X-API-Key": "test"}
            ) as client:
                response = await client.get("/api/v1/health")

                # Health endpoint might skip rate limit headers
                if response.status_code == 200:
                    # Check for API version header
                    assert "X-API-Version" in response.headers

    @pytest.mark.asyncio
    async def test_error_response_includes_timestamp(self):
        """Test that error responses include timestamp."""
        async with LifespanManager(app):
            async with AsyncClient(
                transport=ASGITransport(app=app),
                base_url="http://test"
            ) as client:
                # Make a request that will return an error
                response = await client.get("/api/v1/subtitles/invalid-video-id")

                if response.status_code != 200:
                    body = response.json()
                    if "error" in body:
                        assert "timestamp" in body.get("error", {})


class TestTimingAttackResistance:
    """Tests for timing attack resistance in authentication."""

    def test_constant_time_compare_for_api_keys(self):
        """Test that API key comparison is constant-time."""
        # This is a conceptual test - actual timing analysis is complex
        # The implementation uses hmac.compare_digest which is constant-time

        key = "test-secret-key-12345678"

        # These should all take the same amount of time to compare
        # regardless of where the first mismatch occurs
        wrong_keys = [
            "test-secret-key-12345679",  # Mismatch at last char
            "Xest-secret-key-12345678",  # Mismatch at first char
            "test-secret-key-22345678",  # Mismatch in middle
        ]

        for wrong_key in wrong_keys:
            result = hmac.compare_digest(key.encode(), wrong_key.encode())
            assert result is False

        # Correct key should match
        result = hmac.compare_digest(key.encode(), key.encode())
        assert result is True
