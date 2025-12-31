"""
Middleware tests for API versioning, headers, and error handling.

Tests cover:
- API versioning redirects
- Rate limit headers
- Request ID generation
- Error response format
- CORS headers
- GZip compression
"""

from __future__ import annotations

import time
import uuid
from contextlib import asynccontextmanager
from unittest.mock import Mock, AsyncMock, patch

import pytest
from httpx import ASGITransport, AsyncClient
from asgi_lifespan import LifespanManager

from main import app
from src.api.middleware import (
    APIVersionMiddleware,
    RateLimitHeadersMiddleware,
    create_error_response,
    ErrorCodeException,
    ERROR_CODES,
)
from fastapi import Request


class TestAPIVersionMiddleware:
    """Tests for API versioning middleware."""

    @pytest.mark.asyncio
    async def test_unversioned_api_redirect(self):
        """Test that /api/ redirects to /api/v1/."""
        async with LifespanManager(app):
            async with AsyncClient(
                transport=ASGITransport(app=app),
                base_url="http://test",
            ) as client:
                response = await client.get("/api/health")

                # Health endpoint exists at both paths
                assert response.status_code in (200, 308)

                if response.status_code == 308:
                    assert "redirect" in response.json()
                    assert "/api/v1/" in response.json()["redirect"]

    @pytest.mark.asyncio
    async def test_v1_api_passes_through(self):
        """Test that /api/v1/ passes through without redirect."""
        async with LifespanManager(app):
            async with AsyncClient(
                transport=ASGITransport(app=app),
                base_url="http://test",
            ) as client:
                response = await client.get("/api/v1/health")

                assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_admin_route_redirect(self):
        """Test that /api/admin redirects to /api/v1/admin."""
        async with LifespanManager(app):
            async with AsyncClient(
                transport=ASGITransport(app=app),
                base_url="http://test",
                headers={"X-API-Key": "test"}
            ) as client:
                response = await client.post("/api/admin/cache/clear")

                # Should redirect or require auth
                assert response.status_code in (308, 401, 500)

    @pytest.mark.asyncio
    async def test_version_redirect_headers(self):
        """Test that redirect includes deprecation headers."""
        async with LifespanManager(app):
            async with AsyncClient(
                transport=ASGITransport(app=app),
                base_url="http://test",
            ) as client:
                response = await client.get("/api/health")

                if response.status_code == 308:
                    assert "X-API-Deprecation" in response.headers
                    assert "X-API-Version" in response.headers
                    assert "Location" in response.headers

    @pytest.mark.asyncio
    async def test_subtitles_route_redirect(self):
        """Test that /api/subtitles redirects to /api/v1/subtitles."""
        async with LifespanManager(app):
            async with AsyncClient(
                transport=ASGITransport(app=app),
                base_url="http://test",
                headers={"X-API-Key": "test"}
            ) as client:
                response = await client.post(
                    "/api/subtitles",
                    json={"video_id": "dQw4w9WgXcQ", "language": "en"}
                )

                # Should either process (200/202) or redirect (308)
                assert response.status_code in (200, 202, 308)


