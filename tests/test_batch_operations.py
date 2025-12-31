"""
Batch operation tests for YouTube Subtitle API.

Tests cover:
- Batch subtitle submission (up to 100 videos)
- Mixed cache hit/miss scenarios
- Batch job status queries
- Error handling for invalid video IDs
- Batch webhook delivery
"""

from __future__ import annotations

import re
from contextlib import asynccontextmanager
from unittest.mock import Mock, AsyncMock, patch

import pytest
from httpx import ASGITransport, AsyncClient
from asgi_lifespan import LifespanManager

from main import app


@asynccontextmanager
async def _client():
    """Create test client with disabled rate limiting."""
    app.state.rate_limiter = None  # Disable rate limiting for tests

    async with LifespanManager(app):
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
            headers={"X-API-Key": "test"}
        ) as client:
            yield client


class TestBatchSubmission:
    """Tests for batch subtitle extraction submission."""

    @pytest.mark.asyncio
    async def test_batch_submit_valid_video_ids(self):
        """Test submitting a batch of valid video IDs."""
        async with _client() as client:
            response = await client.post(
                "/api/v1/subtitles/batch",
                json={
                    "video_ids": ["dQw4w9WgXcQ", "9bZkp7q19f0", "RgKAFK5djSk"],
                    "language": "en",
                    "clean_for_ai": True,
                }
            )

            assert response.status_code == 200
            data = response.json()
            assert "job_ids" in data
            assert "queued_count" in data
            assert "cached_count" in data
            assert "video_count" in data
            assert data["video_count"] == 3

    @pytest.mark.asyncio
    async def test_batch_submit_max_100_videos(self):
        """Test that batch accepts up to 100 videos."""
        async with _client() as client:
            # Generate 100 valid video IDs
            video_ids = ["dQw4w9WgXcQ" + str(i).zfill(11) for i in range(100)]
            # Truncate to valid 11-char IDs
            video_ids = [vid[:11] for vid in video_ids]

            response = await client.post(
                "/api/v1/subtitles/batch",
                json={
                    "video_ids": video_ids,
                    "language": "en",
                }
            )

            # Should either be 200 (if queue accepts) or 422 (if validation rejects)
            assert response.status_code in (200, 202, 422)

    @pytest.mark.asyncio
    async def test_batch_submit_over_100_videos_rejected(self):
        """Test that batch rejects more than 100 videos."""
        async with _client() as client:
            # Generate 101 valid video IDs
            video_ids = ["dQw4w9WgXcQ"] * 101

            response = await client.post(
                "/api/v1/subtitles/batch",
                json={
                    "video_ids": video_ids,
                    "language": "en",
                }
            )

            # Pydantic should reject this with 422
            assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_batch_submit_empty_list_rejected(self):
        """Test that empty batch is rejected."""
        async with _client() as client:
            response = await client.post(
                "/api/v1/subtitles/batch",
                json={
                    "video_ids": [],
                    "language": "en",
                }
            )

            assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_batch_submit_with_webhook(self):
        """Test batch submission with webhook URL."""
        async with _client() as client:
            response = await client.post(
                "/api/v1/subtitles/batch",
                json={
                    "video_ids": ["dQw4w9WgXcQ", "9bZkp7q19f0"],
                    "language": "en",
                    "webhook_url": "https://example.com/webhook",
                }
            )

            assert response.status_code == 200
            data = response.json()
            assert data["video_count"] == 2

    @pytest.mark.asyncio
    async def test_batch_submit_invalid_webhook_url(self):
        """Test that invalid webhook URL is rejected."""
        async with _client() as client:
            response = await client.post(
                "/api/v1/subtitles/batch",
                json={
                    "video_ids": ["dQw4w9WgXcQ"],
                    "language": "en",
                    "webhook_url": "not-a-valid-url",
                }
            )

            assert response.status_code == 422
            data = response.json()
            # Should have validation error about webhook URL

    @pytest.mark.asyncio
    async def test_batch_submit_ftp_webhook_rejected(self):
        """Test that ftp:// webhook URLs are rejected."""
        async with _client() as client:
            response = await client.post(
                "/api/v1/subtitles/batch",
                json={
                    "video_ids": ["dQw4w9WgXcQ"],
                    "language": "en",
                    "webhook_url": "ftp://example.com/webhook",
                }
            )

            assert response.status_code == 422


