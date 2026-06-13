from fastapi.testclient import TestClient

from src.main import app

with TestClient(app) as client:

    def test_health_check():
        response = client.get("/health")
        assert response.status_code == 200
        assert response.json() == {"status": "ok"}

    def test_home_page():
        response = client.get("/")
        assert response.status_code == 200
        assert "IEA AGENTIQ" in response.text

    def test_create_lead():
        response = client.post(
            "/api/leads",
            json={"nombre": "Juan", "email": "juan@test.com", "empresa": "ACME"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["nombre"] == "Juan"
        assert data["email"] == "juan@test.com"