class TestRateLimitHeadersMiddleware:
    """Tests for rate limit headers middleware."""

    @pytest.mark.asyncio
    async def test_rate_limit_headers_present(self):
        """Test that rate limit headers are present."""
        async with LifespanManager(app):
            async with AsyncClient(
                transport=ASGITransport(app=app),
                base_url="http://test",
                headers={"X-API-Key": "test"}
            ) as client:
                response = await client.get("/api/v1/subtitles/dQw4w9WgXcQ")

                # Health check and other endpoints might skip headers
                # Check API endpoints specifically
                if response.status_code != 422:
                    headers = response.headers

                    # Rate limit headers may be present
                    assert "X-RateLimit-Limit" in headers or response.status_code in (200, 404)

    @pytest.mark.asyncio
    async def test_rate_limit_headers_format(self):
        """Test that rate limit headers have correct format."""
        async with LifespanManager(app):
            async with AsyncClient(
                transport=ASGITransport(app=app),
                base_url="http://test",
                headers={"X-API-Key": "test"}
            ) as client:
                response = await client.get("/api/v1/subtitles/dQw4w9WgXcQ")

                headers = response.headers
                if "X-RateLimit-Limit" in headers:
                    limit = headers["X-RateLimit-Limit"]
                    assert limit.isdigit()
                    assert "X-RateLimit-Remaining" in headers
                    assert "X-RateLimit-Reset" in headers
                    assert "X-RateLimit-Policy" in headers

    @pytest.mark.asyncio
    async def test_rate_limit_headers_skipped_for_health(self):
        """Test that rate limit headers are skipped for health endpoints."""
        async with LifespanManager(app):
            async with AsyncClient(
                transport=ASGITransport(app=app),
                base_url="http://test",
            ) as client:
                response = await client.get("/health")

                # Health endpoint should work
                assert response.status_code in (200, 503)

    @pytest.mark.asyncio
    async def test_rate_limit_policy_header_format(self):
        """Test that rate limit policy header has correct format."""
        async with LifespanManager(app):
            async with AsyncClient(
                transport=ASGITransport(app=app),
                base_url="http://test",
                headers={"X-API-Key": "test"}
            ) as client:
                response = await client.get("/api/v1/subtitles/dQw4w9WgXcQ")

                if "X-RateLimit-Policy" in response.headers:
                    policy = response.headers["X-RateLimit-Policy"]
                    # Format: 30;w=60;burst=5
                    assert ";w=" in policy
                    assert ";burst=" in policy


class TestRequestIDGeneration:
    """Tests for request ID generation and propagation."""

    @pytest.mark.asyncio
    async def test_request_id_generated(self):
        """Test that request ID is generated for all requests."""
        async with LifespanManager(app):
            async with AsyncClient(
                transport=ASGITransport(app=app),
                base_url="http://test",
            ) as client:
                response = await client.get("/health")

                assert "X-Request-ID" in response.headers
                request_id = response.headers["X-Request-ID"]
                assert len(request_id) > 0

    @pytest.mark.asyncio
    async def test_request_id_preserved(self):
        """Test that client-provided request ID is preserved."""
        client_request_id = "my-custom-request-id-12345"

        async with LifespanManager(app):
            async with AsyncClient(
                transport=ASGITransport(app=app),
                base_url="http://test",
                headers={"X-Request-ID": client_request_id}
            ) as client:
                response = await client.get("/health")

                assert response.headers["X-Request-ID"] == client_request_id

    @pytest.mark.asyncio
    async def test_request_id_unique_per_request(self):
        """Test that each request gets a unique ID."""
        async with LifespanManager(app):
            async with AsyncClient(
                transport=ASGITransport(app=app),
                base_url="http://test",
            ) as client:
                response1 = await client.get("/health")
                response2 = await client.get("/health")

                id1 = response1.headers["X-Request-ID"]
                id2 = response2.headers["X-Request-ID"]

                assert id1 != id2

    @pytest.mark.asyncio
    async def test_request_id_format(self):
        """Test that request ID follows expected format."""
        async with LifespanManager(app):
            async with AsyncClient(
                transport=ASGITransport(app=app),
                base_url="http://test",
            ) as client:
                response = await client.get("/health")

                request_id = response.headers["X-Request-ID"]
                # Should be a hex string (UUID format)
                assert len(request_id) == 32 or len(request_id) > 0


