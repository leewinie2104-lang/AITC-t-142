"""Unit tests for Policy REST router and use case (M3, SCRUM-91)."""

from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from httpx import ASGITransport, AsyncClient

from app.main_api import create_app
from app.platform.config.settings import Settings


@pytest.fixture
def test_app():
    settings = Settings(
        app_name="ParkSmart-Test",
        app_env="test",
        database_url="postgresql://test:test@localhost:5432/test",
        jwt_secret_key="test-secret-key-for-unit-testing-only-at-least-32-bytes",
    )
    return create_app(settings)


@pytest.mark.asyncio
async def test_policy_check_eligibility_permit(test_app):
    """Test REST API /api/v1/policy/check-eligibility cho phép L1 thuê ô TH1."""
    transport = ASGITransport(app=test_app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        user_id = str(uuid4())
        building_id = str(uuid4())
        zone_id = str(uuid4())
        slot_id = str(uuid4())
        now = datetime.now(UTC)

        payload = {
            "user_id": user_id,
            "slot_id": slot_id,
            "slot_code": "B2-045",
            "building_id": building_id,
            "zone_id": zone_id,
            "slot_kind": "TH1",
            "open_scope": "building",
            "eligibilities": [
                {
                    "id": str(uuid4()),
                    "asset_id": str(uuid4()),
                    "zone_id": zone_id,
                    "building_id": building_id,
                    "role": "owner",
                    "status": "verified",
                    "valid_from": (now - timedelta(days=10)).isoformat(),
                    "valid_to": (now + timedelta(days=300)).isoformat(),
                }
            ],
        }

        res = await client.post("/api/v1/policy/check-eligibility", json=payload)
        assert res.status_code == 200
        data = res.json()
        assert data["effective_tier"] == "L1"
        assert data["is_eligible"] is True
        assert data["decision"] == "permit"
        assert data["reason_code"] == "ELIGIBLE"


@pytest.mark.asyncio
async def test_policy_check_eligibility_redirect_th3(test_app):
    """Test REST API /api/v1/policy/check-eligibility chuyển hướng TH3 khi L4 xin vào ô building."""
    transport = ASGITransport(app=test_app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        user_id = str(uuid4())
        building_id = str(uuid4())
        zone_id = str(uuid4())
        slot_id = str(uuid4())

        payload = {
            "user_id": user_id,
            "slot_id": slot_id,
            "slot_code": "B2-045",
            "building_id": building_id,
            "zone_id": zone_id,
            "slot_kind": "TH1",
            "open_scope": "building",
            "eligibilities": [],  # Không có tư cách -> L4
        }

        res = await client.post("/api/v1/policy/check-eligibility", json=payload)
        assert res.status_code == 200
        data = res.json()
        assert data["effective_tier"] == "L4"
        assert data["is_eligible"] is False
        assert data["decision"] == "redirect_th3"
        assert data["reason_code"] == "OUTSIDE_OPEN_SCOPE"


@pytest.mark.asyncio
async def test_policy_check_eligibility_invalid_scope_returns_422(test_app):
    """Test REST API /api/v1/policy/check-eligibility trả 422 khi truyền scope không hợp lệ."""
    transport = ASGITransport(app=test_app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        payload = {
            "user_id": str(uuid4()),
            "slot_id": str(uuid4()),
            "slot_code": "B2-045",
            "building_id": str(uuid4()),
            "zone_id": str(uuid4()),
            "open_scope": "invalid_scope_name",
        }
        res = await client.post("/api/v1/policy/check-eligibility", json=payload)
        assert res.status_code == 422
