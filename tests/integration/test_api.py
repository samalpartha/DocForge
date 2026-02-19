"""Integration tests for FastAPI endpoints (contract tests)."""

import pytest
from httpx import AsyncClient, ASGITransport
from app.main import app


@pytest.fixture
async def client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


@pytest.mark.asyncio
class TestHealthEndpoint:
    async def test_health_returns_ok(self, client):
        resp = await client.get("/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"
        assert data["version"] == "2.0.0"


@pytest.mark.asyncio
class TestTemplatesEndpoint:
    async def test_list_templates(self, client):
        resp = await client.get("/v1/templates")
        assert resp.status_code == 200
        templates = resp.json()
        assert len(templates) >= 3
        ids = [t["id"] for t in templates]
        assert "product-release" in ids
        assert "security-advisory" in ids
        assert "api-release" in ids

    async def test_template_has_required_fields(self, client):
        resp = await client.get("/v1/templates")
        for t in resp.json():
            assert "id" in t
            assert "name" in t
            assert "engines" in t
            assert "description" in t


@pytest.mark.asyncio
class TestGenerateEndpoint:
    async def test_missing_data_returns_422(self, client):
        resp = await client.post("/v1/generate", json={})
        assert resp.status_code == 422

    async def test_missing_product_name(self, client):
        resp = await client.post("/v1/generate", json={
            "data": {"version": "1.0"},
        })
        # Should fail at validation step
        assert resp.status_code in (422, 500)

    async def test_valid_request_accepted(self, client):
        """Verify a valid request with real engine is accepted (may fail at API call stage)."""
        resp = await client.post("/v1/generate", json={
            "data": {"product_name": "Test", "version": "1.0"},
            "engine": "docgen",
        })
        # Will either succeed (200) or fail at Foxit API call (500), but not validation (422)
        assert resp.status_code in (200, 500)


@pytest.mark.asyncio
class TestStructurizeEndpoint:
    async def test_structurize_basic(self, client):
        resp = await client.post("/v1/ocr/structurize", json={
            "text": "Acme Platform v2.0\n\nNew Features\n- Dashboard: Real-time analytics",
        })
        assert resp.status_code == 200
        data = resp.json()
        assert "draft_json" in data
        assert "confidence" in data
        assert data["draft_json"]["version"] == "2.0"

    async def test_structurize_empty_text(self, client):
        resp = await client.post("/v1/ocr/structurize", json={"text": ""})
        assert resp.status_code == 200
        data = resp.json()
        assert data["needs_review"] is True


@pytest.mark.asyncio
class TestVerifyEndpoint:
    async def test_verify_endpoint_exists(self, client):
        """Verify the endpoint exists (will fail without a file, but proves routing)."""
        resp = await client.post("/v1/verify")
        # 422 = missing required file parameter (expected)
        assert resp.status_code == 422