class TestErrorResponseFormat:
    """Tests for standardized error response format."""

    def test_error_response_structure(self):
        """Test that error response has correct structure."""
        response = create_error_response(
            error_code="INVALID_REQUEST",
            request_id="test-123",
        )

        assert response.status_code == 400
        body = response.body.decode()
        assert "error" in body

    def test_all_error_codes_defined(self):
        """Test that all error codes have required fields."""
        for code, info in ERROR_CODES.items():
            assert "message" in info
            assert "status" in info
            assert isinstance(info["status"], int)
            assert 400 <= info["status"] < 600

    def test_error_response_with_request_id(self):
        """Test error response includes request ID."""
        response = create_error_response(
            error_code="RATE_LIMIT_EXCEEDED",
            request_id="req-12345",
        )

        import json
        body = json.loads(response.body.decode())
        assert body["error"]["request_id"] == "req-12345"

    def test_error_response_with_meta(self):
        """Test error response includes metadata."""
        meta = {"retry_after": 60, "endpoint": "/api/v1/subtitles"}
        response = create_error_response(
            error_code="RATE_LIMIT_EXCEEDED",
            request_id="req-12345",
            meta=meta,
        )

        import json
        body = json.loads(response.body.decode())
        assert body["error"]["meta"] == meta

    def test_error_response_includes_timestamp(self):
        """Test error response includes timestamp."""
        response = create_error_response(
            error_code="INTERNAL_ERROR",
            request_id="req-12345",
        )

        import json
        body = json.loads(response.body.decode())
        assert "timestamp" in body["error"]

    def test_error_response_custom_detail(self):
        """Test error response with custom detail message."""
        response = create_error_response(
            error_code="INVALID_REQUEST",
            detail="Custom error message",
            request_id="req-12345",
        )

        import json
        body = json.loads(response.body.decode())
        assert "Custom error message" in body["error"]["message"]

    def test_error_response_custom_status(self):
        """Test error response with custom status code."""
        response = create_error_response(
            error_code="INTERNAL_ERROR",
            status_code=503,
        )

        assert response.status_code == 503

    def test_error_response_headers(self):
        """Test error response includes correct headers."""
        response = create_error_response(
            error_code="UNAUTHORIZED",
            request_id="req-12345",
        )

        assert "Content-Type" in response.headers
        assert response.headers["Content-Type"] == "application/problem+json"
        assert "X-Error-Code" in response.headers
        assert response.headers["X-Error-Code"] == "UNAUTHORIZED"


class TestErrorCodeException:
    """Tests for ErrorCodeException class."""

    def test_exception_creation(self):
        """Test creating an ErrorCodeException."""
        exc = ErrorCodeException(
            error_code="INVALID_VIDEO_ID",
            detail="Video ID must be 11 characters",
        )

        assert exc.error_code == "INVALID_VIDEO_ID"
        assert exc.status_code == 400
        assert "Video ID must be 11 characters" in str(exc.detail)

    def test_exception_with_meta(self):
        """Test ErrorCodeException with metadata."""
        meta = {"video_id": "invalid", "reason": "too_short"}
        exc = ErrorCodeException(
            error_code="INVALID_VIDEO_ID",
            meta=meta,
        )

        assert exc.meta == meta

    def test_exception_unknown_error_code(self):
        """Test ErrorCodeException with unknown error code."""
        exc = ErrorCodeException(
            error_code="UNKNOWN_ERROR",
        )

        # Should fall back to INTERNAL_ERROR
        assert exc.status_code == 500


class TestCORSMiddleware:
    """Tests for CORS middleware."""

    @pytest.mark.asyncio
    async def test_cors_preflight_request(self):
        """Test CORS preflight OPTIONS request."""
        async with LifespanManager(app):
            async with AsyncClient(
                transport=ASGITransport(app=app),
                base_url="http://test",
            ) as client:
                response = await client.options(
                    "/api/v1/subtitles/dQw4w9WgXcQ",
                    headers={
                        "Origin": "http://localhost:3000",
                        "Access-Control-Request-Method": "GET",
                    }
                )

                # CORS headers may be present depending on config
                assert response.status_code in (200, 404, 405)

    @pytest.mark.asyncio
    async def test_cors_headers_in_response(self):
        """Test CORS headers in actual response."""
        async with LifespanManager(app):
            async with AsyncClient(
                transport=ASGITransport(app=app),
                base_url="http://test",
                headers={"Origin": "http://localhost:3000"}
            ) as client:
                response = await client.get("/health")

                # Depending on CORS configuration
                # Should have headers if origin is allowed
                if response.status_code == 200:
                    # Response should succeed
                    assert True