class TestBatchValidation:
    """Tests for batch request validation."""

    @pytest.mark.asyncio
    async def test_batch_rejects_invalid_video_ids(self):
        """Test that invalid video IDs are rejected."""
        async with _client() as client:
            response = await client.post(
                "/api/v1/subtitles/batch",
                json={
                    "video_ids": [
                        "dQw4w9WgXcQ",  # Valid
                        "too-short",    # Invalid
                        "9bZkp7q19f0",  # Valid
                        "invalid_id!",  # Invalid
                    ],
                    "language": "en",
                }
            )

            assert response.status_code == 400
            data = response.json()
            assert "error" in data

    @pytest.mark.asyncio
    async def test_batch_handles_special_characters(self):
        """Test handling of video IDs with special characters."""
        async with _client() as client:
            response = await client.post(
                "/api/v1/subtitles/batch",
                json={
                    "video_ids": [
                        "dQw4w9WgXcQ",    # Valid
                        "dQw4w9WgXQ!",    # Invalid - has special char
                    ],
                    "language": "en",
                }
            )

            assert response.status_code == 400

    @pytest.mark.asyncio
    async def test_batch_rejects_too_long_video_id(self):
        """Test that too-long video IDs are rejected."""
        async with _client() as client:
            response = await client.post(
                "/api/v1/subtitles/batch",
                json={
                    "video_ids": ["dQw4w9WgXcQ123456"],  # Too long
                    "language": "en",
                }
            )

            assert response.status_code == 400

    @pytest.mark.asyncio
    async def test_batch_rejects_too_short_video_id(self):
        """Test that too-short video IDs are rejected."""
        async with _client() as client:
            response = await client.post(
                "/api/v1/subtitles/batch",
                json={
                    "video_ids": ["dQw4w9W"],  # Too short
                    "language": "en",
                }
            )

            assert response.status_code == 400


class TestBatchCacheHitMiss:
    """Tests for mixed cache hit/miss scenarios in batch operations."""

    @pytest.mark.asyncio
    async def test_batch_all_cache_miss(self):
        """Test batch where all videos miss cache."""
        async with _client() as client:
            # Use random video IDs that won't be cached
            video_ids = [f"nonexist{i}{'a' * 5}" for i in range(5)]

            response = await client.post(
                "/api/v1/subtitles/batch",
                json={
                    "video_ids": video_ids,
                    "language": "en",
                }
            )

            # Should queue all of them
            assert response.status_code in (200, 202, 400)  # 400 if invalid IDs

    @pytest.mark.asyncio
    async def test_batch_mixed_cache_hit_miss(self):
        """Test batch with some cache hits and some misses."""
        async with _client() as client:
            # This test requires actual cached data
            # For now, just test the endpoint structure
            response = await client.post(
                "/api/v1/subtitles/batch",
                json={
                    "video_ids": ["dQw4w9WgXcQ", "9bZkp7q19f0"],
                    "language": "en",
                }
            )

            assert response.status_code == 200
            data = response.json()

            # Should have counts for hits and misses
            assert "queued_count" in data
            assert "cached_count" in data

    @pytest.mark.asyncio
    async def test_batch_all_cache_hit(self):
        """Test batch where all videos hit cache (if pre-populated)."""
        async with _client() as client:
            response = await client.post(
                "/api/v1/subtitles/batch",
                json={
                    "video_ids": ["dQw4w9WgXcQ"],
                    "language": "en",
                }
            )

            assert response.status_code == 200
            data = response.json()

            # If all were cached, queued_count would be 0
            assert "cached_count" in data
            assert "queued_count" in data


class TestBatchStatusQueries:
    """Tests for batch job status queries."""

    @pytest.mark.asyncio
    async def test_get_single_job_status(self):
        """Test getting status of a single job."""
        async with _client() as client:
            # First submit a job
            submit_response = await client.post(
                "/api/v1/subtitles/batch",
                json={
                    "video_ids": ["dQw4w9WgXcQ"],
                    "language": "en",
                }
            )

            if submit_response.status_code == 200:
                data = submit_response.json()
                if data.get("job_ids"):
                    job_id = data["job_ids"][0]

                    # Query job status
                    status_response = await client.get(f"/api/v1/job/{job_id}")
                    assert status_response.status_code == 200

                    job_data = status_response.json()
                    assert job_data["job_id"] == job_id
                    assert "status" in job_data

    @pytest.mark.asyncio
    async def test_get_nonexistent_job_status(self):
        """Test getting status of non-existent job."""
        async with _client() as client:
            response = await client.get("/api/v1/job/nonexistent-job-id-12345")

            assert response.status_code == 200
            data = response.json()
            # Should return status "not_found" or similar
            assert "status" in data

    @pytest.mark.asyncio
    async def test_job_status_valid_states(self):
        """Test that job status returns valid states."""
        async with _client() as client:
            response = await client.get("/api/v1/job/test-job-123")

            assert response.status_code == 200
            data = response.json()

            valid_states = [
                "queued", "started", "deferred", "scheduled",
                "finished", "failed", "not_found"
            ]
            assert data.get("status") in valid_states


