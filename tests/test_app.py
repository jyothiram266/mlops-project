"""
Unit tests for the ML Inference Platform FastAPI application.
"""

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app import model


@pytest.fixture(autouse=True)
def _load_model(tmp_path):
    """Train and load a fresh model before each test."""
    from app.train import train_and_save

    model_path = train_and_save(output_dir=str(tmp_path))
    model.load_model(path=model_path)
    yield
    # Reset model state
    model._model = None


@pytest.fixture
def client():
    """FastAPI test client."""
    return TestClient(app)


class TestHealthEndpoints:
    """Tests for liveness and readiness probes."""

    def test_health(self, client):
        resp = client.get("/health")
        assert resp.status_code == 200
        assert resp.json()["status"] == "healthy"

    def test_ready_when_loaded(self, client):
        resp = client.get("/ready")
        assert resp.status_code == 200
        assert resp.json()["status"] == "ready"

    def test_ready_when_not_loaded(self, client):
        model._model = None
        resp = client.get("/ready")
        assert resp.status_code == 503


class TestPrediction:
    """Tests for the /predict inference endpoint."""

    def test_predict_valid_input(self, client):
        resp = client.post("/predict", json={"features": [5.1, 3.5, 1.4, 0.2]})
        assert resp.status_code == 200
        data = resp.json()
        assert "prediction" in data
        assert "prediction_label" in data
        assert "probabilities" in data
        assert "inference_time_ms" in data
        assert data["prediction_label"] in ("setosa", "versicolor", "virginica")

    def test_predict_iris_setosa(self, client):
        resp = client.post("/predict", json={"features": [5.1, 3.5, 1.4, 0.2]})
        assert resp.status_code == 200
        assert resp.json()["prediction_label"] == "setosa"

    def test_predict_iris_virginica(self, client):
        resp = client.post("/predict", json={"features": [7.7, 3.0, 6.1, 2.3]})
        assert resp.status_code == 200
        assert resp.json()["prediction_label"] == "virginica"

    def test_predict_wrong_feature_count(self, client):
        resp = client.post("/predict", json={"features": [1.0, 2.0]})
        assert resp.status_code == 422  # Pydantic validation error

    def test_predict_empty_features(self, client):
        resp = client.post("/predict", json={"features": []})
        assert resp.status_code == 422

    def test_predict_no_body(self, client):
        resp = client.post("/predict")
        assert resp.status_code == 422


class TestRootEndpoint:
    """Tests for the info endpoint."""

    def test_root(self, client):
        resp = client.get("/")
        assert resp.status_code == 200
        data = resp.json()
        assert data["service"] == "ML Inference Platform"
        assert data["version"] == "1.0.0"