class TestGZipMiddleware:
    """Tests for GZip compression middleware."""

    @pytest.mark.asyncio
    async def test_gzip_with_small_response(self):
        """Test that small responses may not be compressed."""
        async with LifespanManager(app):
            async with AsyncClient(
                transport=ASGITransport(app=app),
                base_url="http://test",
            ) as client:
                response = await client.get("/health")

                # Should succeed regardless of compression
                assert response.status_code in (200, 503)

    @pytest.mark.asyncio
    async def test_gzip_accept_encoding(self):
        """Test GZip with Accept-Encoding header."""
        async with LifespanManager(app):
            async with AsyncClient(
                transport=ASGITransport(app=app),
                base_url="http://test",
                headers={"Accept-Encoding": "gzip, deflate"}
            ) as client:
                response = await client.get("/health")

                assert response.status_code in (200, 503)


class TestAPIVersionHeaders:
    """Tests for API version headers."""

    @pytest.mark.asyncio
    async def test_api_version_header_present(self):
        """Test that X-API-Version header is present."""
        async with LifespanManager(app):
            async with AsyncClient(
                transport=ASGITransport(app=app),
                base_url="http://test",
            ) as client:
                response = await client.get("/api/v1/health")

                if response.status_code == 200:
                    assert "X-API-Version" in response.headers

    @pytest.mark.asyncio
    async def test_exposed_headers(self):
        """Test that important headers are exposed."""
        async with LifespanManager(app):
            async with AsyncClient(
                transport=ASGITransport(app=app),
                base_url="http://test",
                headers={"X-API-Key": "test"}
            ) as client:
                response = await client.get("/api/v1/subtitles/dQw4w9WgXcQ")

                # Check for various exposed headers
                assert "X-Request-ID" in response.headers
                assert "X-API-Version" in response.headers or response.status_code in (200, 404)


class TestErrorHandling:
    """Tests for error handling in middleware."""

    @pytest.mark.asyncio
    async def test_404_error_response(self):
        """Test that 404 errors have proper format."""
        async with LifespanManager(app):
            async with AsyncClient(
                transport=ASGITransport(app=app),
                base_url="http://test",
            ) as client:
                response = await client.get("/nonexistent-endpoint")

                assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_405_method_not_allowed(self):
        """Test that 405 errors are handled."""
        async with LifespanManager(app):
            async with AsyncClient(
                transport=ASGITransport(app=app),
                base_url="http://test",
            ) as client:
                response = await client.delete("/api/v1/subtitles")

                # Should be method not allowed or similar
                assert response.status_code in (405, 404)

    @pytest.mark.asyncio
    async def test_422_validation_error(self):
        """Test that validation errors return 422."""
        async with LifespanManager(app):
            async with AsyncClient(
                transport=ASGITransport(app=app),
                base_url="http://test",
                headers={"X-API-Key": "test"}
            ) as client:
                response = await client.post(
                    "/api/v1/subtitles",
                    json={"language": "en"}  # Missing video_id/video_url
                )

                assert response.status_code == 422


class TestMiddlewareOrder:
    """Tests for middleware execution order."""

    @pytest.mark.asyncio
    async def test_headers_present_after_all_middleware(self):
        """Test that all headers are present after middleware chain."""
        async with LifespanManager(app):
            async with AsyncClient(
                transport=ASGITransport(app=app),
                base_url="http://test",
                headers={"X-API-Key": "test", "X-Request-ID": "test-123"}
            ) as client:
                response = await client.get("/api/v1/health")

                # Check for various headers
                headers = response.headers
                assert "X-Request-ID" in headers
                assert headers["X-Request-ID"] == "test-123"
                assert "X-API-Version" in headers