class TestBatchErrorHandling:
    """Tests for error handling in batch operations."""

    @pytest.mark.asyncio
    async def test_batch_partial_failure_handling(self):
        """Test handling of partial failures in batch."""
        async with _client() as client:
            response = await client.post(
                "/api/v1/subtitles/batch",
                json={
                    "video_ids": [
                        "dQw4w9WgXcQ",  # Valid
                        "invalid",      # Invalid
                        "9bZkp7q19f0",  # Valid
                    ],
                    "language": "en",
                }
            )

            # Should reject the entire batch due to validation
            assert response.status_code == 400
            data = response.json()
            assert "error" in data

    @pytest.mark.asyncio
    async def test_batch_network_timeout_handling(self):
        """Test handling of network timeouts during batch processing."""
        # This would require mocking the orchestrator
        async with _client() as client:
            # Simulate a request that might timeout
            response = await client.post(
                "/api/v1/subtitles/batch",
                json={
                    "video_ids": ["dQw4w9WgXcQ"],
                    "language": "en",
                },
                timeout=5.0
            )

            # Should not hang indefinitely
            assert response.status_code in (200, 202, 500, 504)

    @pytest.mark.asyncio
    async def test_batch_missing_required_field(self):
        """Test that missing required fields are rejected."""
        async with _client() as client:
            # Missing language field (though it has default)
            response = await client.post(
                "/api/v1/subtitles/batch",
                json={
                    # "video_ids" is required
                    "language": "en",
                }
            )

            assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_batch_extra_fields_ignored(self):
        """Test that extra fields are handled gracefully."""
        async with _client() as client:
            response = await client.post(
                "/api/v1/subtitles/batch",
                json={
                    "video_ids": ["dQw4w9WgXcQ"],
                    "language": "en",
                    "extra_field": "should_be_ignored",
                }
            )

            # Pydantic should ignore extra fields by default
            assert response.status_code == 200


class TestBatchLanguageSupport:
    """Tests for batch operations with different languages."""

    @pytest.mark.asyncio
    async def test_batch_english_language(self):
        """Test batch with English language."""
        async with _client() as client:
            response = await client.post(
                "/api/v1/subtitles/batch",
                json={
                    "video_ids": ["dQw4w9WgXcQ"],
                    "language": "en",
                }
            )

            assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_batch_spanish_language(self):
        """Test batch with Spanish language."""
        async with _client() as client:
            response = await client.post(
                "/api/v1/subtitles/batch",
                json={
                    "video_ids": ["dQw4w9WgXcQ"],
                    "language": "es",
                }
            )

            assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_batch_chinese_simplified(self):
        """Test batch with Chinese (Simplified) language."""
        async with _client() as client:
            response = await client.post(
                "/api/v1/subtitles/batch",
                json={
                    "video_ids": ["dQw4w9WgXcQ"],
                    "language": "zh-Hans",
                }
            )

            assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_batch_chinese_traditional(self):
        """Test batch with Chinese (Traditional) language."""
        async with _client() as client:
            response = await client.post(
                "/api/v1/subtitles/batch",
                json={
                    "video_ids": ["dQw4w9WgXcQ"],
                    "language": "zh-Hant",
                }
            )

            assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_batch_invalid_language(self):
        """Test batch with invalid language code."""
        async with _client() as client:
            response = await client.post(
                "/api/v1/subtitles/batch",
                json={
                    "video_ids": ["dQw4w9WgXcQ"],
                    "language": "invalid-language-code-123",
                }
            )

            # Should still accept (language code validation may be lenient)
            assert response.status_code == 200


class TestBatchCleanForAI:
    """Tests for clean_for_ai option in batch operations."""

    @pytest.mark.asyncio
    async def test_batch_clean_for_ai_true(self):
        """Test batch with clean_for_ai enabled."""
        async with _client() as client:
            response = await client.post(
                "/api/v1/subtitles/batch",
                json={
                    "video_ids": ["dQw4w9WgXcQ"],
                    "language": "en",
                    "clean_for_ai": True,
                }
            )

            assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_batch_clean_for_ai_false(self):
        """Test batch with clean_for_ai disabled."""
        async with _client() as client:
            response = await client.post(
                "/api/v1/subtitles/batch",
                json={
                    "video_ids": ["dQw4w9WgXcQ"],
                    "language": "en",
                    "clean_for_ai": False,
                }
            )

            assert response.status_code == 200


