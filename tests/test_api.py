import pytest
from httpx import AsyncClient, ASGITransport
from main import app

@pytest.mark.asyncio
async def test_create_rule():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        response = await ac.post("/rules", json={"keyword": "TESTKEY", "dm_message": "test message"})
    assert response.status_code == 201
    data = response.json()
    assert data["keyword"] == "TESTKEY"
    assert data["dm_message"] == "test message"

@pytest.mark.asyncio
async def test_get_stats():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        response = await ac.get("/stats")
    assert response.status_code == 200
    data = response.json()
    assert "sent" in data
    assert "queued" in data
    assert "failed" in data
    assert "duplicates_blocked" in data