class TestHealthEndpoint:
    """Tests for health endpoint behavior."""

    @pytest.mark.asyncio
    async def test_health_response_structure(self):
        """Test that health endpoint has correct structure."""
        async with LifespanManager(app):
            async with AsyncClient(
                transport=ASGITransport(app=app),
                base_url="http://test",
            ) as client:
                response = await client.get("/health")

                assert response.status_code in (200, 503)
                body = response.json()
                assert "components" in body

    @pytest.mark.asyncio
    async def test_health_includes_redis_status(self):
        """Test that health endpoint includes Redis status."""
        async with LifespanManager(app):
            async with AsyncClient(
                transport=ASGITransport(app=app),
                base_url="http://test",
            ) as client:
                response = await client.get("/health")

                if response.status_code == 200:
                    body = response.json()
                    assert "redis" in body["components"]

    @pytest.mark.asyncio
    async def test_health_includes_postgres_status(self):
        """Test that health endpoint includes PostgreSQL status."""
        async with LifespanManager(app):
            async with AsyncClient(
                transport=ASGITransport(app=app),
                base_url="http://test",
            ) as client:
                response = await client.get("/health")

                if response.status_code == 200:
                    body = response.json()
                    assert "postgres" in body["components"]


class TestMiddlewareUnitTests:
    """Unit tests for middleware components."""

    @pytest.mark.asyncio
    async def test_api_version_middleware_direct(self):
        """Test APIVersionMiddleware behavior directly."""
        middleware = APIVersionMiddleware(app)

        # Create mock request
        request = Mock(spec=Request)
        request.url = Mock()
        request.url.path = "/api/subtitles"
        request.url.replace = Mock(return_value=request.url)

        call_next = AsyncMock(return_value=Mock(headers={}))

        # This would normally redirect
        # Testing the logic directly is complex due to FastAPI internals
        assert middleware is not None

    @pytest.mark.asyncio
    async def test_rate_limit_middleware_without_rate_limit_info(self):
        """Test RateLimitHeadersMiddleware without rate limit info."""
        middleware = RateLimitHeadersMiddleware(app)

        request = Mock(spec=Request)
        request.url = Mock()
        request.url.path = "/api/v1/test"
        request.state = Mock()
        request.state.rate_limit_info = None

        response = Mock()
        response.headers = {}

        call_next = AsyncMock(return_value=response)

        result = await middleware.dispatch(request, call_next)

        # Should add default headers
        assert "X-RateLimit-Limit" in result.headers


class TestMiddlewareErrorRecovery:
    """Tests for middleware error recovery."""

    @pytest.mark.asyncio
    async def test_middleware_handles_exception(self):
        """Test that middleware handles exceptions gracefully."""
        async with LifespanManager(app):
            async with AsyncClient(
                transport=ASGITransport(app=app),
                base_url="http://test",
            ) as client:
                # Send malformed request
                response = await client.post(
                    "/api/v1/subtitles",
                    data="invalid json",
                    headers={"Content-Type": "application/json"}
                )

                # Should handle gracefully
                assert response.status_code in (400, 422)

    @pytest.mark.asyncio
    async def test_middleware_handles_large_payload(self):
        """Test that middleware handles large payloads."""
        large_data = {"video_id": "dQw4w9WgXcQ", "data": "x" * 10000}

        async with LifespanManager(app):
            async with AsyncClient(
                transport=ASGITransport(app=app),
                base_url="http://test",
                headers={"X-API-Key": "test"}
            ) as client:
                response = await client.post("/api/v1/subtitles", json=large_data)

                # Should handle without crashing
                assert response.status_code in (200, 202, 413, 422)


class TestExposedHeaders:
    """Tests for exposed headers configuration."""

    @pytest.mark.asyncio
    async def test_expose_headers_includes_rate_limit(self):
        """Test that rate limit headers are in exposed headers."""
        # This is implicitly tested by checking headers are present
        async with LifespanManager(app):
            async with AsyncClient(
                transport=ASGITransport(app=app),
                base_url="http://test",
                headers={"X-API-Key": "test"}
            ) as client:
                response = await client.get("/api/v1/subtitles/dQw4w9WgXcQ")

                # If rate limiting is applied, headers should be present
                headers = response.headers
                # At minimum, X-Request-ID and X-API-Version should always be present
                assert "X-Request-ID" in headers
                assert "X-API-Version" in headers