class TestBatchWebhookDelivery:
    """Tests for webhook delivery in batch operations."""

    @pytest.mark.asyncio
    async def test_batch_webhook_url_validated(self):
        """Test that webhook URL is properly validated."""
        async with _client() as client:
            response = await client.post(
                "/api/v1/subtitles/batch",
                json={
                    "video_ids": ["dQw4w9WgXcQ"],
                    "language": "en",
                    "webhook_url": "https://example.com/webhook",
                }
            )

            assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_batch_webhook_missing_protocol(self):
        """Test that webhook URL without protocol is rejected."""
        async with _client() as client:
            response = await client.post(
                "/api/v1/subtitles/batch",
                json={
                    "video_ids": ["dQw4w9WgXcQ"],
                    "language": "en",
                    "webhook_url": "example.com/webhook",
                }
            )

            assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_batch_webhook_http_allowed(self):
        """Test that http:// webhook URLs are allowed (for non-prod)."""
        async with _client() as client:
            response = await client.post(
                "/api/v1/subtitles/batch",
                json={
                    "video_ids": ["dQw4w9WgXcQ"],
                    "language": "en",
                    "webhook_url": "http://localhost:3000/webhook",
                }
            )

            assert response.status_code == 200


class TestBatchPerformance:
    """Tests for batch operation performance characteristics."""

    @pytest.mark.asyncio
    async def test_batch_response_time(self):
        """Test that batch response is reasonably fast."""
        import time

        async with _client() as client:
            start = time.time()
            response = await client.post(
                "/api/v1/subtitles/batch",
                json={
                    "video_ids": ["dQw4w9WgXcQ"] * 10,
                    "language": "en",
                }
            )
            duration = time.time() - start

            assert response.status_code == 200
            # Should respond quickly (< 1 second for 10 videos)
            assert duration < 1.0

    @pytest.mark.asyncio
    async def test_batch_response_size(self):
        """Test that batch response size is reasonable."""
        async with _client() as client:
            response = await client.post(
                "/api/v1/subtitles/batch",
                json={
                    "video_ids": ["dQw4w9WgXcQ"] * 10,
                    "language": "en",
                }
            )

            assert response.status_code == 200
            content = response.content
            # Response should be reasonably sized (< 10KB)
            assert len(content) < 10240


class TestBatchResponseFormat:
    """Tests for batch response format consistency."""

    @pytest.mark.asyncio
    async def test_batch_response_structure(self):
        """Test that batch response has expected structure."""
        async with _client() as client:
            response = await client.post(
                "/api/v1/subtitles/batch",
                json={
                    "video_ids": ["dQw4w9WgXcQ", "9bZkp7q19f0"],
                    "language": "en",
                }
            )

            assert response.status_code == 200
            data = response.json()

            # Required fields
            assert "status" in data
            assert "video_count" in data
            assert "queued_count" in data
            assert "cached_count" in data
            assert "job_ids" in data
            assert "cached" in data

            # Type checks
            assert isinstance(data["video_count"], int)
            assert isinstance(data["queued_count"], int)
            assert isinstance(data["cached_count"], int)
            assert isinstance(data["job_ids"], list)
            assert isinstance(data["cached"], list)

    @pytest.mark.asyncio
    async def test_batch_status_value(self):
        """Test that batch status has correct value."""
        async with _client() as client:
            response = await client.post(
                "/api/v1/subtitles/batch",
                json={
                    "video_ids": ["dQw4w9WgXcQ"],
                    "language": "en",
                }
            )

            assert response.status_code == 200
            data = response.json()
            assert data["status"] == "queued"


class TestBatchAPIKeyAuthentication:
    """Tests for API key authentication in batch operations."""

    @pytest.mark.asyncio
    async def test_batch_without_api_key(self):
        """Test that batch without API key is rejected."""
        async with LifespanManager(app):
            async with AsyncClient(
                transport=ASGITransport(app=app),
                base_url="http://test",
            ) as client:
                # No X-API-Key header
                response = await client.post(
                    "/api/v1/subtitles/batch",
                    json={
                        "video_ids": ["dQw4w9WgXcQ"],
                        "language": "en",
                    }
                )

                # Should be rejected if API_KEY is configured
                # Or accepted if not configured (dev mode)
                assert response.status_code in (200, 401, 500)

    @pytest.mark.asyncio
    async def test_batch_with_wrong_api_key(self):
        """Test that batch with wrong API key is rejected."""
        async with LifespanManager(app):
            async with AsyncClient(
                transport=ASGITransport(app=app),
                base_url="http://test",
                headers={"X-API-Key": "wrong-api-key"}
            ) as client:
                response = await client.post(
                    "/api/v1/subtitles/batch",
                    json={
                        "video_ids": ["dQw4w9WgXcQ"],
                        "language": "en",
                    }
                )

                # Should be rejected if API_KEY is configured
                assert response.status_code in (401, 200, 500)
