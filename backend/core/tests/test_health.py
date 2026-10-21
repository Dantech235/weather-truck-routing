from django.test import Client


def test_health_reports_status_and_providers() -> None:
    response = Client().get("/api/health/")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert set(body["providers"]) == {"tomtom", "ors"}
