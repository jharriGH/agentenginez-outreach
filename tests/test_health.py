from fastapi.testclient import TestClient

from app.main import app


def test_health() -> None:
    client = TestClient(app)
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


def test_routes_mounted() -> None:
    client = TestClient(app)
    r = client.get("/openapi.json")
    paths = r.json()["paths"]
    assert "/agentenginez/v1/outreach/equity/trigger/{client_id}" in paths
    assert "/agentenginez/v1/outreach/postcards/just-listed/{listing_id}" in paths
    assert "/agentenginez/v1/outreach/postcards/just-sold/{listing_id}" in paths
    assert "/agentenginez/v1/outreach/open-house/checkin" in paths
    assert "/agentenginez/v1/outreach/open-house/qr/{listing_id}" in paths
    assert "/agentenginez/v1/outreach/referrals/request/{client_id}" in paths
    assert "/agentenginez/v1/outreach/referrals/reward/{referral_id}" in paths
    assert "/agentenginez/v1/outreach/reviews/request/{client_id}" in paths
    assert "/agentenginez/v1/outreach/reviews/monitor-and-respond" in paths
