from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_health():
    response = client.get("/api/v1/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_list_datasets():
    response = client.get("/api/v1/metadata/datasets")
    assert response.status_code == 200
    ids = {d["id"] for d in response.json()}
    assert "sas2025_a_production" in ids
    assert "ahs2024_section0" in ids


def test_unknown_dataset_returns_404():
    assert client.get("/api/v1/metadata/datasets/nope").status_code == 404
