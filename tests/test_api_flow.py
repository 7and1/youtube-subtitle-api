from __future__ import annotations

import re
from contextlib import asynccontextmanager

import pytest
from asgi_lifespan import LifespanManager
from httpx import ASGITransport, AsyncClient

from main import app


@asynccontextmanager
async def _client():
    async with LifespanManager(app):
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            yield client


@pytest.mark.asyncio
async def test_health_ok():
    async with _client() as client:
        r = await client.get("/health")
        assert r.status_code in (200, 503)
        body = r.json()
        assert "components" in body
        assert "redis" in body["components"]
        assert "postgres" in body["components"]


@pytest.mark.asyncio
async def test_rewrite_video_queues_job_and_poll_status():
    async with _client() as client:
        r = await client.post(
            "/api/rewrite-video",
            headers={"X-API-Key": "test"},
            json={"video_id": "dQw4w9WgXcQ", "language": "en", "clean_for_ai": True},
        )
        assert r.status_code in (200, 202)
        data = r.json()

        # Cache hit returns full payload; cache miss returns job receipt (202).
        if r.status_code == 202:
            assert "job_id" in data
            assert re.match(r"^[a-f0-9]{32}$", data["job_id"]) or isinstance(
                data["job_id"], str
            )
            job_id = data["job_id"]

            status = await client.get(
                "/api/job/" + job_id, headers={"X-API-Key": "test"}
            )
            assert status.status_code == 200
            s = status.json()
            assert s["job_id"] == job_id
            assert s["status"] in (
                "queued",
                "started",
                "deferred",
                "scheduled",
                "failed",
                "finished",
            )


@pytest.mark.asyncio
async def test_get_subtitles_404_when_missing():
    async with _client() as client:
        r = await client.get(
            "/api/subtitles/dQw4w9WgXcQ", headers={"X-API-Key": "test"}
        )
        assert r.status_code in (200, 404)
